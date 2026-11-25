"""매일 AI 업데이트(pipelines.updates.daily)와 크레딧 잇기 (2026-11-20).

- eligible_item_ids: 실행 전. 잔액이 있는 사용자의 활성 항목만 처리 대상으로 돌려준다.
  잔액이 0인 사용자의 항목은 가격 조건까지 전부 건너뛴다 (2026-11-24: 가격 조건도 AI 추적 항목이라 '다 끄기'에 맞춤.
  그전에는 가격 조건은 LLM이 없어 무료라 계속 확인했다) = 화면의 '충전하지 않으면 AI 연결이 모두 꺼져요' 끄기 대기.
- charge_run: 실행 후. 이번 실행이 만든 카드(db_rows.json의 tracking_updates)마다 차감한다.
  answer → costs.answer, news·disclosure → costs.card, price_condition → costs.price_condition(기본 0).
  잔액이 모자라면 잔액까지만 (그날 카드는 이미 보였다). 같은 카드는 두 번 차감하지 않는다.
- 쓰기 대상은 pipelines.updates.db_store.check_test_target으로 확인한다 (로컬 테스트 DB, 또는 allow_shared면 공용 DB).
  pipelines/updates 패키지는 db_store 말고는 DB에 쓰지 않는다는 규칙(ReadOnlyGuardTest)이 있어 크레딧 쓰기는 여기 둔다.
"""

from __future__ import annotations

import re

from sqlalchemy import create_engine, text

from . import ledger

ITEMS_SQL = """SELECT ti.id, ti.type::text, m.user_id FROM tracking_items ti JOIN memos m ON m.id = ti.memo_id
WHERE ti.status = 'active' AND m.deleted_at IS NULL AND m.ai_linked AND m.kind = 'note'
  AND (:all OR btrim(m.symbol) = ANY(:symbols))"""
REASON = {"answer": "answer", "news": "card", "disclosure": "card", "price_condition": "price_condition"}


def _engine(dsn: str, allow_shared: bool):
    from pipelines.updates.db_store import check_test_target
    check_test_target(dsn, allow_shared)
    url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", dsn.strip())
    return create_engine(url, pool_pre_ping=True)


def eligible_item_ids(dsn: str, symbols, allow_shared: bool = False) -> tuple[list[str], dict]:
    """(처리할 항목 id, {"paused_users": [...], "skipped_items": n, "auto_off": {사용자: 끈 메모 수}}).
    기본량 지급·만료도 여기서 한다. 2026-11-24: 사용자마다 refresh(갱신일 자동 끄기 포함)를 먼저 하고 항목을 다시 뽑는다
    — 갱신일 아침에 방금 꺼진 메모가 그날 확인에 섞이지 않게."""
    engine = _engine(dsn, allow_shared)
    params = {"all": symbols is None, "symbols": list(symbols or [])}
    try:
        with engine.begin() as db:
            users = sorted({u for _, _, u in db.execute(text(ITEMS_SQL), params).all()})
            balances, auto_off = {}, {}
            for uid in users:
                n = ledger.refresh(db, uid)
                if n:
                    auto_off[uid] = n
                balances[uid] = ledger.balance(db, uid)
            rows = db.execute(text(ITEMS_SQL), params).all()      # 자동으로 꺼진 메모는 여기서 빠진다
    finally:
        engine.dispose()
    keep = [str(i) for i, _typ, u in rows if balances.get(u, 0) > 0]
    paused = sorted(u for u, b in balances.items() if b <= 0)
    return keep, {"paused_users": paused, "skipped_items": len(rows) - len(keep), "users": len(balances), "auto_off": auto_off}


def charge_run(dsn: str, update_ids: list[int], allow_shared: bool = False) -> dict:
    """이번 실행이 만든 카드마다 차감. {"cards": n, "charged": 합계, "short": 잔액이 모자라 못 뺀 양}."""
    out = {"cards": 0, "charged": 0, "short": 0}
    if not update_ids:
        return out
    engine = _engine(dsn, allow_shared)
    try:
        with engine.begin() as db:
            rows = db.execute(text("""SELECT tu.id, tu.type::text, m.user_id, tu.details->>'answer_status' FROM tracking_updates tu
                JOIN tracking_items ti ON ti.id = tu.tracking_item_id JOIN memos m ON m.id = ti.memo_id
                WHERE tu.id = ANY(:ids) ORDER BY tu.id"""), {"ids": [int(i) for i in update_ids]}).all()
            for uid_, utype, user_id, astatus in rows:
                reason = REASON.get(utype, "card")
                unverified = utype == "answer" and astatus == "no_answer"   # 2026-11-25 '확인되지 않았어요' 답 (기본 0크레딧)
                want = ledger.cost("answer_unverified" if unverified else reason)   # 장부 사유는 answer 그대로 (credit_ledger CHECK)
                if want <= 0:
                    continue
                if _already(db, user_id, reason, uid_):          # 다시 돌려도 같은 카드는 한 번만
                    continue
                got = ledger.spend(db, user_id, want, reason, "tracking_update", int(uid_))
                out["cards"] += 1
                out["charged"] += got
                out["short"] += want - got                       # 잔액이 모자라 못 뺀 양 (그날 카드는 이미 보였다)
    finally:
        engine.dispose()
    return out


def _already(db, user_id: int, reason: str, update_id: int) -> bool:
    return db.execute(text("""SELECT 1 FROM credit_ledger WHERE user_id = :u AND reason = :r AND ref_kind = 'tracking_update'
        AND ref_id = :i AND delta < 0 LIMIT 1"""), {"u": user_id, "r": reason, "i": int(update_id)}).first() is not None
