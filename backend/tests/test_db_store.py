"""카드 DB 저장 (2026-11-11). 실제 DB 없이 가짜 연결로 SQL과 값만 본다. 실제 쓰기 검증은 로컬 테스트 DB에서 따로."""

import json
import unittest
from datetime import datetime, timezone

from pipelines.updates.db_store import (DbCardWriter, DbItemStateStore, DbUsedRefStore, NotTestDatabase,
                                        check_test_target, refs_from_rows, source_rows)
from pipelines.updates.models import Response, TrackingItem, UpdateDraft

ITEM = TrackingItem("42", "005930", "topic", "HBM 소식", memo_text="HBM 소식 알려줘")
PRICE_ITEM = TrackingItem("43", "005930", "price_below", "7만원 아래", price_threshold=70000)


class Cur:
    def __init__(self, row=None, rows=()):
        self.row, self.rows = row, list(rows)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Conn:
    """execute 호출을 적어 두고, SQL 앞부분으로 돌려줄 값을 고른다."""

    def __init__(self, revisions=(7, 9), returning=(100,), used_rows=(), last_checked=None):
        from types import SimpleNamespace
        self.info = SimpleNamespace(host="127.0.0.1", port=5433, dbname="memos_test")   # 쓰기 클래스는 테스트 DB 연결만 받는다
        self.calls, self.revisions, self.returning = [], revisions, returning
        self.used_rows, self.last_checked = used_rows, last_checked

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "memo_revisions" in sql and "tracking_item_revisions" in sql:
            return Cur(self.revisions)
        if sql.lstrip().startswith("INSERT INTO tracking_updates"):
            return Cur(self.returning)
        if "FROM update_sources" in sql:
            return Cur(rows=self.used_rows)
        if "SELECT last_checked_at" in sql:
            return Cur((self.last_checked,) if self.last_checked else None)
        return Cur()


class GuardTest(unittest.TestCase):
    def test_only_local_test_db(self):
        self.assertEqual(check_test_target("postgresql://u:p@127.0.0.1:5433/memos_test"), "127.0.0.1:5433/memos_test")
        self.assertEqual(check_test_target("postgresql+psycopg://u:p@localhost:5433/test_memos"), "localhost:5433/test_memos")
        for bad in ("postgresql://u:p@192.168.0.105:15432/memos", "postgresql://u:p@127.0.0.1:5432/memos_test",
                    "postgresql://u:p@127.0.0.1:5433/memos"):
            with self.assertRaises(NotTestDatabase):
                check_test_target(bad)


class SourcesTest(unittest.TestCase):
    def draft(self, sources, **kw):
        return UpdateDraft(ITEM, "disclosure", "제목", "문장 하나. 문장 둘.", "메모 연결", sources, card_schema="v2", **kw)

    def test_source_rows_merge_disclosure_chunks(self):
        rows = source_rows(self.draft([("disc:R1#3", "배당 결정"), ("disc:R1#5", "기준일"), ("news:9", "기사 사실"),
                                       ("cmp:R1", "작년 값")]))
        self.assertEqual(rows, [{"news": 9, "rcept": None, "quote": "기사 사실"},
                                {"news": None, "rcept": "R1", "quote": "[청크 3,5] 배당 결정 기준일"}])

    def test_refs_round_trip(self):
        refs = refs_from_rows([(9, None, "기사"), (None, "R1", "[청크 3,5] 배당"), (None, "R2", "청크 번호 없음")])
        self.assertEqual(refs, {"news:9", "disc:R1#3", "disc:R1#5", "disc:R2"})
        store = DbUsedRefStore(Conn(used_rows=[(9, None, "x")]))
        self.assertEqual(store.used("42"), {"news:9"})
        store.record("42", ["news:1"])                                   # DB 구현은 카드 기록이 곧 쓴 근거 기록이다


