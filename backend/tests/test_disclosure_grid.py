"""그리드 평가 테스트 (WO-019) — 모킹만, GPU·DB·모델 다운로드 없음."""

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import numpy as np
import torch

from pipelines.common.config import REPO_ROOT
from pipelines.disclosures import embedder, evaluate_grid, reference_eval as ref, search, sparse_store
from pipelines.disclosures.search import CandidateScores, ColbertCache, Filters, Hit


class ColbertScoreTest(unittest.TestCase):
    def test_maxsim_mean_expected_value(self):
        q = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        d = np.array([[0.6, 0.8], [1.0, 0.0], [0.0, 0.5]], dtype=np.float32)
        # 질의 토큰1 최대 = 1.0, 토큰2 최대 = 0.8 → 평균 0.9
        self.assertAlmostEqual(embedder.colbert_score(q, d), 0.9, places=6)
        self.assertEqual(embedder.colbert_score(np.zeros((0, 2)), d), 0.0)

    def test_matches_flagembedding_definition(self):
        from FlagEmbedding import BGEM3FlagModel

        rng = np.random.default_rng(0)
        q, d = rng.random((7, 16)).astype(np.float32), rng.random((30, 16)).astype(np.float32)
        expected = float(BGEM3FlagModel.colbert_score(None, q, d))  # self를 쓰지 않는 식
        self.assertAlmostEqual(embedder.colbert_score(q, d), expected, places=5)


class FakeBatch(dict):
    def to(self, device):
        return self


class FakeTokenizer:
    special_tokens_map = {"cls_token": "<s>", "eos_token": "</s>", "pad_token": "<pad>", "unk_token": "<unk>"}
    ids = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3}

    def convert_tokens_to_ids(self, token):
        return self.ids[token]

    def __call__(self, texts, padding=False, truncation=False, max_length=None, return_tensors=None, add_special_tokens=True):
        rows = [[0] + [10 + len(w) for w in t.split()] + [2] for t in texts]
        if return_tensors is None:
            return {"input_ids": rows}
        width = max(len(r) for r in rows)
        mask = [[1] * len(r) + [0] * (width - len(r)) for r in rows]
        rows = [r + [1] * (width - len(r)) for r in rows]
        return FakeBatch(input_ids=torch.tensor(rows), attention_mask=torch.tensor(mask))


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
        self.calls.append(return_colbert_vecs)
        ids = inputs["input_ids"]
        out = {"dense_vecs": torch.ones(ids.shape[0], 3, dtype=torch.float16)}
        if return_sparse:
            out["sparse_vecs"] = (ids.float() / 10).unsqueeze(-1)
        if return_colbert_vecs:
            # CLS 다음부터: (B, L-1, 2), 토큰 위치 값을 그대로 넣어 잘림을 확인
            positions = torch.arange(1, ids.shape[1], dtype=torch.float16)
            out["colbert_vecs"] = torch.stack([positions, positions], dim=-1).unsqueeze(0).repeat(ids.shape[0], 1, 1)
        return out


class FakeFlag:
    def __init__(self):
        self.tokenizer = FakeTokenizer()
        self.model = FakeModel()


class EncoderColbertTest(unittest.TestCase):
    def test_colbert_vectors_drop_cls_and_padding(self):
        encoder = embedder.M3Encoder(FakeFlag(), "cpu", batch_size=4, max_length=16, query_max_length=8)
        vecs = encoder.encode_colbert_documents(["a b c", "a"])
        # "a b c": 토큰 5개(CLS a b c EOS) → CLS 제외 4개, "a": 3개 → 2개 (패딩 제외)
        self.assertEqual([v.shape for v in vecs], [(4, 2), (2, 2)])
        self.assertEqual(vecs[0].dtype, np.float16)
        query = encoder.encode_query("a b", sparse=True, colbert=True)
        self.assertEqual(query.colbert.shape, (3, 2))

    def test_existing_paths_do_not_request_colbert(self):
        flag = FakeFlag()
        encoder = embedder.M3Encoder(flag, "cpu", batch_size=4, max_length=16, query_max_length=8)
        encoder.encode_documents(["a b"], sparse=True)
        encoded = encoder.encode_query("a", sparse=False)
        self.assertEqual(flag.model.calls, [False, False])
        self.assertIsNone(encoded.colbert)


