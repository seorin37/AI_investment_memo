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
        self.prev_match, self.has_price = None, False

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "FROM tracking_matches" in sql and sql.lstrip().startswith("SELECT"):
            return Cur(self.prev_match)
        if sql.lstrip().startswith("INSERT INTO tracking_matches"):
            return Cur((500 + params["news"],))
        if "SELECT EXISTS" in sql:
            return Cur((self.has_price,))
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
        w = DbCardWriter(conn, "run_1")
        n = w.write_matches(ITEM, {"news:1": (True, "ON_TOPIC_EVENT"), "news:2": (False, "OFF_TOPIC")},
                            {"news:1": 0.71, "news:2": 0.6})
        self.assertEqual(n, 2)
        ups = [c for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_matches")]
        self.assertEqual([(p["news"], p["decision"], p["sim"]) for _, p in ups], [(1, "relevant", 0.71), (2, "irrelevant", 0.6)])
        self.assertIn("ON CONFLICT (tracking_item_id, news_id) DO UPDATE", ups[0][0])
        self.assertEqual(w.manifest["tracking_matches_inserted"], [501, 502])   # 정리 스크립트가 지울 행
        conn2 = Conn()
        conn2.prev_match = (7, 0.5, "pending", None)
        w2 = DbCardWriter(conn2, "run_2")
        w2.write_matches(ITEM, {"news:1": (True, "")}, {"news:1": 0.7})
        self.assertEqual(w2.manifest["tracking_matches_updated"],
                         [{"id": 501, "similarity": 0.5, "decision": "pending", "decided_at": None}])   # 되돌릴 값

    def test_run_id_and_manifest(self):
        conn = Conn()
        w = DbCardWriter(conn, "run_20261111_160000")
        d = UpdateDraft(ITEM, "news", "t", "s", "r", [("news:9", "q")])
        w.write(ITEM, d, {"headline": "t"})
        p = next(c[1] for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_updates"))
        self.assertEqual(json.loads(p["details"])["run_id"], "run_20261111_160000")
        self.assertEqual((w.manifest["run_id"], w.manifest["target"], w.manifest["tracking_updates"]),
                         ("run_20261111_160000", "127.0.0.1:5433/memos_test", [100]))

    def test_has_price_card(self):
        conn = Conn()
        self.assertFalse(DbCardWriter(conn).has_price_card(PRICE_ITEM))
        conn.has_price = True
        self.assertTrue(DbCardWriter(conn).has_price_card(PRICE_ITEM))
        sql, p = conn.calls[-1]
        self.assertEqual((p["item"], p["rev"]), (43, 9))                       # 최신 항목 버전 기준


class FirstPriceTest(unittest.TestCase):
    def test_first_time_card_even_if_already_reached(self):
        from datetime import date

        from pipelines.updates.price import price_outcome
        item = TrackingItem("2", "000660", "price_above", "40만 원 위로", price_threshold=400000)
        rows = [(date(2026, 11, 10), 1212000), (date(2026, 11, 9), 1150000)]     # 전날에도 이미 도달
        dates = [date(2026, 11, 10), date(2026, 11, 9)]
        self.assertEqual(price_outcome(item, rows, dates)[0], "price_no_card")
        kind, draft, _ = price_outcome(item, rows, dates, first_time=True)
        self.assertEqual((kind, draft.price_state), ("price_card", "reached"))
        far = TrackingItem("5", "005930", "price_below", "7만 원 아래로", price_threshold=70000)
        self.assertEqual(price_outcome(far, [(date(2026, 11, 10), 198900)], dates, first_time=True)[0], "price_no_card")


class MarksCheckedTest(unittest.TestCase):
    def test_only_saved_cards_and_normal_no_new(self):
        from pipelines.updates.response import marks_checked
        r = lambda t, reason="", iid="1": Response(t, "item", item_id=iid, reason=reason)
        for ok in (r("update_card", "card"), r("price_card"), r("no_data", "stale_price"), r("no_new_info", "no_candidates"),
                   r("no_new_info", "llm_no_update"), r("no_new_info", "no_relevant_candidates"),
                   r("no_new_info", "merged_into:7")):
            self.assertTrue(marks_checked(ok), ok)
        for bad in (r("no_new_info", "call_failed"), r("no_new_info", "check_failed"), r("no_new_info", "verify_failed"),
                    r("no_new_info", "relevance_failed"), r("no_new_info", "not_called"),
                    Response("out_of_scope", "memo", memo_id="M1")):
            self.assertFalse(marks_checked(bad), bad)
        self.assertFalse(marks_checked(r("update_card", "card", "9"), {"9"}))   # 카드 저장이 실패한 항목


class CleanupTest(unittest.TestCase):
    def test_plan_and_execute_sql(self):
        from pipelines.updates.db_cleanup import execute, plan

        class C(Conn):
            def execute(self, sql, params=None):
                self.calls.append((sql, params))
                return Cur((3,))
        m = {"run_id": "run_x", "target": "127.0.0.1:5433/memos_test", "tracking_updates": [1, 2],
             "tracking_matches_inserted": [5], "tracking_matches_updated": [{"id": 6, "similarity": 0.5,
                                                                              "decision": "pending", "decided_at": None}],
             "last_checked": [{"item_id": 1, "prev": None, "set": "2026-11-11T15:00:00+09:00"}]}
        conn = C()
        counts = plan(conn, m)
        self.assertEqual(counts["tracking_matches 되돌림"], 1)
        execute(conn, m)
        sqls = [c[0] for c in conn.calls[-4:]]
        self.assertTrue(sqls[0].startswith("DELETE FROM tracking_updates") and "details->>'run_id'" in sqls[0])
        self.assertTrue(sqls[1].startswith("DELETE FROM tracking_matches"))
        self.assertTrue(sqls[3].startswith("UPDATE tracking_items") and "last_checked_at = %(set)s" in sqls[3])


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


class LoadItemsMemoTextTest(unittest.TestCase):
    """2026-11-18: 매일 업데이트 판정에 넣는 메모 문장 = 제목 + 본문 (메모 분석과 같은 memo_full_text)."""

    class ItemsConn:
        def __init__(self, rows):
            self.rows, self.sql = rows, ""

        def execute(self, sql, params=None):
            self.sql = sql
            return Cur(rows=self.rows)

    def load(self, title, content):
        from pipelines.updates.db_store import load_items
        conn = self.ItemsConn([(42, "005930", "topic", "HBM 소식", "HBM, 실적", None, content, title)])
        items = load_items(conn, ("005930",))
        self.assertIn("m.title", conn.sql)
        return items[0]

    def test_one_line_memo_uses_title_not_none(self):
        from pipelines.updates.judge import build_prompt
        item = self.load("HBM 공급 소식 나오면 다시 보기", "")                    # 웹 한 줄 메모: 본문 빈 값
        self.assertEqual(item.memo_text, "HBM 공급 소식 나오면 다시 보기")
        prompt = build_prompt(item, [], guide="지침")
        self.assertIn("HBM 공급 소식 나오면 다시 보기", prompt)                   # 판정 프롬프트의 메모 문장이 '없음'이 아니라 제목
        from dataclasses import replace
        before = build_prompt(replace(item, memo_text=""), [], guide="지침")      # 이전 동작(본문만 → 빈 값)이면 메모 문장 자리가 '없음'
        self.assertEqual(before.count("없음") - prompt.count("없음"), 1)

    def test_title_and_body_rules(self):
        self.assertEqual(self.load("7만원 밑이면", "HBM 소식").memo_text, "7만원 밑이면\nHBM 소식")
        self.assertEqual(self.load("제목 없음", "HBM 소식").memo_text, "HBM 소식")
        self.assertEqual(self.load(None, "HBM 소식").memo_text, "HBM 소식")
        self.assertEqual(self.load("HBM 소식", "HBM 소식\n7만원 밑이면").memo_text, "HBM 소식\n7만원 밑이면")
        self.assertEqual(self.load("HBM 소식 나오면 실적 발표 전에 다시 확인하…", "HBM 소식 나오면 실적 발표 전에 다시 확인하기").memo_text,
                         "HBM 소식 나오면 실적 발표 전에 다시 확인하기")
        self.assertEqual(self.load("", "").memo_text, "")


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


class AskAnswerTest(unittest.TestCase):
    """질문(0019 type=ask): 답은 tracking_updates.type='answer', 답하면(합친 카드 포함) 질문 항목을 닫는다."""

    ASK = TrackingItem("50", "005930", "topic", "3분기 영업이익률 얼마인지", category="ask")

    def test_load_items_maps_ask_to_one_time_topic(self):
        from pipelines.updates.db_store import load_items
        conn = LoadItemsMemoTextTest.ItemsConn([(50, "005930", "ask", "영업이익률 얼마인지", None, None, "얼마야?", "실적")])
        item = load_items(conn, ("005930",))[0]
        self.assertEqual((item.type, item.category), ("topic", "ask"))

    def test_answer_card_and_close_merged_asks(self):
        conn = Conn()
        w = DbCardWriter(conn)
        d = UpdateDraft(self.ASK, "disclosure", "영업이익률 55%", "사실.", "연결", [("disc:R1#0", "사실")], card_schema="v2",
                        merged_items=[{"item_id": "51"}])
        w.write(self.ASK, d, {"headline": "영업이익률 55%"})
        _, p = next(c for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_updates"))
        self.assertEqual(p["type"], "answer")
        self.assertEqual(json.loads(p["details"])["answer_status"], "answer")
        sql, p = next(c for c in conn.calls if c[0].lstrip().startswith("UPDATE tracking_items SET status = 'done'"))
        self.assertIn("type = 'ask'", sql)                                  # 주제 항목은 닫지 않는다
        self.assertEqual(p["ids"], [50, 51])

    def test_topic_card_still_closes_merged_ask(self):
        conn = Conn()
        d = UpdateDraft(ITEM, "disclosure", "실적", "사실.", "연결", [("disc:R1#0", "사실")], card_schema="v2",
                        merged_items=[{"item_id": "51"}])
        DbCardWriter(conn).write(ITEM, d, {})
        _, p = next(c for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_updates"))
        self.assertEqual(p["type"], "disclosure")
        _, p = next(c for c in conn.calls if c[0].lstrip().startswith("UPDATE tracking_items SET status = 'done'"))
        self.assertEqual(p["ids"], [42, 51])

    def test_no_answer_is_saved_and_closes(self):
        from pipelines.updates.response import ASK_NO_ANSWER, ASK_NO_ANSWER_TEXT
        conn = Conn()
        w = DbCardWriter(conn)
        w.write_no_answer(self.ASK, Response(ASK_NO_ANSWER, "item", item_id="50", reason="no_candidates",
                                             message=ASK_NO_ANSWER_TEXT))
        _, p = next(c for c in conn.calls if c[0].lstrip().startswith("INSERT INTO tracking_updates"))
        self.assertEqual((p["type"], p["summary"]), ("answer", ASK_NO_ANSWER_TEXT))
        self.assertEqual(json.loads(p["details"])["answer_status"], "no_answer")
        self.assertEqual(w.written["no_answer"], 1)
