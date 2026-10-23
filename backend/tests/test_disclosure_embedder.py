"""임베더 테스트: 가짜 모델만 쓴다 (모델 다운로드·GPU 없음)."""

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import numpy as np
import torch

from pipelines.disclosures import embedder


class FakeOOM(RuntimeError):
    pass


class BatchRunnerTest(unittest.TestCase):
    def test_length_sorted_batches_and_original_order(self):
        texts = ["aa", "a", "aaaa", "aaa", "aaaaa"]
        lengths = [len(t) for t in texts]
        batches = []

        def forward(batch):
            batches.append(list(batch))
            return [t.upper() for t in batch]

        runner = embedder.BatchRunner(forward, batch_size=2, is_oom=lambda e: False, clear_cache=lambda: None)
        self.assertEqual(runner.run(texts, lengths), [t.upper() for t in texts])
        self.assertEqual(batches, [["aaaaa", "aaaa"], ["aaa", "aa"], ["a"]])

    def test_oom_halves_batch_retries_and_keeps_smaller_size(self):
        calls = []
        cleared = []

        def forward(batch):
            calls.append(len(batch))
            if len(batch) > 2:
                raise FakeOOM("CUDA out of memory")
            return [len(t) for t in batch]

        runner = embedder.BatchRunner(forward, batch_size=8, is_oom=lambda e: isinstance(e, FakeOOM), clear_cache=lambda: cleared.append(1))
        texts = [str(i) * (i + 1) for i in range(7)]
        self.assertEqual(runner.run(texts, [len(t) for t in texts]), [len(t) for t in texts])
        self.assertEqual(calls, [7, 4, 2, 2, 2, 1])  # 8→4→2 후 유지 (첫 시도는 남은 7개)
        self.assertEqual(runner.batch_size, 2)
        self.assertEqual(runner.oom_events, 2)
        self.assertEqual(len(cleared), 2)

    def test_cache_cleared_outside_except_block(self):
        import sys

        states = []

        def forward(batch):
            if len(batch) > 1:
                raise FakeOOM("out of memory")
            return batch

        runner = embedder.BatchRunner(forward, batch_size=2, is_oom=lambda e: True, clear_cache=lambda: states.append(sys.exc_info()[0]))
        runner.run(["a", "b"], [1, 1])
        self.assertEqual(states, [None])  # 처리 중인 예외가 없는 상태에서 비운다

    def test_oom_at_batch_one_raises(self):
        def forward(batch):
            raise FakeOOM("out of memory")

        runner = embedder.BatchRunner(forward, batch_size=2, is_oom=lambda e: True, clear_cache=lambda: None)
        with self.assertRaises(FakeOOM):
            runner.run(["a", "b"], [1, 1])
        self.assertEqual(runner.batch_size, 1)

    def test_non_oom_error_is_not_retried(self):
        runner = embedder.BatchRunner(lambda b: (_ for _ in ()).throw(ValueError("x")), batch_size=4, is_oom=embedder.is_cuda_oom, clear_cache=lambda: None)
        with self.assertRaises(ValueError):
            runner.run(["a"], [1])
        self.assertEqual(runner.batch_size, 4)

    def test_streaming_without_keeping_results(self):
        seen = []
        runner = embedder.BatchRunner(lambda b: b, batch_size=2, is_oom=lambda e: False, clear_cache=lambda: None)
        self.assertEqual(runner.run(["x", "yy", "z"], [1, 2, 1], on_batch=lambda idx, out: seen.extend(idx), keep_results=False), [])
        self.assertEqual(sorted(seen), [0, 1, 2])

    def test_is_cuda_oom(self):
        self.assertTrue(embedder.is_cuda_oom(RuntimeError("CUDA out of memory. Tried to allocate")))
        self.assertTrue(embedder.is_cuda_oom(torch.cuda.OutOfMemoryError("x")))
        self.assertFalse(embedder.is_cuda_oom(ValueError("out of memory")))