def cand(dense, sparse, colbert=None):
    keys = sorted(dense)
    return CandidateScores(keys, dense, sparse, colbert or {}, {k: Hit(k[0], k[1], dense[k], section="s") for k in keys}, {"total": 1.0}, [])


class RankTest(unittest.TestCase):
    def setUp(self):
        self.scores = cand(
            {("A", 0): 0.9, ("A", 1): 0.6, ("B", 0): 0.3},
            {("A", 0): 0.0, ("A", 1): 0.5, ("B", 0): 2.0},
            {("A", 0): 0.2, ("A", 1): 0.9, ("B", 0): 0.5},
        )

    def test_weight_validation(self):
        for bad in ({"dense": 0.5, "sparse": 0.4}, {"dense": 1.2, "sparse": -0.2}, {"dense": 1.0, "bm25": 0.0}):
            with self.assertRaises(ValueError):
                search.validate_weights(bad)
        self.assertEqual(search.validate_weights({"dense": 0.34, "sparse": 0.33, "colbert": 0.33})["colbert"], 0.33)

    def test_single_signal_orders_by_raw_score(self):
        self.assertEqual([k for k, _ in search.rank(self.scores, {"dense": 1.0}, 10)], [("A", 0), ("A", 1), ("B", 0)])
        self.assertEqual([k for k, _ in search.rank(self.scores, {"colbert": 1.0}, 10)], [("A", 1), ("B", 0), ("A", 0)])

    def test_weighted_sum_of_minmax(self):
        ranked = dict(search.rank(self.scores, {"dense": 0.4, "sparse": 0.2, "colbert": 0.4}, 10))
        # dense: 1, .5, 0 / sparse: 0, .25, 1 / colbert: 0, 1, 3/7
        self.assertAlmostEqual(ranked[("A", 0)], 0.4)
        self.assertAlmostEqual(ranked[("A", 1)], 0.4 * 0.5 + 0.2 * 0.25 + 0.4)
        self.assertAlmostEqual(ranked[("B", 0)], 0.2 + 0.4 * 3 / 7)

    def test_zero_weight_signal_is_ignored_even_if_missing(self):
        no_colbert = cand(self.scores.dense, self.scores.sparse)
        self.assertEqual(search.rank(no_colbert, {"dense": 0.5, "sparse": 0.5}, 10), search.rank(self.scores, {"dense": 0.5, "sparse": 0.5, "colbert": 0.0}, 10))
        with self.assertRaises(ValueError):  # 음성 대조: 쓰는 신호가 비어 있으면 0 채움 대신 오류
            search.rank(no_colbert, {"dense": 0.5, "colbert": 0.5}, 10)

    def test_equal_scores_minmax_is_one(self):
        flat = cand({("A", 0): 0.5, ("A", 1): 0.5}, {("A", 0): 1.0, ("A", 1): 1.0})
        self.assertEqual(search.rank(flat, {"dense": 1.0}, 10), [(("A", 0), 1.0), (("A", 1), 1.0)])


class FakeEncoder:
    def __init__(self):
        self.doc_calls = []

    def encode_query(self, query, sparse, colbert=False):
        return embedder.Encoded(dense=np.ones(4, dtype=np.float32) / 2, sparse={"1": 1.0}, colbert=np.eye(2, dtype=np.float16) if colbert else None)

    def encode_colbert_documents(self, texts):
        self.doc_calls.append(list(texts))
        return [np.array([[1.0, 0.0]], dtype=np.float16) if "a0" in t else np.array([[0.0, 1.0]], dtype=np.float16) for t in texts]


class FakeConn:
    def execute(self, statement, params=None):
        return None


