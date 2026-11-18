"""수시공시 저장 테스트 — 테스트 DB(.env.test의 TEST_DATABASE_URL)에서만 돈다.

테스트 DB가 없거나 0014 이전이면 건너뛴다. 중앙 DB(DATABASE_URL)는 쓰지 않는다.
접수번호는 'E9'로 시작하는 가짜 번호라 실제 공시와 겹치지 않고, 끝나면 지운다.
"""

import json
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from app.dart_reports import DartRateLimitError
from pipelines.common.config import REPO_ROOT, load_config
from pipelines.disclosures import events_loader
from pipelines.disclosures.events_fields import EventFieldRules, extract_fields
from pipelines.disclosures.events_list import EventRef
from pipelines.disclosures.events_parse import PARSER_VERSION, parse_event_zip
from pipelines.disclosures.run_events import collect_events


FIXTURES = Path(__file__).parent / "fixtures" / "events"
RULES = EventFieldRules.from_config(load_config(REPO_ROOT / "configs" / "disclosure_events.yaml"))
SYMBOL = "005930"  # 테스트 DB stocks에 있는 종목


def _test_engine():
    try:
        from dotenv import dotenv_values

        url = dotenv_values(REPO_ROOT / ".env.test").get("TEST_DATABASE_URL")
        if not url:
            return None
        engine = create_engine(url)
        with engine.connect() as conn:
            if conn.execute(text("SELECT to_regclass('public.disclosure_events')")).scalar() is None:
                return None
        return engine
    except Exception:
        return None


ENGINE = _test_engine()


def ref(rcept_no, title="현금ㆍ현물배당결정", event_type="dividend", topic="shareholder_return", symbol=SYMBOL,
        rcept_dt="2001-10-22", correction=False, base_title=None):
    return EventRef(
        rcept_no=rcept_no, symbol=symbol, corp_code="00126380", corp_name="테스트", title=title,
        base_title=base_title or title.replace("[기재정정]", ""), rcept_dt=rcept_dt, pblntf_ty="I", kind="other",
        event_type=event_type, topic=topic, is_correction=correction, is_subsidiary=False,
    )


def parsed(name, event_type):
    event = parse_event_zip(FIXTURES / f"{name}.zip", name.split("_")[1])
    return event, extract_fields(event_type, event.pairs, RULES)


