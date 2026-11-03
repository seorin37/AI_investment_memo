"""DB·모델·파일 없이 합성 벡터만 사용하는 클러스터링 단위 테스트."""

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import combinations, permutations

import pytest

from backend.pipelines.news.clustering import (
    DEFAULT_THRESHOLD, NewsArticle, cluster_articles, cosine_similarity,
)


BASE = datetime(2026, 10, 22, 0, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))


def vector(angle=0, scale=1):
    radians = math.radians(angle)
    return [scale * math.cos(radians), scale * math.sin(radians)] + [0.0] * 1022


def article(news_id, angle=0, *, hours=0, scale=1):
    return NewsArticle(news_id, f"기사 {news_id}", f"언론사 {news_id}",
                       BASE + timedelta(hours=hours), vector(angle, scale))


def group_ids(result):
    return [c.article_ids for c in result.clusters]


def test_similar_pair_uses_actual_norm_and_returns_preview():
    result = cluster_articles([article(1, scale=3), article(2, angle=10, scale=7)])
    assert group_ids(result) == [(1, 2)]
    group = result.clusters[0]
    assert group.article_count == 2
    assert group.min_similarity == pytest.approx(math.cos(math.radians(10)))
    assert group.representative.news_id == 1
    assert group.representative.title == "기사 1"
    assert group.representative.publisher == "언론사 1"
    assert not hasattr(group.representative, "dense")
    assert result.missing_embedding_ids == ()


def test_unrelated_pair_stays_singletons():
    result = cluster_articles([article(1), article(2, angle=90)])
    assert group_ids(result) == [(1,), (2,)]
    assert all(c.article_count == 1 and c.min_similarity is None for c in result.clusters)


def test_experimental_default_can_be_overridden():
    articles = [article(1), article(2, angle=49)]
    assert group_ids(cluster_articles(articles)) == [(1, 2)]
    assert group_ids(cluster_articles(articles, threshold=0.7)) == [(1,), (2,)]


def test_threshold_boundary_is_inclusive_without_extra_tolerance():
    a, b = article(1), article(2, angle=45)
    boundary = cosine_similarity(a.dense, b.dense)
    assert group_ids(cluster_articles([a, b], threshold=boundary)) == [(1, 2)]
    above = math.nextafter(boundary, math.inf)
    assert group_ids(cluster_articles([a, b], threshold=above)) == [(1,), (2,)]
    below = math.nextafter(boundary, -math.inf)
    assert group_ids(cluster_articles([a, b], threshold=below)) == [(1, 2)]


def test_similarity_chain_does_not_join_all_three():
    articles = [article(1), article(2, angle=40), article(3, angle=80)]
    assert cosine_similarity(articles[0].dense, articles[1].dense) >= DEFAULT_THRESHOLD
    assert cosine_similarity(articles[1].dense, articles[2].dense) >= DEFAULT_THRESHOLD
    assert cosine_similarity(articles[0].dense, articles[2].dense) < DEFAULT_THRESHOLD
    result = cluster_articles(articles)
    assert sorted(c.article_count for c in result.clusters) == [1, 2]


def test_complete_link_merges_strongest_pair_first():
    result = cluster_articles([article(1), article(2, angle=40), article(3, angle=60)])
    assert group_ids(result) == [(1,), (2, 3)]


def test_all_pairs_in_each_result_satisfy_similarity_and_time_conditions():
    articles = [article(i + 1, angle=angle, hours=i / 2)
                for i, angle in enumerate([0, 15, 35, 70, 90, 110, 180])]
    by_id = {a.news_id: a for a in articles}
    result = cluster_articles(articles, threshold=0.7, max_time_gap=timedelta(hours=1))
    assert sorted(i for c in result.clusters for i in c.article_ids) == sorted(by_id)
    for group in result.clusters:
        scores = []
        for a, b in combinations(group.article_ids, 2):
            score = cosine_similarity(by_id[a].dense, by_id[b].dense)
            assert score >= 0.7
            assert abs(by_id[a].published_at - by_id[b].published_at) <= timedelta(hours=1)
            scores.append(score)
        assert group.min_similarity == (min(scores) if scores else None)


@pytest.mark.parametrize("second", [article(1), replace(article(1), title="다른 제목"),
                                   replace(article(1), dense=None)])
def test_duplicate_id_is_rejected_even_if_metadata_or_embedding_differs(second):
    with pytest.raises(ValueError, match="duplicate news_id: 1"):
        cluster_articles([article(1), second])


@pytest.mark.parametrize("bad_id", [0, -1, True, "1", 1.5])
def test_invalid_id_is_rejected(bad_id):
    with pytest.raises(ValueError, match="news_id"):
        cluster_articles([replace(article(1), news_id=bad_id)])


@pytest.mark.parametrize("bad_vector", [
    [], [1.0] * 1023, [1.0] * 1025, [0.0] * 1024,
    [float("nan")] + [0.0] * 1023,
    [float("inf")] + [0.0] * 1023,
    [float("-inf")] + [0.0] * 1023,
    [True] * 1024, ["1"] * 1024, "x" * 1024, 5,
    dict.fromkeys(range(1024), 0.1), set(range(1024)),
])
def test_invalid_dense_is_rejected_instead_of_silently_skipped(bad_vector):
    with pytest.raises(ValueError, match="news_id=1: invalid dense"):
        cluster_articles([replace(article(1), dense=bad_vector)])
    with pytest.raises(ValueError):
        cosine_similarity(vector(), bad_vector)