class FakeEngine:
    @contextmanager
    def begin(self):
        yield FakeConn()


DENSE_HITS = [Hit("A", 0, 0.9, dense=0.9), Hit("A", 1, 0.6, dense=0.6)]
INDEX = sparse_store.SparseIndex({("A", 0): {"2": 1.0}, ("A", 1): {"1": 0.5}, ("B", 0): {"1": 2.0}})


@contextmanager
def patched_db():
    with (
        mock.patch.object(search, "dense_candidates", return_value=list(DENSE_HITS)),
        mock.patch.object(search, "dense_scores_for", return_value={("B", 0): Hit("B", 0, 0.3, dense=0.3)}),
        mock.patch.object(search, "chunk_texts", side_effect=lambda conn, keys: {k: f"text {k[0].lower()}{k[1]}" for k in keys}),
    ):
        yield


class ScoreCandidatesTest(unittest.TestCase):
    def test_same_candidates_and_existing_mode_parity(self):
        config = {"candidate_k": 50, "final_k": 10, "exact": True}
        with patched_db():
            scores = search.score_candidates(FakeEngine(), FakeEncoder(), INDEX, "q", Filters(), config, ColbertCache())
            hybrid = search.hybrid_search(FakeEngine(), FakeEncoder(), INDEX, "q", Filters(), config, 0.5, 0.5)
            dense = search.dense_search(FakeEngine(), FakeEncoder(), "q", Filters(), config)
        self.assertEqual(scores.keys, [("A", 0), ("A", 1), ("B", 0)])  # dense 후보 ∪ sparse 후보
        self.assertEqual(set(scores.colbert), set(scores.keys))
        self.assertEqual(scores.sparse[("A", 0)], 0.0)  # sparse 후보 밖이어도 실제 계산
        d50 = search.rank(scores, {"dense": 0.5, "sparse": 0.5}, 10)
        self.assertEqual([(k, round(v, 9)) for k, v in d50], [(h.key, round(h.score, 9)) for h in hybrid])
        d100 = search.rank(scores, {"dense": 1.0}, len(dense))
        self.assertEqual([k for k, _ in d100], [h.key for h in dense])

    def test_colbert_vectors_cached_across_queries(self):
        encoder, cache = FakeEncoder(), ColbertCache()
        with patched_db():
            search.score_candidates(FakeEngine(), encoder, INDEX, "q1", Filters(), {}, cache)
            search.score_candidates(FakeEngine(), encoder, INDEX, "q2", Filters(), {}, cache)
        self.assertEqual([len(c) for c in encoder.doc_calls], [3, 0])
        self.assertEqual((cache.hits, cache.misses), (3, 3))

    def test_colbert_encoding_happens_after_db_transaction(self):
        events = []

        class TrackingEngine(FakeEngine):
            @contextmanager
            def begin(self):
                events.append("begin")
                yield FakeConn()
                events.append("end")

        class TrackingEncoder(FakeEncoder):
            def encode_colbert_documents(self, texts):
                events.append("encode")
                return super().encode_colbert_documents(texts)

        with patched_db():
            scores = search.score_candidates(TrackingEngine(), TrackingEncoder(), INDEX, "q", Filters(), {}, ColbertCache())
        self.assertEqual(events, ["begin", "end", "encode"])
        self.assertEqual(scores.colbert_encoded, 3)
        self.assertNotIn("colbert_encoded_docs", scores.timings_ms)

    def test_cache_lru_limit(self):
        cache = ColbertCache(max_mb=2 / 1024)  # 2KB
        block = np.zeros((1, 512), dtype=np.float16)  # 1KB
        for i in range(3):
            cache.put(("A", i), block)
        self.assertEqual(list(cache.items), [("A", 1), ("A", 2)])
        self.assertIsNone(cache.get(("A", 0)))


def question(qid, symbol, groups, **extra):
    return ref.RefQuestion(qid, symbol, "", "q", tuple(f"{qid}-F{i}" for i in range(len(groups))), tuple(frozenset(g) for g in groups), extra.get("flag", False), extra.get("qt", "숫자"), extra.get("di", "D"))