class QualityTest(unittest.TestCase):
    def test_check_dense(self):
        good = embedder.l2_normalize(np.array([[3.0, 4.0], [1.0, 0.0]]))
        embedder.check_dense(good)
        with self.assertRaises(embedder.EmbeddingQualityError):
            embedder.check_dense(np.array([[np.nan, 0.0]], dtype=np.float32))
        with self.assertRaises(embedder.EmbeddingQualityError):
            embedder.check_dense(np.array([[np.inf, 0.0]], dtype=np.float32))
        with self.assertRaises(embedder.EmbeddingQualityError):
            embedder.check_dense(np.array([[0.5, 0.0]], dtype=np.float32))


class DeviceRevisionTest(unittest.TestCase):
    def test_no_cuda_stops_unless_allow_cpu(self):
        with mock.patch("torch.cuda.is_available", return_value=False):
            with self.assertRaises(embedder.DeviceError):
                embedder.select_device(["cuda:0"], allow_cpu=False)
            self.assertEqual(embedder.select_device(["cuda:0"], allow_cpu=True), "cpu")

    def test_revision_mismatch_stops(self):
        with mock.patch("huggingface_hub.snapshot_download", return_value="/cache/snapshots/othersha"):
            with self.assertRaises(embedder.ModelRevisionError):
                embedder.resolve_model_path("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", offline=True)
        with mock.patch("huggingface_hub.snapshot_download", return_value="/cache/snapshots/abc") as download:
            self.assertEqual(embedder.resolve_model_path("BAAI/bge-m3", "abc", offline=True), Path("/cache/snapshots/abc"))
            self.assertTrue(download.call_args.kwargs["local_files_only"])
            self.assertIn("onnx/*", download.call_args.kwargs["ignore_patterns"])


class FakeBatch(dict):
    def to(self, device):
        return self


class FakeTokenizer:
    special_tokens_map = {"cls_token": "<s>", "eos_token": "</s>", "pad_token": "<pad>", "unk_token": "<unk>"}
    ids = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3}

    def convert_tokens_to_ids(self, token):
        return self.ids[token]

    def __call__(self, texts, padding=False, truncation=False, max_length=None, return_tensors=None, add_special_tokens=True):
        rows = [[0] + [10 + len(word) for word in text.split()] + [2] for text in texts]
        if return_tensors is None:
            return {"input_ids": rows}
        width = max(len(r) for r in rows)
        rows = [r + [1] * (width - len(r)) for r in rows]
        return FakeBatch(input_ids=torch.tensor(rows))


class FakeModel:
    def __init__(self):
        self.calls = []

    def to(self, device):
        return self

    def eval(self):
        return self

    def float(self):
        return self

    def __call__(self, inputs, return_dense, return_sparse, return_colbert_vecs):
        self.calls.append((return_dense, return_sparse, return_colbert_vecs, torch.is_inference_mode_enabled()))
        ids = inputs["input_ids"]
        dense = torch.stack([torch.tensor([float(len(row)), 1.0, 0.0], dtype=torch.float16) for row in ids])
        sparse = (ids.float() / 10.0).unsqueeze(-1)
        return {"dense_vecs": dense, "sparse_vecs": sparse}


class FakeFlagModel:
    def __init__(self):
        self.tokenizer = FakeTokenizer()
        self.model = FakeModel()


class EncoderTest(unittest.TestCase):
    def test_single_pass_dense_and_sparse(self):
        flag = FakeFlagModel()
        encoder = embedder.M3Encoder(flag, "cpu", batch_size=4, max_length=8, query_max_length=4)
        results, stats = encoder.encode_documents(["a bb", "ccc", "a a a a a a a a a"], sparse=True)
        self.assertEqual(len(flag.model.calls), 1)  # 탐색용 재추론 없이 한 번
        self.assertEqual(flag.model.calls[0], (True, True, False, True))
        self.assertEqual(stats.truncated, 1)
        for result in results:
            self.assertAlmostEqual(float(np.linalg.norm(result.dense)), 1.0, places=5)
            self.assertEqual(result.dense.dtype, np.float32)
        # 특수 토큰(0,1,2) 제외, 토큰별 최대 가중치, 키는 원래 토큰 ID 문자열
        self.assertEqual(results[0].sparse, {"11": 1.1, "12": 1.2})
        self.assertEqual(results[1].sparse, {"13": 1.3})

    def test_dense_only_mode(self):
        flag = FakeFlagModel()
        encoder = embedder.M3Encoder(flag, "cpu", batch_size=4, max_length=8, query_max_length=4)
        results, _ = encoder.encode_documents(["a"], sparse=False)
        self.assertIsNone(results[0].sparse)
        self.assertEqual(flag.model.calls[0][:3], (True, False, False))
        query = encoder.encode_query("a", sparse=True)
        self.assertEqual(query.sparse, {"11": 1.1})

    def test_patch_dtype_is_idempotent(self):
        from transformers import AutoModel

        embedder.patch_transformers_dtype()
        patched = AutoModel.from_pretrained
        embedder.patch_transformers_dtype()
        self.assertIs(AutoModel.from_pretrained, patched)


