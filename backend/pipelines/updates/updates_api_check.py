"""카드 조회 API 점검 (2026-11-11): 로컬 테스트 DB에서 FastAPI 경로를 그대로 부른다 (로그인만 시범 사용자로 바꿔 끼움). LLM 없음.

    PYTHONPATH=backend python -m pipelines.updates.updates_api_check

GET /stocks/{code}/ai-updates · GET /memos/{id}/timeline · GET /ai-updates/summary · POST /ai-updates/{id}/read
쓰기는 읽음 처리 한 건뿐이고 대상은 TEST_DATABASE_URL의 로컬 테스트 DB만.
"""

from __future__ import annotations

import json
import os


def main() -> int:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.auth.routes import get_current_user
    from app.db import get_db, get_read_db
    from app.updates.routes import router

    from .db_store import check_test_target

    dsn = os.environ.get("TEST_DATABASE_URL", "")
    target = check_test_target(dsn)
    url = dsn.replace("postgresql://", "postgresql+psycopg://", 1) if dsn.startswith("postgresql://") else dsn
    Session = sessionmaker(bind=create_engine(url), expire_on_commit=False)

    def db():
        s = Session()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    with Session() as s:
        from sqlalchemy import text
        uid = s.execute(text("SELECT id FROM users WHERE email = 'updates-test@example.invalid'")).scalar()
        memo_with_card = s.execute(text("""SELECT ti.memo_id FROM tracking_updates tu JOIN tracking_items ti ON ti.id = tu.tracking_item_id
            ORDER BY tu.id LIMIT 1""")).scalar()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": uid}
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_read_db] = db
    c = TestClient(app)
    print(f"테스트 DB: {target} · 사용자 {uid}")

    r = c.get("/api/v1/stocks/005930/ai-updates")
    cards = r.json()
    print(f"\nGET /stocks/005930/ai-updates → {r.status_code} · 카드 {len(cards)}건")
    for u in cards[:3]:
        print("  " + json.dumps({k: u[k] for k in ("id", "type", "title", "headline", "source", "published_at", "memo_title",
                                                   "memo_version", "read", "relevance")}, ensure_ascii=False))
        print(f"    item {u['item']} · sources {len(u['sources'])} · price {u['price']} · card keys {sorted(u['card'])[:8]}")
    r = c.get("/api/v1/stocks/000660/ai-updates")
    price = [u for u in r.json() if u["type"] == "price"]
    print(f"\nGET /stocks/000660/ai-updates → {r.status_code} · 카드 {len(r.json())}건 · 가격 카드 "
          + json.dumps([{k: p[k] for k in ("title", "headline", "price")} for p in price], ensure_ascii=False))
    r = c.get(f"/api/v1/memos/{memo_with_card}/timeline")
    t = r.json()
    print(f"\nGET /memos/{memo_with_card}/timeline → {r.status_code} · entries {[e['kind'] for e in t['entries']]} · "
          f"price_condition_count {t['price_condition_count']}")
    for it in t["tracking_items"]:
        print(f"  항목 {it['id']} {it['type']} {it['description']} · {it['status']} · last_checked_at {it['last_checked_at']}")
    r = c.get("/api/v1/ai-updates/summary")
    print(f"\nGET /ai-updates/summary → {r.status_code} · " + json.dumps(
        [{"stock": s["stock_code"], "new": s["new_count"], "memos": len(s["memos"])} for s in r.json()], ensure_ascii=False))
    first = cards[0]["id"] if cards else None
    if first:
        r = c.post(f"/api/v1/ai-updates/{first}/read")
        after = c.get("/api/v1/ai-updates/summary").json()
        print(f"\nPOST /ai-updates/{first}/read → {r.status_code} · summary 뒤 " + json.dumps(
            [{"stock": s["stock_code"], "new": s["new_count"]} for s in after], ensure_ascii=False))
        print(f"POST /ai-updates/999999/read → {c.post('/api/v1/ai-updates/999999/read').status_code}")
    print(f"GET /memos/999999/timeline → {c.get('/api/v1/memos/999999/timeline').status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
