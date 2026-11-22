"""크레딧 주기 (2026-11-22 결정 6) — 실제 DB 없이.

시작점 = 첫 월 기본량 지급일(무료 = 첫 사용일), 그 뒤 시작점 기준 한 달 고정 주기, 짧은 달은 말일,
경계 = 한국 시간 그날 0시, 중간 접속 · 오래 안 들어와도 다시 시작하지 않음, 같은 주기 중복 지급 없음.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.credits import ledger

KST = ZoneInfo("Asia/Seoul")


def kst(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=KST)


# ─── 순수 계산 ───────────────────────────────────────────────────
def test_month_end_anchor_uses_last_day_without_drift():
    a = date(2026, 1, 31)
    assert [ledger.add_months(a, k) for k in range(4)] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    assert ledger.add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)            # 윤년
    assert ledger.cycle(a, date(2026, 3, 1)) == (date(2026, 2, 28), date(2026, 3, 31))
    assert ledger.cycle(a, date(2026, 3, 31)) == (date(2026, 3, 31), date(2026, 4, 30))


def test_cycle_mid_and_long_absence_keep_anchor_rhythm():
    a = date(2026, 11, 20)
    assert ledger.cycle(a, date(2026, 11, 20)) == (date(2026, 11, 20), date(2026, 12, 20))
    assert ledger.cycle(a, date(2026, 12, 19)) == (date(2026, 11, 20), date(2026, 12, 20))   # 중간
    assert ledger.cycle(a, date(2027, 4, 3)) == (date(2027, 3, 20), date(2027, 4, 20))       # 넉 달 만에 와도 20일 주기
    assert ledger.cycle(a, date(2026, 11, 1)) == (a, date(2026, 12, 20))                     # 시작점 전 날짜


# ─── 저장소 흉내 (credit_grants 만) ───────────────────────────────
class R:
    def __init__(self, v=None, row=None):
        self.v, self.row = v, row

    def scalar(self):
        return self.v

    def first(self):
        return self.row


class FakeCreditDb:
    """ensure_monthly · user_period 가 쓰는 SQL 만: 첫 지급일 · 플랜 · 월 기본량 지급(UNIQUE) · 장부."""

    def __init__(self, plan="free"):
        self.plan = plan
        self.grants: list[dict] = []
        self.ledger: list[dict] = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        p = params or {}
        if sql.startswith("SELECT min(period_start) FROM credit_grants"):
            starts = [g["period_start"] for g in self.grants if g["user_id"] == p["u"] and g["source"] == "monthly"]
            return R(min(starts) if starts else None)
        if sql.startswith("SELECT u.plan::text, pl.monthly_credits"):
            return R(row=(self.plan, None))
        if sql.startswith("INSERT INTO credit_grants") and "'monthly'" in sql:
            if any(g["user_id"] == p["u"] and g["source"] == "monthly" and g["period_start"] == p["p"] for g in self.grants):
                return R(None)                                                 # ON CONFLICT DO NOTHING
            gid = len(self.grants) + 1
            self.grants.append({"id": gid, "user_id": p["u"], "source": "monthly", "amount": p["a"], "period_start": p["p"], "expires_at": p["e"]})
            return R(gid)
        if sql.startswith("INSERT INTO credit_ledger"):
            self.ledger.append(dict(p))
            return R()
        raise AssertionError(f"unexpected SQL: {sql[:80]}")

    def starts(self):
        return [g["period_start"] for g in self.grants]


def test_first_use_sets_anchor_and_mid_access_does_not_restart():
    db = FakeCreditDb()
    assert ledger.ensure_monthly(db, 7, kst(2026, 11, 20, 15)) == 30            # 첫 사용 = 시작점 11/20
    assert ledger.ensure_monthly(db, 7, kst(2026, 11, 28)) == 0                 # 중간 접속: 새로 주지 않음
    assert ledger.ensure_monthly(db, 7, kst(2026, 12, 19, 23, 59)) == 0         # 경계 직전 (KST)
    assert ledger.ensure_monthly(db, 7, kst(2026, 12, 20, 0, 0)) == 30          # 경계 (KST 0시) → 다음 주기
    assert db.starts() == [date(2026, 11, 20), date(2026, 12, 20)]
    assert db.grants[0]["expires_at"] == datetime(2026, 12, 20, tzinfo=KST)     # 다음 주기 시작에 만료


def test_no_duplicate_grant_in_same_cycle():
    db = FakeCreditDb()
    for when in (kst(2026, 11, 20), kst(2026, 11, 20, 18), kst(2026, 12, 1), kst(2026, 12, 19, 23, 59)):
        ledger.ensure_monthly(db, 7, when)
    assert len(db.grants) == 1 and len(db.ledger) == 1


def test_long_absence_keeps_anchor_rhythm_not_access_day():
    db = FakeCreditDb()
    ledger.ensure_monthly(db, 7, kst(2026, 11, 20))
    ledger.ensure_monthly(db, 7, kst(2027, 2, 3))                               # 석 달 만에 접속
    assert db.starts() == [date(2026, 11, 20), date(2027, 1, 20)]               # 2/3 로 다시 시작하지 않음


def test_month_end_anchor_grants():
    db = FakeCreditDb()
    for when in (kst(2026, 1, 31), kst(2026, 2, 28), kst(2026, 3, 31), kst(2026, 3, 30)):
        ledger.ensure_monthly(db, 7, when)
    assert db.starts() == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_paid_plan_uses_same_anchor_rule_for_now():
    # 결제일 저장 칸이 없어 유료도 첫 지급일이 시작점 (결제 연결 때 anchor_date 에서 결제일로)
    db = FakeCreditDb(plan="plus")
    assert ledger.ensure_monthly(db, 7, kst(2026, 11, 5)) == 100                # plus 가안 100 (configs/credits.yaml)
    assert ledger.user_period(db, 7, kst(2026, 11, 30))[0] == date(2026, 11, 5)


def test_existing_calendar_grant_keeps_first_of_month_cycle():
    # 0019 때 달력 월로 받은 사용자 (period_start = 11/01) → 계속 매달 1일
    db = FakeCreditDb()
    db.grants.append({"id": 1, "user_id": 7, "source": "monthly", "amount": 30, "period_start": date(2026, 11, 1), "expires_at": None})
    start, start_at, nxt = ledger.user_period(db, 7, kst(2026, 11, 22))
    assert (start, nxt) == (date(2026, 11, 1), datetime(2026, 12, 1, tzinfo=KST))
    assert start_at == datetime(2026, 11, 1, tzinfo=KST)


def test_renew_label_is_day_before_next_cycle():
    u = ledger.Usage(0, 0, 30, date(2026, 11, 20), datetime(2026, 12, 20, tzinfo=KST), False)
    assert u.to_dict()["renew_label"] == "12.19 갱신"
    assert u.renews_at - timedelta(days=1) == datetime(2026, 12, 19, tzinfo=KST)
