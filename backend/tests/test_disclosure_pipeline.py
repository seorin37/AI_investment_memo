"""실행 진입점·validate·evaluate 테스트 (실제 API·모델 없음)."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import numpy as np
import yaml
from sqlalchemy import text

from pipelines.common.config import REPO_ROOT, load_config
from pipelines.disclosures import dart, evaluate, pipeline, sparse_store
from pipelines.disclosures.chunker import Chunk, doc_fingerprint, sha256_text
from pipelines.disclosures.search import Hit, vector_literal
from pipelines.disclosures.validate import disclosures_per_symbol_detail, validate
from tests.disclosure_fixtures import SAMPLE_XML, FakeTokens, zip_bytes


API_KEY = "test-secret-key"


class Workspace:
    """임시 디렉터리에 경로만 바꾼 설정 파일과 샘플 ZIP을 만든다."""

    def __init__(self, directory: str):
        self.root = Path(directory)
        config = load_config(REPO_ROOT / "configs/common.yaml")
        config["paths"] = {key: str(self.root / key) for key in ("raw_dir", "parsed_dir", "chunks_dir", "sparse_dir", "logs_dir")}
        self.common = self.root / "common.yaml"
        self.common.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        self.zip = self.root / "raw_dir" / "005930_20260814003699.zip"
        self.zip.parent.mkdir(parents=True)
        self.zip.write_bytes(zip_bytes("20260814003699.xml", SAMPLE_XML))

    def args(self, mode="hybrid", *extra):
        return ["--config", str(self.common), "--mode-config", str(REPO_ROOT / f"configs/{mode}.yaml"), *extra]

    def run_logs(self):
        return sorted((self.root / "logs_dir").glob("run_*.json"))


class PipelineCliTest(unittest.TestCase):
    def test_parse_steps(self):
        self.assertEqual(pipeline.parse_steps("embed,parse"), ["parse", "embed"])
        with self.assertRaises(SystemExit):
            pipeline.parse_steps("parse,fly")

    def test_mode_config_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(pipeline.main("dense", ws.args("hybrid", "--dry-run")), 1)

    def test_collect_without_key_exits_2_without_network_or_db(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch("dotenv.load_dotenv"),
                mock.patch.object(dart, "collect") as collect,
                mock.patch("pipelines.common.db.get_engine") as get_engine,
                redirect_stderr(io.StringIO()) as stderr,
            ):
                result = pipeline.main("dense", ws.args("dense"))
        self.assertEqual(result, 2)
        collect.assert_not_called()
        get_engine.assert_not_called()
        self.assertIn("DART_API_KEY", stderr.getvalue())

    def test_from_zip_dry_run_needs_no_key_db_or_model(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch("pipelines.common.db.get_engine") as get_engine,
            ):
                result = pipeline.main("hybrid", ws.args("hybrid", "--from-zip", str(ws.zip), "--dry-run"), token_counter_factory=FakeTokens)
            self.assertEqual(result, 0)
            get_engine.assert_not_called()
            record = json.loads(ws.run_logs()[0].read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "success")
            self.assertEqual(record["documents"][0]["period_end"], "2026-06-30")
            self.assertEqual(record["documents"][0]["kind"], "half")
            self.assertGreater(record["chunk_summary"]["chunks"], 0)
            self.assertIn("20260814003699", record["doc_fingerprints"])
            self.assertFalse((ws.root / "chunks_dir").exists())  # dry-run은 산출물을 쓰지 않는다

    def test_dry_run_without_zip_lists_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            ref = dart.ReportRef("005930", "20250311000001", "사업보고서 (2024.12)", "annual", "2024-12-31", "2025-03-11")
            with mock.patch.object(pipeline.Run, "resolve_refs", return_value=[ref]):
                result = pipeline.main("dense", ws.args("dense", "--steps", "parse,chunk", "--dry-run"), token_counter_factory=FakeTokens)
            self.assertEqual(result, 0)

    def test_structurally_broken_zip_fails_only_that_document_with_quality_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            broken = SAMPLE_XML.replace("<P>첫 문단입니다.</P>", "<P>첫 문단<SECTION-1><TITLE>X</TITLE></SECTION-1></P>")
            bad_zip = ws.root / "raw_dir" / "005930_20260814000001.zip"
            bad_zip.write_bytes(zip_bytes("20260814000001.xml", broken))
            with redirect_stderr(io.StringIO()) as stderr:
                result = pipeline.main(
                    "dense",
                    ws.args("dense", "--from-zip", str(ws.zip), "--from-zip", str(bad_zip), "--steps", "parse,chunk", "--dry-run"),
                    token_counter_factory=FakeTokens,
                )
            self.assertEqual(result, 1)
            self.assertIn("구조 이상", stderr.getvalue())
            record = json.loads(ws.run_logs()[0].read_text(encoding="utf-8"))
            self.assertTrue(record["parse_quality"]["20260814000001"]["failed"])
            self.assertEqual(record["parse_quality"]["20260814000001"]["nested_sections"], 1)
            self.assertIn("20260814003699", record["doc_fingerprints"])  # 정상 문서는 계속 처리

    def test_period_mismatch_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            ref = dart.ReportRef("005930", "20260814003699", "반기보고서 (2025.06)", "half", "2025-06-30", "2025-08-14")
            with (
                mock.patch.object(pipeline.Run, "resolve_refs", return_value=[ref]),
                redirect_stderr(io.StringIO()) as stderr,
            ):
                result = pipeline.main("dense", ws.args("dense", "--steps", "parse,chunk", "--dry-run"), token_counter_factory=FakeTokens)
        self.assertEqual(result, 1)
        self.assertIn("XML 기간", stderr.getvalue())

    def test_api_key_never_reaches_logs_or_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            ws = Workspace(directory)
            fake = dart.CollectResult(reports=[], corp_codes={}, failures=[f"005930: 오류 crtfc_key={API_KEY}"])
            with (
                mock.patch.dict(os.environ, {"DART_API_KEY": API_KEY}, clear=True),
                mock.patch.object(dart, "collect", return_value=fake),
                redirect_stderr(io.StringIO()) as stderr,
            ):
                result = pipeline.main("dense", ws.args("dense", "--dry-run"), token_counter_factory=FakeTokens)
            self.assertEqual(result, 1)
            self.assertNotIn(API_KEY, stderr.getvalue())
            log_text = ws.run_logs()[0].read_text(encoding="utf-8")
            self.assertNotIn(API_KEY, log_text)
            self.assertIn("[REDACTED]", log_text)

    def test_manifest_update_replaces_per_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.jsonl"
            pipeline.update_manifest(path, {"B": [{"rcept_no": "B", "chunk_index": 0}], "A": [{"rcept_no": "A", "chunk_index": 1}, {"rcept_no": "A", "chunk_index": 0}]})
            pipeline.update_manifest(path, {"A": [{"rcept_no": "A", "chunk_index": 0}]}, drop={"B"})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{"rcept_no": "A", "chunk_index": 0}])


class EvaluateTest(unittest.TestCase):
    def test_metrics(self):
        hits = [Hit("R", 0, 1.0, section="II. 사업 > 1"), Hit("R", 1, 0.9, section="III. 재무 > 3. 주석 > 5. 재고자산 (연결)"), Hit("Q", 0, 0.8, section="III. 재무 > 3. 주석")]
        gold = [{"rcept_no": "R", "section_prefix": "III. 재무 > 3. 주석 > 5. 재고자산"}, {"rcept_no": "Z", "section_prefix": ""}]
        self.assertTrue(evaluate.matches(hits[1], gold[0]))
        self.assertFalse(evaluate.matches(hits[2], gold[0]))  # 다른 문서
        self.assertEqual(evaluate.recall_at(hits, gold, 1), 0.0)
        self.assertEqual(evaluate.recall_at(hits, gold, 5), 0.5)
        self.assertEqual(evaluate.reciprocal_rank(hits, gold), 0.5)
        self.assertEqual(evaluate.reciprocal_rank(hits[:1], gold), 0.0)

    def test_evaluate_summary_and_latency(self):
        queries = [{"query": "q", "gold": [{"rcept_no": "R", "section_prefix": "A"}]}] * 2
        result = evaluate.evaluate(queries, lambda row: [Hit("R", 0, 1.0, section="A > b")])
        self.assertEqual(result["summary"]["recall@5"], 1.0)
        self.assertEqual(result["summary"]["mrr"], 1.0)
        self.assertEqual(result["summary"]["queries"], 2)
        self.assertGreaterEqual(result["summary"]["latency_ms_p95"], 0.0)

    def test_example_queries_file_is_valid(self):
        queries = evaluate.load_queries(REPO_ROOT / "eval/queries.example.jsonl")
        self.assertGreater(len(queries), 0)
        for row in queries:
            self.assertTrue(all({"rcept_no", "section_prefix"} <= set(g) for g in row["gold"]))

    def test_percentile(self):
        self.assertEqual(evaluate.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(evaluate.percentile([], 0.95), 0.0)


def _engine_or_none():
    try:
        from pipelines.common.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


VALIDATION_PERIODS = [
    "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
    "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
    "2026-03-31", "2026-06-30",
]


def validation_rows(symbol):
    kind = {"03": "quarterly", "06": "half", "09": "quarterly", "12": "annual"}
    return [(symbol, kind[period[5:7]], period, f"{symbol}-{index}") for index, period in enumerate(VALIDATION_PERIODS)]


class DisclosuresPerSymbolDetailTest(unittest.TestCase):
    def test_four_companies_have_exactly_ten(self):
        symbols = ["005930", "000660", "035420", "105560"]
        check = disclosures_per_symbol_detail(
            [row for symbol in symbols for row in validation_rows(symbol)],
            {symbol: 10 for symbol in symbols},
            VALIDATION_PERIODS,
        )
        self.assertTrue(check["ok"], check)
        self.assertEqual({symbol: detail["actual"] for symbol, detail in check["detail"]["companies"].items()}, {symbol: 10 for symbol in symbols})

    def test_missing_and_duplicate_details_are_exact(self):
        rows = validation_rows("105560")
        rows = [row for row in rows if row[2] != "2025-12-31"]
        rows.append(("105560", "quarterly", "2024-03-31", "duplicate-rcept"))
        check = disclosures_per_symbol_detail(rows, {"105560": 10}, VALIDATION_PERIODS)
        self.assertFalse(check["ok"])
        self.assertEqual(check["detail"], {"companies": {"105560": {
            "expected": 10,
            "actual": 10,
            "missing": [{"period_end": "2025-12-31", "kind": "annual"}],
            "duplicates": [{
                "period_end": "2024-03-31",
                "kind": "quarterly",
                "count": 2,
                "rcept_nos": ["105560-0", "duplicate-rcept"],
            }],
            "unexpected": [],
        }}})


ENGINE = _engine_or_none()


def tearDownModule():
    if ENGINE is not None:
        ENGINE.dispose()


@unittest.skipIf(ENGINE is None, "로컬 DB(DATABASE_URL)에 연결할 수 없어 건너뜀")
class ValidateDbTest(unittest.TestCase):
    RCEPT = "T0000000000077"

    def setUp(self):
        self.conn = ENGINE.connect()
        self.outer = self.conn.begin()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.conn.execute(text(
            "INSERT INTO disclosures (rcept_no, symbol, title, kind, period_end, rcept_dt)"
            " VALUES (:r, '005930', 't', 'half', '2001-06-30', '2001-08-14')"
        ), {"r": self.RCEPT})
        texts = ["첫 청크", "둘째 청크"]
        vector = vector_literal(np.full(1024, 1 / 32, dtype=np.float32))
        for i, chunk_text in enumerate(texts):
            self.conn.execute(text(
                "INSERT INTO disclosure_chunks (rcept_no, chunk_index, section, chunk_text, embedding) VALUES (:r, :i, 's', :t, CAST(:e AS vector))"
            ), {"r": self.RCEPT, "i": i, "t": chunk_text, "e": vector})
        self.chunks = [Chunk(self.RCEPT, i, "s", "text", t, 1, sha256_text(t)) for i, t in enumerate(texts)]
        pipeline.update_manifest(self.root / "manifest.jsonl", {self.RCEPT: [c.manifest_row() for c in self.chunks]})
        sparse_store.append(self.root / "sparse", [(self.RCEPT, 0, {"5": 1.0}), (self.RCEPT, 1, {"6": 1.0})])

    def tearDown(self):
        self.outer.rollback()
        self.conn.close()
        self.tmp.cleanup()

    def run_validate(self, **kwargs):
        options = {"manifest_path": self.root / "manifest.jsonl", "sparse_dir": self.root / "sparse", "expected_per_symbol": None}
        options.update(kwargs)
        return validate(self.conn, [self.RCEPT], **options)

    def failed(self, result):
        return {c["name"] for c in result["checks"] if not c["ok"]}

    def test_all_checks_pass_and_fingerprint(self):
        result = self.run_validate()
        self.assertTrue(result["ok"], result["checks"])
        self.assertEqual(result["fingerprints"][self.RCEPT], doc_fingerprint([c.chunk_hash for c in self.chunks]))

    def test_detects_null_embedding_sparse_gap_and_manifest_mismatch(self):
        self.conn.execute(text("UPDATE disclosure_chunks SET embedding = NULL WHERE rcept_no = :r AND chunk_index = 1"), {"r": self.RCEPT})
        sparse_store.compact(self.root / "sparse", self.RCEPT, valid_indices={0})
        pipeline.update_manifest(self.root / "manifest.jsonl", {self.RCEPT: [self.chunks[0].manifest_row()]})
        self.assertEqual(self.failed(self.run_validate()), {"embedding_not_null", "sparse_matches_db", "manifest_matches_db"})

    def test_detects_index_gap_and_bad_norm(self):
        self.conn.execute(text("UPDATE disclosure_chunks SET chunk_index = 5 WHERE rcept_no = :r AND chunk_index = 1"), {"r": self.RCEPT})
        self.conn.execute(text("UPDATE disclosure_chunks SET embedding = array_fill(0.5, ARRAY[1024])::vector WHERE rcept_no = :r AND chunk_index = 0"), {"r": self.RCEPT})
        self.assertTrue({"chunk_index_contiguous", "embedding_norm"} <= self.failed(self.run_validate(sparse_dir=None)))

    def test_per_symbol_expectation(self):
        result = self.run_validate(sparse_dir=None, expected_per_symbol={"005930": 10}, periods=["2001-06-30"])
        self.assertIn("disclosures_per_symbol", self.failed(result))

    def test_non_periodic_and_out_of_period_rows_are_ignored(self):
        # 수시공시(period_end NULL) 2건과 대상 기간 밖 정기보고서는 중복·기업별 개수 검사에 넣지 않는다.
        for rcept_no, kind, period_end in (("T0000000000078", "major", None), ("T0000000000079", "major", None), ("T0000000000080", "annual", "2000-12-31")):
            self.conn.execute(text(
                "INSERT INTO disclosures (rcept_no, symbol, title, kind, period_end, rcept_dt)"
                " VALUES (:r, '005930', 't', CAST(:k AS disclosure_kind), CAST(:p AS date), '2001-08-14')"
            ), {"r": rcept_no, "k": kind, "p": period_end})
        result = self.run_validate(expected_per_symbol={"005930": 1}, periods=["2001-06-30"])
        self.assertTrue(result["ok"], result["checks"])


if __name__ == "__main__":
    unittest.main()
