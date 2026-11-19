import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import numpy as np

from pipelines.disclosures import search, sparse_store
from pipelines.disclosures.embedder import Encoded
from pipelines.disclosures.search import Filters, Hit
from pipelines.updates.disclosure_search import _minmax, _select_top


class CombineTest(unittest.TestCase):
    def test_minmax(self):
        self.assertEqual(search.minmax({("a", 0): 2.0, ("a", 1): 4.0, ("a", 2): 3.0}), {("a", 0): 0.0, ("a", 1): 1.0, ("a", 2): 0.5})
        self.assertEqual(search.minmax({}), {})

    def test_minmax_equal_values_are_all_one(self):
        self.assertEqual(search.minmax({("a", 0): 0.7, ("a", 1): 0.7}), {("a", 0): 1.0, ("a", 1): 1.0})

    def test_half_half_weighting(self):
        dense = {("a", 0): 0.9, ("a", 1): 0.5, ("a", 2): 0.1}
        sparse = {("a", 0): 0.0, ("a", 1): 10.0, ("a", 2): 5.0}
        ranked = search.combine(dense, sparse, 0.5, 0.5, 10)
        scores = dict(ranked)
        self.assertAlmostEqual(scores[("a", 0)], 0.5)
        self.assertAlmostEqual(scores[("a", 1)], 0.5 * 0.5 + 0.5 * 1.0)
        self.assertAlmostEqual(scores[("a", 2)], 0.5 * 0.0 + 0.5 * 0.5)
        self.assertEqual([key for key, _ in ranked], [("a", 1), ("a", 0), ("a", 2)])

    def test_weights_change_ranking(self):
        dense = {("a", 0): 1.0, ("a", 1): 0.0}
        sparse = {("a", 0): 0.0, ("a", 1): 1.0}
        self.assertEqual(search.combine(dense, sparse, 0.7, 0.3, 1)[0][0], ("a", 0))
        self.assertEqual(search.combine(dense, sparse, 0.3, 0.7, 1)[0][0], ("a", 1))

    def test_combine_rejects_zero_filling(self):
        with self.assertRaises(ValueError):
            search.combine({("a", 0): 1.0}, {("a", 1): 1.0}, 0.5, 0.5, 10)

    def test_vector_literal(self):
        self.assertEqual(search.vector_literal(np.array([0.5, -1.0], dtype=np.float32)), "[0.5,-1.0]")

    def test_colbert_cache_key_invalidates_on_text_or_model_change(self):
        cache = search.ColbertCache(1)
        vector = np.ones((1, 4), dtype=np.float16)
        cache.put(("R", 0, "text-a", "model-a"), vector)
        self.assertIsNotNone(cache.get(("R", 0, "text-a", "model-a")))
        self.assertIsNone(cache.get(("R", 0, "text-b", "model-a")))
        self.assertIsNone(cache.get(("R", 0, "text-a", "model-b")))


