"""요금제 카탈로그·추적 항목 상한 (2026-11-25 팀 확정안, configs/credits.yaml).

- catalog(): 화면용 요금제 목록(가격·첫 달 가격·월 크레딧·추적 항목 상한)과 추가 크레딧 상품. GET /api/v1/plans.
- tracking_cap(): 그 사용자 요금제의 AI 추적 항목 상한 = 설정 파일 tracking_items. (plan_limits.max_active_tracking_items는 0002 시드의
  옛 값(free 10 · pro 제한 없음)이 남아 있을 수 있어 쓰지 않는다. 화면에 보여 주는 숫자와 실제 상한이 같아야 하므로)
- active_items(): 지금 켜져 있는 AI 추적 항목 수 (AI 연결 메모의 active 항목).
- 상한은 '새로 켤 때'만 막는다. 이미 상한보다 많이 켜 둔 사용자의 항목은 멈추지 않는다 (2026-11-25 결정).
"""

from __future__ import annotations

from sqlalchemy import text

from .ledger import rules

PLAN_CODES = ("free", "plus", "pro")


def catalog() -> dict:
    r = rules()
    monthly = r.get("monthly") or {}
    caps = r.get("tracking_items") or {}
    plans = []
    for p in r.get("plans") or []:
        code = p["code"]
        plans.append({
            "code": code, "name": p.get("name") or code, "price": int(p.get("price") or 0),
            "first_month_price": None if p.get("first_month_price") is None else int(p["first_month_price"]),
            "monthly_credits": int(monthly.get(code, 0)), "tracking_items": int(caps.get(code, 0)),
            "summary": p.get("summary") or "", "recommended": bool(p.get("recommended", False)),
        })
    packs = [{"credits": int(x["credits"]), "price": int(x["price"])} for x in r.get("credit_packs") or []]
    costs = {k: int(v) for k, v in (r.get("costs") or {}).items()}
    return {"plans": plans, "credit_packs": packs, "costs": costs}


def user_plan(db, user_id: int) -> str:
    plan = db.execute(text("SELECT plan::text FROM users WHERE id = :u"), {"u": user_id}).scalar()
    return plan if plan in PLAN_CODES else "free"


def tracking_cap(db, user_id: int) -> int:
    return int((rules().get("tracking_items") or {}).get(user_plan(db, user_id), 0))


def active_items(db, user_id: int) -> int:
    return int(db.execute(text("""SELECT count(*) FROM tracking_items ti JOIN memos m ON m.id = ti.memo_id
        WHERE m.user_id = :u AND m.ai_linked AND m.kind = 'note' AND m.deleted_at IS NULL AND ti.status = 'active'"""),
                          {"u": user_id}).scalar() or 0)