@unittest.skipIf(ENGINE is None, "테스트 DB(TEST_DATABASE_URL)가 없거나 0014 이전이라 건너뜀")
class EventsLoaderDbTest(unittest.TestCase):
    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        with ENGINE.begin() as conn:
            conn.execute(text("DELETE FROM disclosure_chunks WHERE rcept_no LIKE 'E9%'"))
            conn.execute(text("DELETE FROM disclosure_events WHERE rcept_no LIKE 'E9%'"))
            conn.execute(text("DELETE FROM disclosures WHERE rcept_no LIKE 'E9%'"))

    def one(self, sql, **params):
        with ENGINE.connect() as conn:
            return conn.execute(text(sql), params).one()

    def test_upsert_event_writes_three_tables(self):
        event, result = parsed("033920_20261022800228", "dividend")
        with ENGINE.begin() as conn:
            outcome = events_loader.upsert_event(conn, ref("E9000000000001"), event, result)
        self.assertEqual(outcome, {"corrects": None, "chunks_loaded": True})
        row = self.one("SELECT kind::text, period_end, rcept_dt::text FROM disclosures WHERE rcept_no = 'E9000000000001'")
        self.assertEqual(tuple(row), ("other", None, "2001-10-22"))
        ev = self.one("SELECT event_type, topic, parse_status, fields, jsonb_array_length(pairs), parser_version, doc_format"
                      " FROM disclosure_events WHERE rcept_no = 'E9000000000001'")
        self.assertEqual((ev[0], ev[1], ev[2], ev[5], ev[6]), ("dividend", "shareholder_return", "ok", PARSER_VERSION, "html"))
        self.assertEqual((ev[3]["dps_common"], ev[3]["yield_common"], ev[3]["record_date"]), (160, 2.14, "2026-09-30"))
        self.assertEqual(ev[4], len(event.pairs))
        chunk = self.one("SELECT count(*), bool_and(section IS NULL), bool_and(dense_embedding IS NULL), min(chunk_text)"
                         " FROM disclosure_chunks WHERE rcept_no = 'E9000000000001'")
        self.assertEqual(tuple(chunk[:3]), (1, True, True))
        self.assertTrue(chunk[3].startswith("[테스트 2001-10-22 수시공시 | 현금ㆍ현물배당결정]\n"))
        self.assertIn("3. 1주당 배당금(원) > 보통주식: 160", chunk[3])
        self.assertNotIn(": -\n", chunk[3])  # 빈 값 줄은 뺀다

        # 다시 저장해도 행이 늘지 않고, 청크가 같으면 다시 쓰지 않는다
        with ENGINE.begin() as conn:
            again = events_loader.upsert_event(conn, ref("E9000000000001"), event, result)
        self.assertFalse(again["chunks_loaded"])
        self.assertEqual(self.one("SELECT count(*) FROM disclosure_events WHERE rcept_no LIKE 'E9%'")[0], 1)

    def test_correction_links_to_original_on_original_date(self):
        event, result = parsed("033920_20261022800228", "dividend")
        with ENGINE.begin() as conn:
            events_loader.upsert_event(conn, ref("E9000000000010", rcept_dt="2001-10-12"), event, result)
            events_loader.upsert_event(conn, ref("E9000000000011", rcept_dt="2001-10-12"), event, result)  # 같은 날 두 번째
            events_loader.upsert_event(conn, ref("E9000000000012", rcept_dt="2001-10-20"), event, result)  # 다른 날
        result.correction = {"date": "2001-10-26", "original_date": "2001-10-12", "reason": "오기 정정"}
        fix = ref("E9000000000020", title="[기재정정]현금ㆍ현물배당결정", rcept_dt="2001-10-26", correction=True)
        with ENGINE.begin() as conn:
            outcome = events_loader.upsert_event(conn, fix, event, result)
        self.assertEqual(outcome["corrects"], "E9000000000011")  # 원래 제출일 공시 중 가장 최근
        row = self.one("SELECT corrects, is_correction, correction FROM disclosure_events WHERE rcept_no = 'E9000000000020'")
        self.assertEqual((row[0], row[1], row[2]["reason"]), ("E9000000000011", True, "오기 정정"))
        # 원본은 지우지 않는다
        self.assertEqual(self.one("SELECT count(*) FROM disclosures WHERE rcept_no LIKE 'E90000000000_%'")[0], 4)

    def test_correction_without_original_in_db_is_not_guessed(self):
        event, result = parsed("033920_20261022800228", "dividend")
        with ENGINE.begin() as conn:
            events_loader.upsert_event(conn, ref("E9000000000030", rcept_dt="2001-10-20"), event, result)
        result.correction = {"original_date": "2001-09-01"}
        fix = ref("E9000000000031", title="[기재정정]현금ㆍ현물배당결정", correction=True)
        with ENGINE.begin() as conn:
            self.assertIsNone(events_loader.upsert_event(conn, fix, event, result)["corrects"])

    def test_failed_parse_keeps_listing_and_is_retried(self):
        with ENGINE.begin() as conn:
            events_loader.upsert_event(conn, ref("E9000000000040"), None, None, parse_error="DartDownloadError: 014")
        row = self.one("SELECT parse_status, parse_issues, fields, pairs FROM disclosure_events WHERE rcept_no = 'E9000000000040'")
        self.assertEqual(tuple(row), ("failed", ["DartDownloadError: 014"], {}, []))
        self.assertEqual(self.one("SELECT count(*) FROM disclosure_chunks WHERE rcept_no = 'E9000000000040'")[0], 0)
        with ENGINE.connect() as conn:
            self.assertEqual(events_loader.done_rcept_nos(conn, ["E9000000000040"]), set())  # 실패는 다시 시도 대상

    def test_non_date_original_date_is_not_guessed(self):
        event, result = parsed("033920_20261022800228", "dividend")
        with ENGINE.begin() as conn:
            events_loader.upsert_event(conn, ref("E9000000000035", rcept_dt="2001-10-20"), event, result)
            fix = ref("E9000000000036", title="[기재정정]현금ㆍ현물배당결정", correction=True)
            self.assertIsNone(events_loader.find_original(conn, fix, "타법인 주식 처분결정"))

    def test_collect_events_continues_after_store_error(self):
        fixture = FIXTURES / "051600_20261021800137.zip"
        refs = [ref(f"E900000000008{i}", "단일판매ㆍ공급계약체결", "supply_contract", "business") for i in range(3)]
        original = events_loader.upsert_event

        def flaky_upsert(conn, r, *args, **kwargs):
            if r.rcept_no == "E9000000000081":
                raise ValueError("깨진 값")
            return original(conn, r, *args, **kwargs)

        from pipelines.disclosures import run_events

        run_events.upsert_event = flaky_upsert
        try:
            summary = collect_events(ENGINE, refs, "key", Path("."), RULES, download=lambda *a: fixture)
        finally:
            run_events.upsert_event = original
        self.assertEqual(summary.loaded, ["E9000000000080", "E9000000000082"])
        self.assertEqual([f["rcept_no"] for f in summary.failures], ["E9000000000081"])
        self.assertIn("저장 실패 ValueError", summary.failures[0]["error"])
        self.assertFalse(summary.stopped_on_errors)
        # 실패한 건은 아무것도 남지 않는다(그 건의 트랜잭션만 되돌림)
        self.assertEqual(self.one("SELECT count(*) FROM disclosures WHERE rcept_no = 'E9000000000081'")[0], 0)

    def test_topic_check_constraint(self):
        from sqlalchemy.exc import IntegrityError

        event, result = parsed("033920_20261022800228", "dividend")
        with self.assertRaises(IntegrityError), ENGINE.begin() as conn:
            events_loader.upsert_event(conn, ref("E9000000000050", topic="weather"), event, result)

    def test_collect_events_skips_unknown_and_done_and_stops_on_rate_limit(self):
        fixture = FIXTURES / "051600_20261021800137.zip"  # 공급계약
        calls = []

        def fake_download(r, api_key, docs_dir, session):
            calls.append(r.rcept_no)
            if r.rcept_no == "E9000000000063":
                raise DartRateLimitError("020")
            return fixture

        refs = [
            ref("E9000000000060", "단일판매ㆍ공급계약체결", "supply_contract", "business"),
            ref("E9000000000061", "단일판매ㆍ공급계약체결", "supply_contract", "business", symbol="999999"),
            ref("E9000000000063", "단일판매ㆍ공급계약체결", "supply_contract", "business"),
            ref("E9000000000064", "단일판매ㆍ공급계약체결", "supply_contract", "business"),
        ]
        summary = collect_events(ENGINE, refs, "key", Path("."), RULES, download=fake_download)
        self.assertEqual(summary.loaded, ["E9000000000060"])
        self.assertEqual(dict(summary.status), {"ok": 1})
        self.assertEqual(dict(summary.skipped_unknown_symbol), {"999999": 1})
        self.assertTrue(summary.rate_limited)
        self.assertEqual(calls, ["E9000000000060", "E9000000000063"])  # 한도에 걸린 뒤로는 받지 않는다
        amount = self.one("SELECT fields->>'contract_amount' FROM disclosure_events WHERE rcept_no = 'E9000000000060'")[0]
        self.assertEqual(json.loads(amount), 83_613_252_000)

        # 다시 실행하면 이미 저장한 것은 건너뛴다
        calls.clear()
        again = collect_events(ENGINE, refs[:1], "key", Path("."), RULES, download=fake_download)
        self.assertEqual((again.loaded, again.skipped_done, calls), ([], 1, []))


class EventChunksTest(unittest.TestCase):
    def test_long_documents_are_split_under_limit(self):
        event, _ = parsed("010120_20261021800151", "prelim_earnings")
        event.pairs = event.pairs * 20  # 일부러 길게
        chunks = events_loader.event_chunks(ref("E9000000000070"), event)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.chunk_text) <= events_loader.CHUNK_MAX_CHARS for c in chunks))
        self.assertTrue(all(c.chunk_text.startswith("[테스트 ") for c in chunks))
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))


if __name__ == "__main__":
    unittest.main()