class SparseStoreTest(unittest.TestCase):
    def test_append_read_dedupe_compact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sparse_store.append(root, [("R1", 1, {"7": 0.5}), ("R1", 0, {"5": 0.25}), ("R2", 0, {"5": 1.0})])
            sparse_store.append(root, [("R1", 1, {"7": 0.75})])  # 재실행으로 생긴 중복: 마지막 줄 사용
            self.assertEqual(sparse_store.read(root, "R1"), {1: {"7": 0.75}, 0: {"5": 0.25}})
            self.assertEqual(sparse_store.keys(root, ["R1", "R2"]), {("R1", 0), ("R1", 1), ("R2", 0)})
            self.assertEqual(sparse_store.compact(root, "R1", valid_indices={0, 1}), 2)
            lines = (root / "R1.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ['{"rcept_no":"R1","chunk_index":0,"weights":{"5":0.25}}', '{"rcept_no":"R1","chunk_index":1,"weights":{"7":0.75}}'])
            self.assertEqual(sparse_store.compact(root, "R1", valid_indices={0}), 1)
            sparse_store.remove(root, "R2")
            self.assertFalse((root / "R2.jsonl").exists())

    def test_index_matches_bruteforce(self):
        rng = np.random.default_rng(0)
        entries = {}
        for i in range(40):
            tokens = rng.choice(100, size=12, replace=False)
            entries[("R", i)] = {str(int(t)): float(np.float32(rng.random())) for t in tokens}
        index = sparse_store.SparseIndex(entries)
        query = {str(t): 0.5 for t in (1, 5, 9, 42, 77)}
        expected = sorted(
            ((key, sparse_store.lexical_score(query, weights)) for key, weights in entries.items()),
            key=lambda item: (-item[1], item[0]),
        )
        expected = [(k, s) for k, s in expected if s > 0][:5]
        got = index.top(query, 5)
        self.assertEqual([k for k, _ in got], [k for k, _ in expected])
        for (k1, s1), (_, s2) in zip(got, expected):
            self.assertAlmostEqual(s1, s2, places=5)
        for key, weights in list(entries.items())[:10]:
            self.assertAlmostEqual(index.score(query, key), sparse_store.lexical_score(query, weights), places=5)
        self.assertIsNone(index.score(query, ("X", 0)))
        self.assertEqual(index.top(query, 5, allowed={"none"}), [])

    def test_from_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            sparse_store.append(Path(directory), [("R1", 0, {"3": 1.0}), ("R2", 0, {"3": 2.0})])
            index = sparse_store.SparseIndex.from_dir(Path(directory), ["R2", "R1"])
            self.assertEqual(index.top({"3": 1.0}, 2), [(("R2", 0), 2.0), (("R1", 0), 1.0)])

    def test_db_and_legacy_file_indexes_score_the_same(self):
        entries = [("R1", 0, {"3": 1.0}), ("R2", 0, {"3": 2.0})]

        class RowsConn:
            def execute(self, statement, params=None):
                return entries

        db_index = sparse_store.SparseIndex.from_connection(RowsConn())
        with tempfile.TemporaryDirectory() as directory:
            sparse_store.append(Path(directory), entries)
            file_index = sparse_store.SparseIndex.from_dir(Path(directory), ["R1", "R2"])
        query = {"3": 0.5}
        self.assertEqual(db_index.top(query, 2), file_index.top(query, 2))


class FakeEncoder:
    def encode_query(self, query, sparse, colbert=False):
        return Encoded(dense=np.ones(4, dtype=np.float32) / 2, sparse={"1": 1.0} if sparse else None)


class FakeConn:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append(str(statement))


class FakeEngine:
    def __init__(self):
        self.conn = FakeConn()

    @contextmanager
    def begin(self):
        yield self.conn


class HybridSearchTest(unittest.TestCase):
    def test_one_sided_candidates_get_real_scores(self):
        # dense 후보: A0, A1 / sparse 후보: A1, B0 → A0은 sparse 실계산, B0은 dense 실계산
        dense_hits = [Hit("A", 0, 0.9, dense=0.9), Hit("A", 1, 0.6, dense=0.6)]
        index = sparse_store.SparseIndex({("A", 0): {"2": 1.0}, ("A", 1): {"1": 0.5}, ("B", 0): {"1": 2.0}})
        engine = FakeEngine()
        with (
            mock.patch.object(search, "dense_candidates", return_value=dense_hits) as candidates,
            mock.patch.object(search, "dense_scores_for", return_value={("B", 0): Hit("B", 0, 0.3, dense=0.3)}) as extra,
        ):
            hits = search.hybrid_search(engine, FakeEncoder(), index, "질의", Filters(), {"candidate_k": 50, "final_k": 10, "exact": True})
        self.assertEqual(candidates.call_args.args[2], 50)
        self.assertEqual(extra.call_args.args[2], [("B", 0)])
        by_key = {hit.key: hit for hit in hits}
        self.assertEqual(set(by_key), {("A", 0), ("A", 1), ("B", 0)})
        self.assertEqual(by_key[("A", 0)].sparse, 0.0)  # 공통 토큰 없음 → 실제 계산값 0
        self.assertEqual(by_key[("B", 0)].dense, 0.3)
        # dense: A0 .9→1, A1 .6→.5, B0 .3→0 / sparse: A0 0→0, A1 .5→.25, B0 2→1
        self.assertAlmostEqual(by_key[("A", 0)].score, 0.5)
        self.assertAlmostEqual(by_key[("A", 1)].score, 0.375)
        self.assertAlmostEqual(by_key[("B", 0)].score, 0.5)
        self.assertEqual([h.key for h in hits], [("A", 0), ("B", 0), ("A", 1)])
        self.assertIn("SET LOCAL enable_indexscan = off", engine.conn.statements)

    def test_service_mode_sets_ef_search(self):
        engine = FakeEngine()
        with mock.patch.object(search, "dense_candidates", return_value=[]):
            search.dense_search(engine, FakeEncoder(), "q", Filters(), {"exact": False, "ef_search": 200})
        self.assertIn("SET LOCAL hnsw.ef_search = 200", engine.conn.statements)


class UpdateDisclosureSearchTest(unittest.TestCase):
    def test_minmax(self):
        self.assertEqual(_minmax({"a": 2.0, "b": 4.0}), {"a": 0.0, "b": 1.0})
        self.assertEqual(_minmax({"a": 2.0}), {"a": 0.0})

    def test_top_limits_chunks_from_one_document(self):
        scores = {("old", i): 1.0 - i / 100 for i in range(8)}
        scores.update({("current", 0): 0.8, ("current", 1): 0.79, ("other", 0): 0.78})
        top = _select_top(scores, 6, 3)
        self.assertEqual(sum(r == "old" for r, _ in top), 3)
        self.assertIn(("current", 0), top)
        self.assertIn(("current", 1), top)


if __name__ == "__main__":
    unittest.main()


class SectionHintsTest(unittest.TestCase):
    """질문 종류 → 정기보고서 목차 힌트 (실험 2026-11-17)."""

    def test_hints(self):
        from pipelines.updates.disclosure_search import section_hints
        self.assertEqual(section_hints("유상증자 규모가 작년 영업이익이랑 비교하면?")[:1], ["증권의 발행을 통한 자금조달"])
        self.assertIn("사업의 개요", section_hints("46시리즈 배터리가 기존이랑 뭐가 달라?"))
        self.assertIn("매출 및 수주상황", section_hints("수출 계약이 매출로 언제 잡혀?"))
        self.assertIn("부문", section_hints("양극재 사업 적자가 얼마나 돼?"))
        self.assertEqual(section_hints("오늘 기분이 좋다"), [])
        hints = section_hints("유상증자 하는 이유가 뭐야? 자금 조달 계획도")
        self.assertEqual(len(hints), len(set(hints)))             # 겹치지 않게
