"""메모 질문 답 목록 · AI/데이터 통계 · 피드백 API (2026-11-20). 로컬 테스트 DB(TEST_DATABASE_URL, 0019 이상)에서 돈다."""

from __future__ import annotations

import json
import os
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

EMAILS = ("answers-a@example.test", "answers-b@example.test")
SYMBOL = "A00001"


def _engine():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url or "test" not in url:
        pytest.skip("로컬 테스트 DB(TEST_DATABASE_URL)가 없습니다")
    return create_engine(re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+psycopg://", url))


def _cleanup(c):
    c.execute(text("DELETE FROM feedbacks WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:e))"), {"e": list(EMAILS)})
    c.execute(text("DELETE FROM memos WHERE symbol = :s"), {"s": SYMBOL})
    c.execute(text("DELETE FROM user_stocks WHERE symbol = :s"), {"s": SYMBOL})
    c.execute(text("DELETE FROM users WHERE email = ANY(:e)"), {"e": list(EMAILS)})
    c.execute(text("DELETE FROM stocks WHERE symbol = :s"), {"s": SYMBOL})


@pytest.fixture()
def seeded():
    engine = _engine()
    with engine.begin() as c:
        if c.execute(text("SELECT to_regclass('credit_grants')")).scalar() is None:
            pytest.skip("0019 전 DB")
        _cleanup(c)
        c.execute(text("INSERT INTO stocks (symbol, name, market) VALUES (:s, '답변전자', 'KOSPI')"), {"s": SYMBOL})
        ua, ub = c.execute(text("INSERT INTO users (email, display_name) VALUES (:a, 'A'), (:b, 'B') RETURNING id"),
                           {"a": EMAILS[0], "b": EMAILS[1]}).scalars().all()
        c.execute(text("INSERT INTO user_stocks (user_id, symbol, status) VALUES (:u, :s, 'holding')"), {"u": ua, "s": SYMBOL})
        memo = c.execute(text("""INSERT INTO memos (user_id, symbol, kind, title, content, ai_linked)
            VALUES (:u, :s, 'note', '실적', '얼마야?', true) RETURNING id"""), {"u": ua, "s": SYMBOL}).scalar()
        c.execute(text("INSERT INTO memos (user_id, symbol, kind, title, content) VALUES (:u, :s, 'checklist', '체크', '')"),
                  {"u": ua, "s": SYMBOL})

        def item(typ, desc, status):
            return c.execute(text("""INSERT INTO tracking_items (memo_id, type, description, status)
                VALUES (:m, CAST(:t AS tracking_type), :d, CAST(:st AS tracking_status)) RETURNING id"""),
                             {"m": memo, "t": typ, "d": desc, "st": status}).scalar()
        answered, merged, pending, noans = (item("ask", "영업이익률이 얼마인지", "done"), item("ask", "작년과 비교", "done"),
                                            item("ask", "배당은 얼마인지", "active"), item("ask", "재무가 건전한지", "done"))
        topic = item("topic", "실적 소식", "active")

        def card(iid, typ, title, details):
            return c.execute(text("""INSERT INTO tracking_updates (tracking_item_id, type, title, summary, details)
                VALUES (:i, CAST(:t AS update_type), :ti, '요약', CAST(:d AS jsonb)) RETURNING id"""),
                             {"i": iid, "t": typ, "ti": title, "d": json.dumps(details, ensure_ascii=False)}).scalar()
        a_card = card(answered, "answer", "영업이익률 55%", {"answer_status": "answer", "explanation": "답 본문",
                                                          "merged_items": [{"item_id": str(merged)}],
                                                          "source_list": [{"kind": "data", "title": "재무 표"}]})
        card(noans, "answer", "재무가 건전한지", {"answer_status": "no_answer"})
        card(topic, "news", "실적 기사", {})
    yield engine, ua, ub, memo, a_card
    with engine.begin() as c:
        _cleanup(c)
    engine.dispose()


def _client(engine, user):
    from app.answers.routes import router as answers_router
    from app.auth.routes import get_current_user
    from app.db import get_db, get_read_db
    from app.stats.routes import router as stats_router

    def session():
        with Session(engine) as s:
            yield s
    app = FastAPI()
    app.include_router(answers_router)
    app.include_router(stats_router)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_read_db] = session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_memo_answers(seeded):
    engine, ua, ub, memo, a_card = seeded
    user = {"id": str(ua)}
    body = _client(engine, user).get(f"/api/v1/memos/{memo}/answers").json()
    by_q = {a["question"]: a for a in body}
    assert [a["question"] for a in body] == ["영업이익률이 얼마인지", "작년과 비교", "배당은 얼마인지", "재무가 건전한지"]
    assert by_q["영업이익률이 얼마인지"]["status"] == "answered"
    assert by_q["영업이익률이 얼마인지"]["answer"]["text"] == "답 본문"
    assert by_q["영업이익률이 얼마인지"]["answer"]["sources"] == [{"kind": "data", "title": "재무 표"}]
    assert by_q["작년과 비교"]["answer"]["id"] == str(a_card)          # 합쳐 답한 카드도 답으로
    assert by_q["배당은 얼마인지"] == {**by_q["배당은 얼마인지"], "status": "pending", "answer": None}
    assert by_q["재무가 건전한지"]["status"] == "no_answer"
    user["id"] = str(ub)
    assert _client(engine, user).get(f"/api/v1/memos/{memo}/answers").status_code == 404   # 다른 사람 메모


def test_stats_and_feedback(seeded):
    engine, ua, _ub, _memo, _ = seeded
    client = _client(engine, {"id": str(ua)})
    assert client.get("/api/v1/ai/stats").json() == {"linked_memos": 1, "updates_this_month": 3, "linked_stocks": 1}
    assert client.get("/api/v1/data/stats").json() == {"memos": 1, "journals": 0, "stocks": 1}
    ok = client.post("/api/v1/feedback", json={"kind": "bug", "rating": 4, "screen": "home", "categories": ["속도"],
                                               "message": " 느려요 "})
    assert ok.status_code == 204
    assert client.post("/api/v1/feedback", json={"kind": "bug", "rating": 6, "message": "x"}).status_code == 422
    assert client.post("/api/v1/feedback", json={"kind": "general", "message": "   "}).status_code == 422
    with engine.connect() as c:
        row = c.execute(text("SELECT kind, screen, types, body, rating FROM feedbacks WHERE user_id = :u"), {"u": ua}).one()
    assert tuple(row) == ("bug", "home", ["속도"], "느려요", 4)
