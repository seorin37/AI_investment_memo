"""로더 테스트. DB 테스트는 연결이 안 되면 skip하고, 모든 쓰기는 바깥 트랜잭션 롤백으로 되돌린다."""

import unittest

from sqlalchemy import text

from pipelines.disclosures import loader
from pipelines.disclosures.chunker import Chunk, sha256_text
from pipelines.disclosures.dart import ReportRef


TEST_SYMBOL = "005930"
# 실제 파이프라인 대상(2024~2026)과 겹치지 않는 기간을 써서 로컬 DB에 이미 적재된 공시와 충돌하지 않게 한다.
TEST_PERIOD = "2001-06-30"


def ref(rcept_no, title="반기보고서 (2001.06)", period_end=TEST_PERIOD, kind="half"):
    return ReportRef(TEST_SYMBOL, rcept_no, title, kind, period_end, "2001-08-14")


def chunks(rcept_no, texts):
    return [Chunk(rcept_no, i, "A > B", "text", t, len(t), sha256_text(t)) for i, t in enumerate(texts)]


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeConn:
    def __init__(self, alembic="0012_financials_sector_columns", vector="0.8.7", symbols=("005930",), column="vector(1024)", sparse="jsonb"):
        self.answers = [[alembic], vector, list(symbols), column, sparse]

    def execute(self, *args, **kwargs):
        return FakeResult(self.answers.pop(0))


class PreflightUnitTest(unittest.TestCase):
    def test_passes(self):
        loader.preflight(FakeConn(), ["005930"])

    def test_each_failure_stops(self):
        cases = [
            FakeConn(alembic="0004"),
            FakeConn(vector=None),
            FakeConn(symbols=()),
            FakeConn(column="vector(768)"),
        ]
        for conn in cases:
            with self.assertRaises(loader.PreflightError):
                loader.preflight(conn, ["005930"])


def _engine_or_none():
    try:
        from pipelines.common.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


ENGINE = _engine_or_none()


def tearDownModule():
    if ENGINE is not None:
        ENGINE.dispose()


@unittest.skipIf(ENGINE is None, "로컬 DB(DATABASE_URL)에 연결할 수 없어 건너뜀")
class LoaderDbTest(unittest.TestCase):
    def setUp(self):
        self.conn = ENGINE.connect()
        self.outer = self.conn.begin()
        self.conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))

    def tearDown(self):
        self.outer.rollback()
        self.conn.close()

    def count(self, sql, **params):
        return self.conn.execute(text(sql), params).scalar()

    def test_preflight_real_db(self):
        loader.preflight(self.conn, ["005930", "000660", "035420", "105560"])
        with self.assertRaises(loader.PreflightError):
            loader.preflight(self.conn, ["999999"])

    def test_upsert_and_amendment_replacement(self):
        self.assertEqual(loader.upsert_disclosure(self.conn, ref("T0000000000001")), [])
        loader.load_chunks(self.conn, "T0000000000001", chunks("T0000000000001", ["가", "나"]))
        replaced = loader.upsert_disclosure(self.conn, ref("T0000000000002", title="[기재정정]반기보고서 (2001.06)"))
        self.assertEqual(replaced, ["T0000000000001"])
        self.assertEqual(self.count("SELECT count(*) FROM disclosures WHERE rcept_no = 'T0000000000001'"), 0)
        self.assertEqual(self.count("SELECT count(*) FROM disclosure_chunks WHERE rcept_no = 'T0000000000001'"), 0)
        row = self.conn.execute(text("SELECT title, kind::text, period_end::text, source_url FROM disclosures WHERE rcept_no = 'T0000000000002'")).one()
        self.assertEqual(tuple(row), ("[기재정정]반기보고서 (2001.06)", "half", "2001-06-30", "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=T0000000000002"))

    def test_quarterly_q1_and_q3_coexist(self):
        loader.upsert_disclosure(self.conn, ref("T0000000000011", "분기보고서 (2001.03)", "2001-03-31", "quarterly"))
        self.assertEqual(loader.upsert_disclosure(self.conn, ref("T0000000000012", "분기보고서 (2001.09)", "2001-09-30", "quarterly")), [])

    def test_referenced_old_disclosure_blocks_replacement(self):
        loader.upsert_disclosure(self.conn, ref("T0000000000021"))
        self.conn.execute(
            text("INSERT INTO tracking_matches (tracking_item_id, disclosure_rcept_no, similarity) VALUES (-1, 'T0000000000021', 0.5)")
        )
        with self.assertRaises(loader.ReferencedDisclosureError):
            loader.upsert_disclosure(self.conn, ref("T0000000000022"))
        self.assertEqual(self.count("SELECT count(*) FROM disclosures WHERE rcept_no = 'T0000000000021'"), 1)
        self.assertEqual(self.count("SELECT count(*) FROM disclosures WHERE rcept_no = 'T0000000000022'"), 0)

    def test_load_chunks_skip_on_same_fingerprint(self):
        loader.upsert_disclosure(self.conn, ref("T0000000000031"))
        self.assertTrue(loader.load_chunks(self.conn, "T0000000000031", chunks("T0000000000031", ["가", "나"])))
        self.conn.execute(text("UPDATE disclosure_chunks SET dense_embedding = array_fill(0.03125, ARRAY[1024])::vector, sparse_embedding='{}'::jsonb, embedding_model='m', embedding_revision='r', embedding_config_hash='h', embedded_at=now() WHERE rcept_no = 'T0000000000031'"))
        self.assertFalse(loader.load_chunks(self.conn, "T0000000000031", chunks("T0000000000031", ["가", "나"])))
        self.assertEqual(self.count("SELECT count(*) FROM disclosure_chunks WHERE rcept_no = 'T0000000000031' AND dense_embedding IS NOT NULL"), 2)
        self.assertTrue(loader.load_chunks(self.conn, "T0000000000031", chunks("T0000000000031", ["가", "다", "라"])))
        self.assertEqual(
            self.conn.execute(text("SELECT array_agg(chunk_index ORDER BY chunk_index) FROM disclosure_chunks WHERE rcept_no = 'T0000000000031' AND dense_embedding IS NULL")).scalar(),
            [0, 1, 2],
        )

    def test_update_corp_codes_never_inserts(self):
        before = self.count("SELECT count(*) FROM stocks")
        loader.update_corp_codes(self.conn, {"005930": "00126380", "999999": "00000000"})
        self.assertEqual(self.count("SELECT count(*) FROM stocks"), before)
        self.assertEqual(self.count("SELECT dart_corp_code FROM stocks WHERE symbol = '005930'"), "00126380")


if __name__ == "__main__":
    unittest.main()