class StubEncoder:
    """encode_documents 계약만 흉내 낸다. bad_texts는 NaN 벡터를 낸다."""

    def __init__(self, bad_texts=()):
        self.batch_size = 2
        self.bad_texts = set(bad_texts)

    def encode_documents(self, texts, sparse, on_batch=None, keep_results=True):
        for start in range(0, len(texts), self.batch_size):
            indices = list(range(start, min(start + self.batch_size, len(texts))))
            outputs = []
            for i in indices:
                vector = np.full(1024, np.nan if texts[i] in self.bad_texts else 1 / 32, dtype=np.float32)
                outputs.append(embedder.Encoded(dense=vector, sparse={"7": 0.5} if sparse else None))
            on_batch(indices, outputs)
        return [], embedder.EncodeStats(items=len(texts), batch_size=self.batch_size)


def _engine_or_none():
    try:
        from sqlalchemy import text

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
class EmbedPendingDbTest(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import text

        self.text = text
        self.conn = ENGINE.connect()
        self.outer = self.conn.begin()
        self.conn.execute(text(
            "INSERT INTO disclosures (rcept_no, symbol, title, kind, period_end, rcept_dt)"
            " VALUES ('T0000000000099', '005930', 't', 'half', '2001-06-30', '2001-08-14')"
        ))
        for i, chunk_text in enumerate(["가", "나", "다", "라", "마"]):
            self.conn.execute(text(
                "INSERT INTO disclosure_chunks (rcept_no, chunk_index, section, chunk_text) VALUES ('T0000000000099', :i, 's', :t)"
            ), {"i": i, "t": chunk_text})

    def tearDown(self):
        self.outer.rollback()
        self.conn.close()

    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn

    def null_count(self):
        return self.conn.execute(self.text("SELECT count(*) FROM disclosure_chunks WHERE rcept_no = 'T0000000000099' AND embedding IS NULL")).scalar()

    def test_hybrid_embeds_nulls_writes_sparse_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            sparse_dir = Path(directory)
            report = embedder.embed_pending(self.begin, StubEncoder(), ["T0000000000099"], sparse_dir=sparse_dir, commit_every=2)
            self.assertEqual((report.pending, report.embedded, report.failed), (5, 5, 0))
            self.assertEqual(self.null_count(), 0)
            from pipelines.disclosures import sparse_store

            self.assertEqual(sparse_store.keys(sparse_dir, ["T0000000000099"]), {("T0000000000099", i) for i in range(5)})
            again = embedder.embed_pending(self.begin, StubEncoder(), ["T0000000000099"], sparse_dir=sparse_dir, commit_every=2)
            self.assertEqual(again.pending, 0)
            sparse_store.remove(sparse_dir, "T0000000000099")  # sparse가 없으면 다시 처리
            self.assertEqual(embedder.embed_pending(self.begin, StubEncoder(), ["T0000000000099"], sparse_dir=sparse_dir).pending, 5)

    def test_bad_batch_is_not_saved(self):
        report = embedder.embed_pending(self.begin, StubEncoder(bad_texts={"다"}), ["T0000000000099"], sparse_dir=None, commit_every=256)
        self.assertEqual((report.embedded, report.failed), (3, 2))  # 배치 [다, 라] 실패
        self.assertEqual(self.null_count(), 2)
        norm = self.conn.execute(self.text(
            "SELECT max(abs(vector_norm(embedding) - 1)) FROM disclosure_chunks WHERE rcept_no = 'T0000000000099' AND embedding IS NOT NULL"
        )).scalar()
        self.assertLess(norm, 1e-5)


if __name__ == "__main__":
    unittest.main()