def test_representative_is_earliest_article_not_smallest_id():
    result = cluster_articles([article(1, hours=2), article(9, hours=1), article(3, hours=3)])
    assert group_ids(result) == [(1, 3, 9)]
    assert result.clusters[0].representative.news_id == 9


def test_same_time_representative_tie_break_uses_smallest_id():
    a = article(10)
    b = replace(article(2), published_at=BASE.astimezone(KST))
    group = cluster_articles([a, b]).clusters[0]
    assert group.representative.news_id == 2
    assert group.representative.published_at == BASE
    assert group.representative.published_at.tzinfo == timezone.utc


def test_time_window_inclusive_and_can_be_disabled():
    a, b = article(1), article(2, hours=24)
    assert group_ids(cluster_articles([a, b])) == [(1, 2)]
    b = replace(b, published_at=b.published_at + timedelta(microseconds=1))
    assert group_ids(cluster_articles([a, b])) == [(1,), (2,)]
    assert group_ids(cluster_articles([a, b], max_time_gap=None)) == [(1, 2)]


def test_time_chain_does_not_join_group_exceeding_window():
    result = cluster_articles([article(1), article(2, hours=1), article(3, hours=2)],
                              max_time_gap=timedelta(hours=1))
    assert group_ids(result) == [(1, 2), (3,)]


def test_zero_time_window_allows_only_same_instant_across_timezones():
    a = article(1)
    b = replace(article(2), published_at=BASE.astimezone(KST))
    c = replace(article(3), published_at=BASE + timedelta(microseconds=1))
    assert group_ids(cluster_articles([a, b, c], max_time_gap=timedelta(0))) == [(1, 2), (3,)]


@pytest.mark.parametrize("published", [None, "2026-10-22", datetime(2026, 10, 22)])
def test_missing_or_naive_publication_time_is_rejected(published):
    with pytest.raises(ValueError, match="timezone-aware"):
        cluster_articles([replace(article(1), published_at=published)])


def test_timezone_conversion_overflow_is_reported_as_invalid_input():
    published = datetime.max.replace(tzinfo=timezone(timedelta(hours=-14)))
    with pytest.raises(ValueError, match="news_id=1: published_at"):
        cluster_articles([replace(article(1), published_at=published)])


def test_singleton_and_empty_input():
    result = cluster_articles([article(5)])
    assert group_ids(result) == [(5,)]
    assert result.clusters[0].article_count == 1
    assert result.clusters[0].min_similarity is None
    empty = cluster_articles([])
    assert empty.clusters == () and empty.missing_embedding_ids == ()


def test_missing_embeddings_reported_separately_and_sorted():
    result = cluster_articles([replace(article(9), dense=None), article(1),
                               replace(article(3), dense=None)])
    assert group_ids(result) == [(1,)]
    assert result.missing_embedding_ids == (3, 9)
    result = cluster_articles([replace(article(9), dense=None)])
    assert result.clusters == () and result.missing_embedding_ids == (9,)


def test_input_permutations_produce_identical_results_including_ties():
    articles = [article(4), article(1), article(3, angle=90), article(2, angle=90)]
    expected = cluster_articles(articles)
    assert group_ids(expected) == [(1, 4), (2, 3)]
    for ordering in permutations(articles):
        assert cluster_articles(ordering) == expected


def test_chain_permutations_are_stable():
    articles = [article(1), article(2, angle=40), article(3, angle=80)]
    expected = cluster_articles(articles)
    for ordering in permutations(articles):
        assert cluster_articles(ordering) == expected


def test_input_is_not_modified_and_generator_is_supported():
    articles = [article(2, scale=7), article(1, scale=3)]
    before = [(a.news_id, a.published_at, list(a.dense)) for a in articles]
    expected = cluster_articles(articles)
    assert cluster_articles(a for a in articles) == expected
    assert [(a.news_id, a.published_at, list(a.dense)) for a in articles] == before


@pytest.mark.parametrize("threshold", [-1.1, 1.1, float("nan"), float("inf"), True, "0.65", None])
def test_invalid_threshold_is_rejected(threshold):
    with pytest.raises(ValueError, match="threshold"):
        cluster_articles([], threshold=threshold)


def test_extreme_valid_thresholds_and_cosine_values():
    assert cosine_similarity(vector(scale=2), vector(scale=7)) == 1.0
    assert cosine_similarity(vector(), [-x for x in vector()]) == -1.0
    assert group_ids(cluster_articles([article(1), article(2)], threshold=1)) == [(1, 2)]
    assert group_ids(cluster_articles([article(1), article(2, angle=180)], threshold=-1)) == [(1, 2)]


@pytest.mark.parametrize("window", [timedelta(microseconds=-1), 24, "24h", True])
def test_invalid_time_window_is_rejected(window):
    with pytest.raises(ValueError, match="max_time_gap"):
        cluster_articles([], max_time_gap=window)


@pytest.mark.parametrize("field,value", [("title", ""), ("title", None),
                                        ("publisher", " "), ("publisher", None)])
def test_missing_display_metadata_is_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        cluster_articles([replace(article(1), **{field: value})])
