"""내 종목 memo_count · ai_count (GET /api/v1/stocks · 2026-11-22).

- SQL 문장: 한 번의 집계 JOIN · 휴지통 제외 · memo_count 는 note 만 · ai_count 는 /ai/stats linked_memos 와 같은 조건
- 실제 DB(선택): 기존 STOCK_API_TEST_DATABASE_URL + STOCK_API_TEST_ALLOW=1 패턴. 없으면 건너뜀 (중앙 DB 금지)
"""

from __future__ import annotations

import inspect
import os
import re

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.stats.routes import ai_stats
from app.stocks import repository as stock_repo
from app.stocks.repository import StockRepository
from app.stocks.schemas import MyStockResponse


def flat(sql: str) -> str:
    return " ".join(sql.split())


class RecordingSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((flat(str(statement)), params))
        return self

    def mappings(self):
        return self

    def all(self):
        return []

    def first(self):
        return None


def test_list_and_get_use_one_grouped_join_not_per_stock_queries():
    for call in (lambda r: r.list_user_stocks(7), lambda r: r.get_user_stock(7, "005930")):
        s = RecordingSession()
        call(StockRepository(s))
        assert len(s.calls) == 1                                    # 종목마다 따로 묻지 않음
        sql, params = s.calls[0]
        assert "LEFT JOIN ( SELECT symbol, count(*) FILTER (WHERE kind = 'note') AS memo_count, count(*) FILTER (WHERE ai_linked) AS ai_count FROM memos WHERE user_id = :user_id AND deleted_at IS NULL GROUP BY symbol ) mc ON mc.symbol = us.symbol" in sql
        assert "COALESCE(mc.memo_count, 0)::integer AS memo_count" in sql    # 메모 0개 종목은 0
        assert "COALESCE(mc.ai_count, 0)::integer AS ai_count" in sql
        assert params["user_id"] == 7


def test_ai_count_condition_matches_ai_stats_linked_memos():
    # linked_memos: memos WHERE user_id = :u AND deleted_at IS NULL AND ai_linked (새 기준을 만들지 않음)
    linked = flat(inspect.getsource(ai_stats))
    assert re.search(r"FROM memos WHERE user_id = :u AND deleted_at IS NULL AND ai_linked\)", linked)
    join = flat(stock_repo.MEMO_COUNTS_JOIN)
    assert "FROM memos WHERE user_id = :user_id AND deleted_at IS NULL" in join
    assert "count(*) FILTER (WHERE ai_linked) AS ai_count" in join


def test_response_has_counts_with_zero_default():
    base = {"code": "005930", "name": "삼성전자", "market": "KOSPI", "status": "watching", "added_at": "2026-11-22T00:00:00Z"}
    assert MyStockResponse(**base).model_dump()["memo_count"] == 0
    got = MyStockResponse(**base, memo_count=3, ai_count=2).model_dump()
    assert (got["memo_count"], got["ai_count"]) == (3, 2)


# ─── 실제 DB (선택) ────────────────────────────────────────────────
TEST_URL = os.getenv("STOCK_API_TEST_DATABASE_URL", "")
TEST_ALLOWED = os.getenv("STOCK_API_TEST_ALLOW") == "1"
A, B, C = "T00101", "T00102", "T00103"
EMAIL = "stock-memo-counts@example.test"


@pytest.fixture()
def db_engine():
    if not TEST_URL or not TEST_ALLOWED:
        pytest.skip("explicit isolated PostgreSQL test database was not provided")
    if not (make_url(TEST_URL).database or "").endswith("_test"):
        pytest.fail("refusing to use a database whose name does not end with _test")
    engine = create_engine(TEST_URL, pool_pre_ping=True)

    def clean(c):
        c.execute(text("DELETE FROM memos WHERE symbol = ANY(:s)"), {"s": [A, B, C]})
        c.execute(text("DELETE FROM user_stocks WHERE symbol = ANY(:s)"), {"s": [A, B, C]})
        c.execute(text("DELETE FROM users WHERE email = :e"), {"e": EMAIL})
        c.execute(text("DELETE FROM stocks WHERE symbol = ANY(:s)"), {"s": [A, B, C]})

    with engine.begin() as c:
        clean(c)
    yield engine
    with engine.begin() as c:
        clean(c)
    engine.dispose()


def test_postgres_counts_exclude_trash_and_checklists_and_sum_to_linked_memos(db_engine):
    with db_engine.begin() as c:
        c.execute(text("INSERT INTO stocks (symbol, name, market) VALUES (:a,'카운트전자','KOSPI'), (:b,'카운트금융','KOSPI'), (:c,'카운트화학','KOSPI')"),
                  {"a": A, "b": B, "c": C})
        uid = c.execute(text("INSERT INTO users (email, display_name) VALUES (:e, '카운트') RETURNING id"), {"e": EMAIL}).scalar_one()
        for sym in (A, B, C):
            c.execute(text("INSERT INTO user_stocks (user_id, symbol, status) VALUES (:u, :s, 'watching')"), {"u": uid, "s": sym})
        memos = [
            (A, "note", True, None), (A, "note", False, None),          # A: 일반 2 (AI 1)
            (A, "note", True, "now"),                                    #    휴지통 AI 메모 → 둘 다 제외
            (A, "checklist", False, None),                               #    체크리스트 → 제외
            (B, "note", True, None),                                     # B: 일반 1 (AI 1)
        ]                                                                # C: 0
        for sym, kind, ai, deleted in memos:
            c.execute(text(f"""INSERT INTO memos (user_id, symbol, kind, content, ai_linked, deleted_at)
                VALUES (:u, :s, CAST(:k AS memo_kind), 'x', :ai, {'now()' if deleted else 'NULL'})"""),
                      {"u": uid, "s": sym, "k": kind, "ai": ai})
    with Session(db_engine) as s:
        rows = {r["code"]: r for r in StockRepository(s).list_user_stocks(uid)}
        assert (rows[A]["memo_count"], rows[A]["ai_count"]) == (2, 1)
        assert (rows[B]["memo_count"], rows[B]["ai_count"]) == (1, 1)
        assert (rows[C]["memo_count"], rows[C]["ai_count"]) == (0, 0)
        assert sum(r["ai_count"] for r in rows.values()) == ai_stats(s, uid)["linked_memos"]
        one = StockRepository(s).get_user_stock(uid, A)
        assert (one["memo_count"], one["ai_count"]) == (2, 1)
