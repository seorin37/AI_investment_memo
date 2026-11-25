"""크레딧 묶음·장부 (2026-11-20, 0019 credit_grants · credit_ledger · plan_limits.monthly_credits).

규칙 (configs/credits.yaml)
- 기간은 사용자 시작점 기준 한 달 고정 주기 (2026-11-22 결정 6). 시작점 = 첫 월 기본량 지급일(무료는 첫 사용일),
  짧은 달은 말일 (1/31 → 2/28 → 3/31). 경계는 한국 시간 그날 0시. 중간 접속 · 오래 안 들어와도 주기를 다시 시작하지 않는다.
  그 주기 기본량(monthly)은 처음 필요할 때 지급하고, 다음 주기 시작에 만료된다. 같은 주기는 한 번만 (uq_credit_grants_monthly).
  유료 결제일 시작점은 결제가 연결되면 anchor_date 에서 쓴다 (지금은 저장된 결제일이 없음).
- 산 크레딧(purchase)은 다음 달로 넘어간다 (유효기간 purchase_valid_days, 0이면 만료 없음).
- 쓸 때는 만료가 빠른 묶음부터 꺼낸다 → 이번 달 기본량을 먼저 쓰고 산 크레딧은 나중에 쓴다. 묶음마다 장부 한 줄.
- 잔액보다 많이 쓰려 하면 잔액까지만 차감한다 (음수 잔액 없음). 차감한 양을 돌려준다.
- 같은 대상(ref_kind, ref_id, reason)은 한 번만 차감한다 (매일 실행을 다시 돌려도 두 번 빠지지 않게).
- 모든 함수는 호출자의 연결(SQLAlchemy Connection 또는 Session)과 트랜잭션 안에서 돈다. commit은 호출자가 한다.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import text

SEOUL = ZoneInfo("Asia/Seoul")
CONFIG_PATH = "configs/credits.yaml"


@lru_cache(maxsize=1)
def rules() -> dict:
    from pipelines.common.config import load_config
    return load_config(CONFIG_PATH)


def cost(reason: str) -> int:
    return int((rules().get("costs") or {}).get(reason, 0))


def _midnight(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), SEOUL)


def add_months(anchor: date, months: int) -> date:
    """시작점에서 months 달 뒤 같은 날 — 그 달에 그날이 없으면 말일 (1/31 → 2/28 → 3/31: 늘 시작점에서 바로 계산해 밀리지 않음)."""
    y, m = divmod(anchor.month - 1 + months, 12)
    y, m = anchor.year + y, m + 1
    return date(y, m, min(anchor.day, calendar.monthrange(y, m)[1]))


def cycle(anchor: date, today: date) -> tuple[date, date]:
    """시작점 기준 한 달 고정 주기 중 today 가 든 주기의 (시작일, 다음 시작일). 시작점 전 날짜면 첫 주기."""
    if today < anchor:
        return anchor, add_months(anchor, 1)
    k = (today.year - anchor.year) * 12 + (today.month - anchor.month)
    if add_months(anchor, k) > today:
        k -= 1
    return add_months(anchor, k), add_months(anchor, k + 1)


def anchor_date(db, user_id: int, today: date) -> date:
    """주기 시작점 (2026-11-22 결정 6) = 이 사용자의 첫 월 기본량 지급일(credit_grants.period_start 중 가장 이른 날).
    아직 없으면 오늘 = 첫 사용일. 새 칸 없이 credit_grants 로 정한다.
    - 유료 플랜의 결제일 시작점: 결제가 연결되지 않아 저장된 결제일이 없다 → 지금은 무료와 같은 규칙 (결제 연결 때 여기서 결제일을 쓴다)
    - 0019 달력 월로 이미 받은 사용자는 첫 지급일이 1일이라 지금처럼 매달 1일 주기가 이어진다"""
    first = db.execute(text("""SELECT min(period_start) FROM credit_grants WHERE user_id = :u AND source = 'monthly'"""),
                       {"u": user_id}).scalar()
    return first or today


def user_period(db, user_id: int, now: datetime | None = None) -> tuple[date, datetime, datetime]:
    """(주기 시작일, 시작 시각, 다음 주기 시작 시각) — 사용자 시작점 기준 한 달 고정 주기. 경계는 한국 시간 그날 0시."""
    today = (now or datetime.now(SEOUL)).astimezone(SEOUL).date()
    start, nxt = cycle(anchor_date(db, user_id, today), today)
    return start, _midnight(start), _midnight(nxt)


def monthly_amount(db, user_id: int) -> int:
    row = db.execute(text("""SELECT u.plan::text, pl.monthly_credits FROM users u
        LEFT JOIN plan_limits pl ON pl.plan = u.plan WHERE u.id = :u"""), {"u": user_id}).first()
    if row is None:
        return 0
    plan, db_amount = row
    if db_amount:
        return int(db_amount)
    return int((rules().get("monthly") or {}).get(plan or "free", 0))


def ensure_monthly(db, user_id: int, now: datetime | None = None) -> int:
    """이번 주기 기본량을 아직 안 줬으면 준다. 새로 준 양 (이미 있으면 0). 같은 주기는 uq_credit_grants_monthly 로 한 번만."""
    start, _, nxt = user_period(db, user_id, now)
    amount = monthly_amount(db, user_id)
    if amount <= 0:
        return 0
    gid = db.execute(text("""INSERT INTO credit_grants (user_id, source, amount, remaining, period_start, expires_at)
        VALUES (:u, 'monthly', :a, :a, :p, :e)
        ON CONFLICT (user_id, period_start) WHERE source = 'monthly' DO NOTHING RETURNING id"""),
                     {"u": user_id, "a": amount, "p": start, "e": nxt}).scalar()
    if gid is None:
        return 0
    db.execute(text("""INSERT INTO credit_ledger (user_id, grant_id, delta, reason, ref_kind, ref_id)
        VALUES (:u, :g, :a, 'grant', 'credit_grant', :g)"""), {"u": user_id, "g": gid, "a": amount})
    return amount


def expire(db, user_id: int, now: datetime | None = None) -> int:
    """만료 시각이 지난 묶음의 남은 양을 0으로 (장부에 expire 줄). 만료된 양."""
    now = now or datetime.now(SEOUL)
    rows = db.execute(text("""UPDATE credit_grants g SET remaining = 0 FROM (
          SELECT id, remaining FROM credit_grants WHERE user_id = :u AND remaining > 0 AND expires_at IS NOT NULL
            AND expires_at <= :now FOR UPDATE) old
        WHERE g.id = old.id RETURNING g.id, old.remaining"""), {"u": user_id, "now": now}).all()
    for gid, left in rows:
        db.execute(text("""INSERT INTO credit_ledger (user_id, grant_id, delta, reason, ref_kind, ref_id)
            VALUES (:u, :g, :d, 'expire', 'credit_grant', :g)"""), {"u": user_id, "g": gid, "d": -int(left)})
    return sum(int(left) for _, left in rows)


def refresh(db, user_id: int, now: datetime | None = None) -> int:
    """만료 → 이번 기간 기본량. 2026-11-24: 지난 기간을 크레딧 0으로 끝낸 채 갱신되면 AI 연결 메모를 모두 끈다
    (선택 창에서 충전·업그레이드를 하지 않은 경우, app/credits/ai_off.py). 자동으로 끈 메모 수."""
    from . import ai_off
    left_before = int(db.execute(text("SELECT COALESCE(sum(remaining), 0) FROM credit_grants WHERE user_id = :u"),
                                 {"u": user_id}).scalar() or 0)          # 만료 처리 전 = 지난 기간이 끝날 때 남은 양
    had_prior = db.execute(text("SELECT 1 FROM credit_grants WHERE user_id = :u AND source = 'monthly' LIMIT 1"),
                           {"u": user_id}).first() is not None
    expire(db, user_id, now)
    granted = ensure_monthly(db, user_id, now)
    if ai_off.should_auto_off(granted, had_prior, left_before):
        return ai_off.turn_off_all(db, user_id, auto=True)
    return 0


def balance(db, user_id: int, now: datetime | None = None) -> int:
    now = now or datetime.now(SEOUL)
    return int(db.execute(text("""SELECT COALESCE(sum(remaining), 0) FROM credit_grants
        WHERE user_id = :u AND remaining > 0 AND (expires_at IS NULL OR expires_at > :now)"""),
                          {"u": user_id, "now": now}).scalar() or 0)


def spend(db, user_id: int, amount: int, reason: str, ref_kind: str | None = None, ref_id: int | None = None,
          now: datetime | None = None) -> int:
    """amount만큼 차감 (잔액이 모자라면 잔액까지만). 차감한 양. 같은 대상은 한 번만."""
    if amount <= 0:
        return 0
    now = now or datetime.now(SEOUL)
    if ref_id is not None and db.execute(text("""SELECT 1 FROM credit_ledger WHERE user_id = :u AND reason = :r
            AND ref_kind = :k AND ref_id = :i AND delta < 0 LIMIT 1"""),
                                         {"u": user_id, "r": reason, "k": ref_kind, "i": ref_id}).first():
        return 0
    refresh(db, user_id, now)
    grants = db.execute(text("""SELECT id, remaining FROM credit_grants
        WHERE user_id = :u AND remaining > 0 AND (expires_at IS NULL OR expires_at > :now)
        ORDER BY expires_at NULLS LAST, granted_at, id FOR UPDATE"""), {"u": user_id, "now": now}).all()
    left, charged = amount, 0
    for gid, remaining in grants:
        if left <= 0:
            break
        take = min(left, int(remaining))
        db.execute(text("UPDATE credit_grants SET remaining = remaining - :t WHERE id = :g"), {"t": take, "g": gid})
        db.execute(text("""INSERT INTO credit_ledger (user_id, grant_id, delta, reason, ref_kind, ref_id)
            VALUES (:u, :g, :d, :r, :k, :i)"""), {"u": user_id, "g": gid, "d": -take, "r": reason, "k": ref_kind, "i": ref_id})
        left -= take
        charged += take
    return charged


def grant_purchase(db, user_id: int, amount: int, payment_ref: str, now: datetime | None = None) -> int | None:
    """산 크레딧 묶음 (결제 연동 전에는 관리자 명령으로만). 같은 결제번호는 한 번만. 새 묶음 id (이미 있으면 None)."""
    now = now or datetime.now(SEOUL)
    days = int(rules().get("purchase_valid_days") or 0)
    gid = db.execute(text("""INSERT INTO credit_grants (user_id, source, amount, remaining, granted_at, expires_at, payment_ref)
        VALUES (:u, 'purchase', :a, :a, :now, :e, :p)
        ON CONFLICT (payment_ref) WHERE payment_ref IS NOT NULL DO NOTHING RETURNING id"""),
                     {"u": user_id, "a": amount, "now": now, "e": now + timedelta(days=days) if days else None,
                      "p": payment_ref}).scalar()
    if gid is not None:
        db.execute(text("""INSERT INTO credit_ledger (user_id, grant_id, delta, reason, ref_kind, ref_id)
            VALUES (:u, :g, :a, 'purchase', 'credit_grant', :g)"""), {"u": user_id, "g": gid, "a": amount})
    return gid


@dataclass
class Usage:
    usage_percent: int
    used: int
    balance: int
    period_start: date
    renews_at: datetime
    paused: bool

    def to_dict(self) -> dict:
        return {"usage_percent": self.usage_percent, "used": self.used, "balance": self.balance,
                "period_start": self.period_start.isoformat(), "renews_at": self.renews_at.isoformat(),
                "renew_label": f"{(self.renews_at - timedelta(days=1)):%m.%d} 갱신", "paused": self.paused}


def usage(db, user_id: int, now: datetime | None = None) -> Usage:
    """화면의 'AI 사용량 %' = 이번 기간에 쓴 양 ÷ (쓴 양 + 지금 남은 양). 남은 게 0이면 AI 업데이트 멈춤."""
    now = now or datetime.now(SEOUL)
    refresh(db, user_id, now)
    start, start_at, nxt = user_period(db, user_id, now)
    used = int(-(db.execute(text("""SELECT COALESCE(sum(delta), 0) FROM credit_ledger
        WHERE user_id = :u AND delta < 0 AND reason NOT IN ('expire', 'refund', 'adjust') AND created_at >= :s"""),
                            {"u": user_id, "s": start_at}).scalar() or 0))
    left = balance(db, user_id, now)
    total = used + left
    pct = 100 if total <= 0 else min(100, round(used * 100 / total))   # 받은 크레딧이 하나도 없으면 다 쓴 것과 같다
    return Usage(pct, used, left, start, nxt, left <= 0)
