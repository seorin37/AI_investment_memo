"""run_events main() 다시 실행 테스트 — 멈췄거나 --no-embed로 돌린 뒤 다시 실행하면 빠진 임베딩이 채워지는가.

2026-11-05 중앙 DB 수집에서 실제로 난 실수 두 가지를 다시 막는다.
- a968e35: 새로 저장한 공시가 0건이면 임베딩 단계를 아예 건너뛰었다.
- a968c27: 이번 실행에서 저장한 공시만 임베딩해서, 기간 안의 앞날 공시에 남은 빈 청크를 채우지 않았다.

main()을 그대로 돌리고 바깥 연결만 바꾼다: DART 목록·원문(fixture ZIP), 인코더(고정 벡터), DB(테스트 DB).
테스트 DB(.env.test의 TEST_DATABASE_URL)가 없거나 0014 이전이면 건너뛴다. 접수번호는 'E9'로 시작하는 가짜 번호다.
"""

import functools
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import yaml
from sqlalchemy import text

from pipelines.common import db as common_db
from pipelines.common.config import REPO_ROOT
from pipelines.disclosures import embedder, run_events
from pipelines.disclosures.embedder import EncodeStats, Encoded

from tests.test_disclosure_events_loader import ENGINE, FIXTURES, ref

DAY1, DAY2 = "2001-10-22", "2001-10-23"
REFS = [
    ref("E9000000000101", "단일판매ㆍ공급계약체결", "supply_contract", "business", rcept_dt=DAY1),
    ref("E9000000000102", "단일판매ㆍ공급계약체결", "supply_contract", "business", rcept_dt=DAY2),
]
FIXTURE = FIXTURES / "051600_20261021800137.zip"  # 공급계약


class FakeEncoder:
    """BGE-M3 대신 고정 벡터를 돌려준다. 몇 개를 임베딩했는지 센다."""

    batch_size = 8

    def __init__(self):
        self.encoded: list[str] = []

    def encode_documents(self, texts, sparse, on_batch, keep_results=False):
        self.encoded.extend(texts)
        dense = np.zeros(1024, dtype=np.float32)
        dense[0] = 1.0
        on_batch(list(range(len(texts))), [Encoded(dense=dense, sparse={"1": 0.5}) for _ in texts])
        return None, EncodeStats(items=len(texts))


def fake_fetch_day(api_key, day, list_config, raw_dir, *, session=None, use_cache=True):
    return [day]  # 목록 대신 날짜를 넘기고 select_events에서 그날 공시로 바꾼다


def fake_select_events(items, rules, kind_by_type, universe, report):
    return [r for r in REFS if r.rcept_dt == items[0].isoformat()], report


def fake_download(r, api_key, docs_dir, session):
    return FIXTURE


@unittest.skipIf(ENGINE is None, "테스트 DB(TEST_DATABASE_URL)가 없거나 0014 이전이라 건너뜀")
class RunEventsRerunTest(unittest.TestCase):
    def setUp(self):
        self.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        config = yaml.safe_load((REPO_ROOT / "configs" / "disclosure_events.yaml").read_text(encoding="utf-8"))
        config["paths"] = {"raw_dir": str(tmp / "raw"), "out_dir": str(tmp / "out")}  # 저장소 data/에 쓰지 않게
        self.config_path = tmp / "events.yaml"
        self.config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        self.universe = tmp / "no-universe.json"
        self.encoder = FakeEncoder()

        patches = [
            mock.patch.object(run_events, "get_api_key", return_value="test-key"),
            mock.patch.object(run_events, "fetch_day", fake_fetch_day),
            mock.patch.object(run_events, "select_events", fake_select_events),
            mock.patch.object(run_events, "collect_events",
                              functools.partial(run_events.collect_events, download=fake_download)),
            mock.patch.object(common_db, "get_engine", return_value=ENGINE),
            mock.patch.object(embedder, "load_encoder", return_value=(self.encoder, {})),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.cleanup()
        self.tmp.cleanup()

    def cleanup(self):
        with ENGINE.begin() as conn:
            conn.execute(text("DELETE FROM disclosure_chunks WHERE rcept_no LIKE 'E9%'"))
            conn.execute(text("DELETE FROM disclosure_events WHERE rcept_no LIKE 'E9%'"))
            conn.execute(text("DELETE FROM disclosures WHERE rcept_no LIKE 'E9%'"))

    def run_main(self, *args):
        argv = ["--config", str(self.config_path), "--universe", str(self.universe), *args]
        self.encoder.encoded.clear()
        return run_events.main(argv)

    def chunk_counts(self, rcept_no=None):
        """(전체 청크, 임베딩 빈 청크)"""
        where = "rcept_no = :r" if rcept_no else "rcept_no LIKE 'E9%'"
        with ENGINE.connect() as conn:
            return tuple(conn.execute(
                text(f"SELECT count(*), count(*) FILTER (WHERE dense_embedding IS NULL OR sparse_embedding IS NULL)"
                     f" FROM disclosure_chunks WHERE {where}"), {"r": rcept_no}).one())

    def test_rerun_without_new_disclosures_fills_missing_embeddings(self):
        # 1차: --no-embed → 청크만 저장
        self.assertEqual(self.run_main("--since", DAY1, "--until", DAY2, "--no-embed"), run_events.EXIT_OK)
        total, missing = self.chunk_counts()
        self.assertGreater(total, 0)
        self.assertEqual(missing, total)
        self.assertEqual(self.encoder.encoded, [])

        # 2차: 새로 저장할 공시가 0건이어도 빈 임베딩은 채운다 (a968e35)
        self.assertEqual(self.run_main("--since", DAY1, "--until", DAY2), run_events.EXIT_OK)
        self.assertEqual(self.chunk_counts(), (total, 0))
        self.assertEqual(len(self.encoder.encoded), total)

        # 3차: 이미 된 것은 다시 임베딩하지 않는다
        self.assertEqual(self.run_main("--since", DAY1, "--until", DAY2), run_events.EXIT_OK)
        self.assertEqual(self.encoder.encoded, [])

    def test_rerun_fills_earlier_days_not_only_newly_saved(self):
        # 앞날(DAY1)만 임베딩 없이 저장해 둔다 — 앞 실행이 임베딩 전에 멈춘 상황
        self.assertEqual(self.run_main("--date", DAY1, "--no-embed"), run_events.EXIT_OK)
        day1_total, day1_missing = self.chunk_counts(REFS[0].rcept_no)
        self.assertEqual(day1_missing, day1_total)

        # 기간 전체로 다시 실행: 새로 저장하는 건 DAY2뿐이지만 DAY1의 빈 청크도 채운다 (a968c27)
        self.assertEqual(self.run_main("--since", DAY1, "--until", DAY2), run_events.EXIT_OK)
        self.assertEqual(self.chunk_counts(REFS[0].rcept_no), (day1_total, 0))
        total, missing = self.chunk_counts()
        self.assertEqual(missing, 0)
        self.assertEqual(len(self.encoder.encoded), total)


if __name__ == "__main__":
    unittest.main()