class ReferenceMetricTest(unittest.TestCase):
    def test_and_between_groups_or_within(self):
        q = question("Q", "005930", [{("R", 1), ("R", 2)}, {("R", 9)}])
        ranked = [("R", 5), ("R", 2), ("R", 3), ("R", 4), ("R", 6), ("R", 9)]
        m = ref.score_question(ranked, q)
        self.assertEqual((m["complete@5"], m["group_recall@5"]), (0.0, 0.5))  # 두 번째 그룹은 6위
        self.assertEqual((m["complete@10"], m["group_recall@10"]), (1.0, 1.0))
        self.assertEqual(m["rr"], 0.5)
        self.assertEqual(ref.score_question([("X", 0)], q)["rr"], 0.0)

    def test_load_reference_scores_only_scored(self):
        rows = [
            {"id": "A-1", "symbol": "005930", "question_original": "q", "eval_status": "scored", "needs_human_check": True,
             "question_type": "숫자", "design_intent": "D", "target_reports": [{"period_end": "2025-12-31"}],
             "required_fact_groups": [{"group_id": "g", "valid_evidence_or": [{"rcept_no": "R", "chunk_index": 3}]}]},
            {"id": "A-2", "symbol": "005930", "question_original": "q", "eval_status": "excluded", "exclude_reason": "not_disclosed_in_scope", "required_fact_groups": []},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ref.jsonl"
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
            scored, excluded = ref.load_reference(path)
            self.assertEqual([q.id for q in scored], ["A-1"])
            self.assertEqual(scored[0].groups, (frozenset({("R", 3)}),))
            self.assertEqual(scored[0].periods, ("2025-12-31",))
            self.assertEqual(excluded, [{"id": "A-2", "reason": "not_disclosed_in_scope"}])
            rows[0]["required_fact_groups"][0]["valid_evidence_or"] = []
            path.write_text(json.dumps(rows[0], ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                ref.load_reference(path)

    def test_real_aligned_reference_loads(self):
        folder = REPO_ROOT / "eval/reference_rag_repair_20261022_v1_db"
        scored, excluded = ref.load_reference(folder / "reference_annotations.jsonl")
        counts = json.loads((folder / "alignment_summary.json").read_text(encoding="utf-8"))["questions"]
        self.assertEqual((len(scored), len(excluded)), (counts.get("scored", 0), counts.get("excluded", 0)))

    def test_malformed_row_error_names_question(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ref.jsonl"
            path.write_text(json.dumps({"id": "BAD-1", "eval_status": "scored", "symbol": "005930"}), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                ref.load_reference(path)
            self.assertIn("BAD-1", str(caught.exception))

    def test_split_reproducible_and_stratified(self):
        qs = [question(f"{s}-{i:02d}", s, [{("R", i)}]) for s in ("A", "B") for i in range(10)]
        first = ref.stratified_split(qs, 0.7, 42)
        self.assertEqual(first, ref.stratified_split(list(reversed(qs)), 0.7, 42))
        self.assertNotEqual(first, ref.stratified_split(qs, 0.7, 7))
        dev, test = first
        small = [question("C-0", "C", [{("R", 0)}]), question("C-1", "C", [{("R", 1)}])]
        small_dev, small_test = ref.stratified_split(small, 0.7, 42)
        self.assertEqual((len(small_dev), len(small_test)), (1, 1))  # 작은 기업도 test가 비지 않는다
        self.assertEqual(sum(1 for i in dev if i.startswith("A")), 7)
        self.assertEqual(sum(1 for i in dev if i.startswith("B")), 7)
        self.assertEqual(set(dev) | set(test), {q.id for q in qs})
        self.assertFalse(set(dev) & set(test))

    def test_stratified_limit(self):
        qs = [question(f"{s}-{i}", s, [{("R", i)}]) for s in ("A", "B", "C", "D") for i in range(5)]
        self.assertEqual([q.id for q in ref.stratified_limit(qs, 8)], ["A-0", "B-0", "C-0", "D-0", "A-1", "B-1", "C-1", "D-1"])


class GridRunTest(unittest.TestCase):
    def test_grid_config_is_valid(self):
        combos, colbert = evaluate_grid.load_grid(REPO_ROOT / "configs/grid.yaml")
        self.assertEqual([c["id"] for c in combos], ["D100", "D50S50", "D30S70", "C1", "C2", "C3", "C4", "C5"])
        self.assertGreater(colbert["cache_max_mb"], 0)

    def test_grid_config_rejects_bad_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            for body in ("combos:\n  - {id: X, dense: 0.6, sparse: 0.6}\n", "combos:\n  - {id: X, dense: 1.0}\n  - {id: X, sparse: 1.0}\n"):
                path = Path(directory) / "g.yaml"
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    evaluate_grid.load_grid(path)

    def test_scorer_called_once_per_question_and_split_selection(self):
        combos, _ = evaluate_grid.load_grid(REPO_ROOT / "configs/grid.yaml")
        scores = cand(
            {("A", 0): 0.9, ("A", 1): 0.6, ("B", 0): 0.3},
            {("A", 0): 0.0, ("A", 1): 0.5, ("B", 0): 2.0},
            {("A", 0): 0.2, ("A", 1): 0.9, ("B", 0): 0.5},
        )
        calls = []

        def scorer(q):
            calls.append(q.id)
            return scores

        qs = [question("S-1", "005930", [{("B", 0)}]), question("S-2", "000660", [{("A", 0)}], flag=True)]
        results = evaluate_grid.run_grid(qs, combos, scorer, final_k=1)
        self.assertEqual(calls, ["S-1", "S-2"])
        self.assertEqual(results[0]["combos"]["D100"]["top"][0]["rcept_no"], "A")
        self.assertEqual(results[0]["combos"]["D30S70"]["complete@5"], 1.0)  # sparse 비중 높으면 B0이 1위
        summary = evaluate_grid.summarize(results, combos, ["S-1"], ["S-2"])
        self.assertEqual(summary["combos"]["D100"]["reviewed"]["n"], 1)
        self.assertIn(summary["selection"]["best_on_dev"], {"D30S70", "C4"})
        self.assertEqual(summary["selection"]["best_on_dev"], "D30S70")  # 동점이면 그리드 앞 순서

    def test_question_filters(self):
        q = ref.RefQuestion("Q", "005930", "", "q", ("g",), (frozenset({("R", 1)}),), False, "", "", ("2025-12-31",))
        self.assertEqual(evaluate_grid.question_filters(q, "symbol"), Filters(symbol="005930"))
        self.assertEqual(evaluate_grid.question_filters(q, "none"), Filters())
        self.assertEqual(evaluate_grid.question_filters(q, "symbol_period"), Filters(symbol="005930", period_end="2025-12-31"))

    def test_reference_corpus_mismatch_stops(self):
        from pipelines.disclosures.chunker import CHUNKER_VERSION
        from pipelines.disclosures.parser import PARSER_VERSION

        with tempfile.TemporaryDirectory() as directory:
            ref_path = Path(directory) / "reference_annotations.jsonl"
            summary = Path(directory) / "alignment_summary.json"
            corpus = {"db_chunks": 100, "parser_version": PARSER_VERSION, "chunker_version": CHUNKER_VERSION}
            summary.write_text(json.dumps({"corpus": corpus}), encoding="utf-8")
            evaluate_grid.check_reference_corpus(ref_path, 100)
            with self.assertRaises(SystemExit):
                evaluate_grid.check_reference_corpus(ref_path, 101)
            summary.write_text(json.dumps({"corpus": {**corpus, "parser_version": "0.9"}}), encoding="utf-8")
            with self.assertRaises(SystemExit):  # 청크 수가 같아도 버전이 다르면 중단
                evaluate_grid.check_reference_corpus(ref_path, 100)


if __name__ == "__main__":
    unittest.main()