class WriterTest(unittest.TestCase):
    def test_update_card(self):
        conn = Conn()
        w = DbCardWriter(conn)
        d = UpdateDraft(ITEM, "disclosure", "HBM 공급 계약", "사실 하나. 사실 둘.", "메모 연결", [("disc:R1#0", "사실 하나"),
                        ("news:9", "사실 둘")], card_schema="v2", coverage="10월 28일 이후 기사 기준")
        card = {"headline": "HBM 공급 계약", "coverage": "10월 28일 이후 기사 기준"}
        self.assertEqual(w.write(ITEM, d, card), 100)
        sql, p = next(c for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_updates"))
        self.assertEqual((p["item"], p["type"], p["memo_rev"], p["track_rev"]), (42, "disclosure", 7, 9))
        self.assertEqual(json.loads(p["details"])["coverage"], "10월 28일 이후 기사 기준")
        srcs = [c[1] for c in conn.calls if c[0].lstrip().startswith("INSERT INTO update_sources")]
        self.assertEqual([(s["news"], s["rcept"]) for s in srcs], [(9, None), (None, "R1")])
        self.assertEqual(w.written["update_card"], 1)
        news_only = UpdateDraft(ITEM, "news", "t", "s", "r", [("news:9", "q")])
        w.write(ITEM, news_only, {})
        self.assertEqual(conn.calls[-2][1]["type"], "news")

    def test_price_card(self):
        conn = Conn()
        w = DbCardWriter(conn)
        d = UpdateDraft(PRICE_ITEM, "price_condition", "조건가에 가까워졌어요", "s", "r", price_state="near",
                        details={"close": 71000.0}, observed_trade_date="2026-11-10", origin="fixed")
        self.assertEqual(w.write(PRICE_ITEM, d, {}), 100)
        sql, p = conn.calls[-1]
        self.assertIn("ON CONFLICT (tracking_item_id, tracking_revision_id, observed_trade_date)", sql)
        self.assertEqual((p["state"], p["value"], p["trade_date"], p["track_rev"]), ("near", 71000.0, "2026-11-10", 9))
        self.assertFalse(any("update_sources" in c[0] or "price_events" in c[0] for c in conn.calls))   # 0005 트리거가 막는다
        dup = DbCardWriter(Conn(returning=None))                         # 같은 거래일 두 번째: 행 없음
        self.assertIsNone(dup.write(PRICE_ITEM, d, {}))
        self.assertEqual(dup.written["price_duplicate"], 1)
        with self.assertRaises(ValueError):
            DbCardWriter(Conn(revisions=(7, None))).write(PRICE_ITEM, d, {})

    def test_matches(self):
        conn = Conn()
        n = DbCardWriter(conn).write_matches(ITEM, {"news:1": (True, "ON_TOPIC_EVENT"), "news:2": (False, "OFF_TOPIC")},
                                             {"news:1": 0.71, "news:2": 0.6})
        self.assertEqual(n, 2)
        self.assertEqual([(p["news"], p["decision"], p["sim"]) for _, p in conn.calls],
                         [(1, "relevant", 0.71), (2, "irrelevant", 0.6)])
        self.assertIn("ON CONFLICT (tracking_item_id, news_id) DO UPDATE", conn.calls[0][0])


class StateTest(unittest.TestCase):
    def test_last_checked(self):
        ts = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
        store = DbItemStateStore(Conn(last_checked=ts))
        self.assertEqual(store.get("42"), {"last_checked_at": ts.isoformat()})
        self.assertIsNone(DbItemStateStore(Conn()).get("42"))
        conn = Conn()
        s = DbItemStateStore(conn)
        s.record(Response("no_new_info", "item", item_id="42", checked_at="2026-11-11T13:00:00+09:00"))
        s.record(Response("no_data", "item", item_id="43", reason="stale_price", checked_at="2026-11-11T13:00:00+09:00"))
        s.record(Response("out_of_scope", "memo", memo_id="M1"))         # 항목 응답이 아니면 쓰지 않는다
        self.assertEqual([p["item"] for _, p in conn.calls], [42, 43])
        self.assertTrue(all(c[0].startswith("UPDATE tracking_items SET last_checked_at") for c in conn.calls))


class MemoAnalysisTest(unittest.TestCase):
    def test_returns_only_confirmations_and_memo_scope(self):
        from types import SimpleNamespace

        from pipelines.updates.response import memo_analysis_responses
        j = lambda i, dec, code=None: SimpleNamespace(sentence_index=i, decision=dec, reason_code=code, category="B2",
                                                       text=f"문장 {i}", cleaned_text=f"문장 {i}")
        out = memo_analysis_responses("M1", [j(0, "full_fallback"), j(1, "needs_confirmation", "UNSUPPORTED_CONDITION")], 0)
        self.assertEqual([r.type for r in out], ["needs_confirmation"])     # 확인 질문이 있으면 메모 단위 범위 밖은 없다
        none = memo_analysis_responses("M2", [j(0, "full_fallback")], 0)
        self.assertEqual([(r.type, r.scope) for r in none], [("out_of_scope", "memo")])
        self.assertEqual(memo_analysis_responses("M3", [j(0, "normal")], 1), [])


if __name__ == "__main__":
    unittest.main()
