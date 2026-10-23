import pytest

from backend.pipelines.news import evaluate as ev


def test_minmax_and_ties():
    assert ev.minmax([1, 3, 2]) == [0.0, 1.0, 0.5]
    assert ev.minmax([2, 2]) == [0.0, 0.0]


def test_metrics():
    ranked = ["a", "b", "c", "d"]
    assert ev.recall_at_k(ranked, {"b", "z"}, 2) == pytest.approx(0.5)
    assert ev.reciprocal_rank(ranked, {"c"}) == pytest.approx(1 / 3)
    assert ev.reciprocal_rank(ranked, {"z"}) == 0.0
    assert ev.ndcg_at_k(["a", "b"], {"a", "b"}, 2) == pytest.approx(1.0)
    assert ev.ndcg_at_k(["x", "a"], {"a"}, 2) == pytest.approx(1 / 1.5849625, rel=1e-4)


def test_combine_weights_and_norm():
    d, s = [0.2, 0.8], [10.0, 0.0]
    assert ev.combine(d, s, (1, 0), "none") == [0.2, 0.8]          # dense만
    assert ev.combine(d, s, (0, 1), "none") == [10.0, 0.0]         # sparse만
    assert ev.combine(d, s, (0.5, 0.5), "minmax") == [0.5, 0.5]    # 둘 다 0~1로 맞춘 뒤 합
    with pytest.raises(ValueError):
        ev.combine(d, s, (1, 0), "x")


def test_evaluate_picks_up_weight_effect():
    docs = [ev.Doc(1, "u1", "t1", [1.0, 0.0], {"x": 1.0}),
            ev.Doc(2, "u2", "t2", [0.0, 1.0], {"y": 1.0})]
    queries = [{"id": "q1", "query": "q", "relevant": {"u1"}}]
    encoded = [([0.0, 1.0], {"x": 1.0})]   # dense는 u2를, sparse는 u1을 가리킨다
    rows = ev.evaluate(queries, docs, encoded, [(1, 0), (0, 1)], ["none"], [1])
    by_w = {r["weight"]: r for r in rows}
    assert by_w["1:0"]["MRR"] == pytest.approx(0.5)
    assert by_w["0:1"]["MRR"] == pytest.approx(1.0)
    assert by_w["0:1"]["Recall@1"] == 1.0


def test_relevant_missing_from_pool_counts_as_a_miss_not_removed():
    # 정답 u1, u2 중 u2는 검색 풀에 없다 (예: 태그가 없어 --only-tagged에서 빠짐). 100%가 아니라 50%여야 한다.
    docs = [ev.Doc(1, "u1", "t", [1.0], {})]
    rows = ev.evaluate([{"id": "q", "query": "q", "relevant": {"u1", "u2"}}], docs, [([1.0], {})],
                       [(1, 0)], ["none"], [1, 5])
    assert rows[0]["queries"] == 1
    assert rows[0]["Recall@5"] == pytest.approx(0.5)


def test_query_whose_relevant_are_all_missing_scores_zero():
    docs = [ev.Doc(1, "u1", "t", [1.0], {})]
    rows = ev.evaluate([{"id": "q", "query": "q", "relevant": {"missing"}}], docs, [([1.0], {})],
                       [(1, 0)], ["none"], [1])
    assert rows[0]["queries"] == 1 and rows[0]["MRR"] == 0.0 and rows[0]["Recall@1"] == 0.0


def test_query_with_no_labels_is_skipped():
    docs = [ev.Doc(1, "u1", "t", [1.0], {})]
    rows = ev.evaluate([{"id": "q", "query": "q", "relevant": set()}], docs, [([1.0], {})],
                       [(1, 0)], ["none"], [1])
    assert rows[0]["queries"] == 0


def test_pool_coverage_reports_labels_outside_pool():
    docs = [ev.Doc(1, "u1", "t", [1.0], {})]
    assert ev.pool_coverage([{"id": "q", "relevant": {"u1", "u2"}}], docs) == [("q", 2, 1)]
