"""DB·모델·네트워크 없이 합성 1,024차원 벡터를 사용하는 연결 계층 테스트."""
import builtins
from collections import UserDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from itertools import permutations
import json
import math
import socket

import pytest

from backend.pipelines.news import preview
from backend.pipelines.news.clustering import NewsArticle, cluster_articles, cosine_similarity

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))


def row(news_id, angle=0, *, hours=0, scale=1):
    radians = math.radians(angle)
    return {
        "news_id": news_id, "title": f"합성 기사 {news_id}", "publisher": f"매체 {news_id}",
        "published_at": BASE + timedelta(hours=hours), "url": f"https://example.test/news/{news_id}",
        "model": "BAAI/bge-m3", "variant": "hybrid",
        "dense": [scale * math.cos(radians), scale * math.sin(radians)] + [0.0] * 1022,
    }


def missing_row(news_id):
    return {**row(news_id), "dense": None, "model": None, "variant": None}


def ids(report):
    return [group["article_ids"] for group in report["groups"]]


def test_valid_rows_delegate_once_and_preserve_existing_group_results(monkeypatch):
    rows = [row(3, 90), row(2, 10, scale=7), row(1, hours=1, scale=3)]
    calls = []
    def spy(articles, **options):
        calls.append((articles, options))
        return cluster_articles(articles, **options)
    monkeypatch.setattr(preview, "cluster_articles", spy)
    result = preview.preview_articles(rows)
    assert len(calls) == 1
    articles, options = calls[0]
    assert [a.news_id for a in articles] == [1, 2, 3]
    assert all(isinstance(a, NewsArticle) and isinstance(a.dense, tuple) for a in articles)
    assert options == {"threshold": 0.65, "max_time_gap": timedelta(hours=24)}
    expected = cluster_articles(articles, **options)
    assert ids(result) == [list(c.article_ids) for c in expected.clusters]
    assert [g["representative_id"] for g in result["groups"]] == [c.representative.news_id for c in expected.clusters]
    assert [g["min_similarity"] for g in result["groups"]] == [c.min_similarity for c in expected.clusters]
    assert result["input_article_count"] == result["processed_article_count"] == 3
    assert result["preview"] is True
    assert result["settings"]["similarity_metric"] == "dense_cosine"
    assert result["settings"]["threshold_status"] == "experimental"


def test_metadata_json_and_singleton_null_without_vector_exposure():
    rows = [row(1, hours=1), row(2, 5), row(3, 90)]
    result = preview.preview_articles(rows)
    assert ids(result) == [[1, 2], [3]]
    group = result["groups"][0]
    assert group["representative_id"] == 2 and group["article_count"] == 2
    assert group["representative"] == {
        "news_id": 2, "title": "합성 기사 2", "publisher": "매체 2",
        "published_at": BASE.isoformat(), "url": "https://example.test/news/2",
    }
    assert [a["news_id"] for a in group["articles"]] == [1, 2]
    assert all(a["url"] and a["title"] and a["publisher"] for a in group["articles"])
    assert result["groups"][1]["min_similarity"] is None
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
    assert json.loads(encoded) == result
    assert '"dense":' not in encoded and '"sparse":' not in encoded
    assert "event_id" not in encoded and "generated_at" not in encoded


def test_representative_tie_and_timezone_are_core_rules():
    first = row(9)
    second = {**row(3), "published_at": BASE.astimezone(KST)}
    result = preview.preview_articles([first, second])
    assert result["groups"][0]["representative_id"] == 3
    assert all(a["published_at"] == BASE.isoformat() for a in result["groups"][0]["articles"])


def test_only_valid_embeddings_are_passed_and_missing_ids_are_sorted(monkeypatch):
    calls = []
    def spy(articles, **options):
        calls.append(articles)
        return cluster_articles(articles, **options)
    monkeypatch.setattr(preview, "cluster_articles", spy)
    result = preview.preview_articles([missing_row(9), row(2), missing_row(1)])
    assert [a.news_id for a in calls[0]] == [2]
    assert result["input_article_count"] == 3 and result["processed_article_count"] == 1
    assert result["missing_embedding_ids"] == [1, 9]
    assert ids(result) == [[2]]


@pytest.mark.parametrize("rows", [[], [missing_row(2), missing_row(1)]])
def test_empty_or_all_missing_has_no_groups(rows):
    result = preview.preview_articles(rows)
    assert result["groups"] == []
    assert result["input_article_count"] == len(rows)
    assert result["processed_article_count"] == 0
    assert result["missing_embedding_ids"] == sorted(r["news_id"] for r in rows)


@pytest.mark.parametrize("change", [
    {"dense": None}, {"dense": None, "model": None}, {"dense": None, "variant": None},
    {"dense": None, "model": "other-model", "variant": None},
])
def test_partial_null_embedding_is_not_silently_reported_as_missing(change):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), **change}])
    assert caught.value.code == "inconsistent_embedding"


@pytest.mark.parametrize("bad", [
    [], [1.0] * 1023, [1.0] * 1025, [0.0] * 1024,
    [math.nan] + [0.0] * 1023, [math.inf] + [0.0] * 1023,
    [-math.inf] + [0.0] * 1023, [True] + [0.0] * 1023,
    ["1"] + [0.0] * 1023, [None] + [0.0] * 1023,
    [1.7e308] * 1024, "[1,0]", {0: 1.0}, 1,
])
def test_bad_dense_is_rejected_before_clustering(bad, monkeypatch):
    monkeypatch.setattr(preview, "cluster_articles", lambda *a, **k: pytest.fail("invalid input reached clustering"))
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), "dense": bad}])
    assert caught.value.code == "invalid_dense"
    assert caught.value.news_id == 1 and caught.value.field == "dense"


@pytest.mark.parametrize("field", [
    "news_id", "title", "publisher", "published_at", "url", "model", "variant", "dense",
])
def test_each_required_field_must_be_present_even_for_missing_embedding(field):
    article = missing_row(1)
    del article[field]
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([article])
    assert caught.value.code == "missing_fields"
    assert field in caught.value.reason


@pytest.mark.parametrize("field,bad", [
    ("title", None), ("title", ""), ("title", "  "),
    ("publisher", None), ("publisher", " "), ("publisher", 1),
    ("url", None), ("url", ""), ("url", 1),
])
def test_required_metadata_values_are_validated(field, bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), field: bad}])
    assert caught.value.code == "invalid_metadata" and caught.value.field == field


@pytest.mark.parametrize("bad", [
    "not-a-url", "/news/1", "ftp://example.test/news/1", "https:///news/1",
    "https://user:password@example.test/news/1", "https://example.test:invalid/1",
    "https://example.test/a\nb", "https://[broken/1",
])
def test_invalid_urls_are_rejected_without_requesting_them(bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), "url": bad}])
    assert caught.value.code == "invalid_url"


@pytest.mark.parametrize("bad", [BASE.replace(tzinfo=None), None, BASE.isoformat(), "2026-01-01", 1])
def test_invalid_or_naive_timestamp_is_rejected(bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), "published_at": bad}])
    assert caught.value.code == "invalid_published_at"


@pytest.mark.parametrize("field,bad,code", [
    ("model", "other-model", "model_mismatch"), ("model", None, "model_mismatch"),
    ("model", "", "model_mismatch"), ("variant", "dense", "variant_mismatch"),
    ("variant", None, "variant_mismatch"), ("variant", "HYBRID", "variant_mismatch"),
])
def test_model_and_variant_must_match_existing_hybrid_contract(field, bad, code):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), field: bad}])
    assert caught.value.code == code


@pytest.mark.parametrize("second", [row(1), missing_row(1), {**row(1), "title": "다른 제목"}])
def test_duplicate_ids_are_rejected_including_missing_embeddings(second):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([row(1), second])
    assert caught.value.code == "duplicate_news_id" and caught.value.news_id == 1


@pytest.mark.parametrize("bad", [0, -1, True, "1", 1.5, None])
def test_invalid_article_ids_are_rejected(bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(1), "news_id": bad}])
    assert caught.value.code == "invalid_news_id"


@pytest.mark.parametrize("options", [
    {"threshold": True}, {"threshold": "0.65"}, {"threshold": None},
    {"threshold": math.nan}, {"threshold": math.inf}, {"threshold": -1.1}, {"threshold": 1.1},
    {"threshold": 10 ** 1000},
    {"max_time_gap": -timedelta(seconds=1)}, {"max_time_gap": 86400}, {"max_time_gap": True},
    {"max_articles": 0}, {"max_articles": -1}, {"max_articles": True},
    {"max_articles": 1.5}, {"max_articles": None},
])
def test_invalid_execution_options_fail_even_on_empty_input(options):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([], **options)
    assert caught.value.code == "invalid_option"


@pytest.mark.parametrize("bad", [None, "rows", b"rows", {}, 1])
def test_top_level_input_must_be_an_iterable_of_rows(bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles(bad)
    assert caught.value.code == "invalid_rows"


@pytest.mark.parametrize("bad", [None, (), [], "row", 1])
def test_each_row_must_be_a_named_mapping(bad):
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([bad])
    assert caught.value.code == "invalid_row"


def test_article_limit_counts_missing_and_stops_an_unbounded_iterator(monkeypatch):
    consumed = []
    def many():
        for i in range(1, 1000):
            consumed.append(i)
            yield missing_row(i)
    monkeypatch.setattr(preview, "cluster_articles", lambda *a, **k: pytest.fail("over-limit input reached clustering"))
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles(many(), max_articles=2)
    assert caught.value.code == "article_limit_exceeded" and consumed == [1, 2, 3]
    assert preview.DEFAULT_MAX_ARTICLES == 100


def test_exact_limit_and_mapping_generator_are_supported():
    result = preview.preview_articles((UserDict(row(i)) for i in (2, 1)), max_articles=2)
    assert ids(result) == [[1, 2]] and result["settings"]["max_articles"] == 2


def test_thresholds_use_actual_norm_and_inclusive_core_boundary():
    rows = [row(1, scale=3), row(2, 49, scale=7)]
    assert ids(preview.preview_articles(rows, threshold=0.65)) == [[1, 2]]
    assert ids(preview.preview_articles(rows, threshold=0.70)) == [[1], [2]]
    boundary = cosine_similarity(rows[0]["dense"], rows[1]["dense"])
    assert ids(preview.preview_articles(rows, threshold=boundary)) == [[1, 2]]
    assert ids(preview.preview_articles(rows, threshold=math.nextafter(boundary, math.inf))) == [[1], [2]]


def test_chain_is_not_merged_as_a_connected_component():
    result = preview.preview_articles([row(1), row(2, 40), row(3, 80)])
    assert sorted(g["article_count"] for g in result["groups"]) == [1, 2]


def test_time_limit_can_be_changed_or_disabled():
    rows = [row(1), row(2, hours=25)]
    assert ids(preview.preview_articles(rows)) == [[1], [2]]
    assert ids(preview.preview_articles(rows, max_time_gap=timedelta(hours=25))) == [[1, 2]]
    unlimited = preview.preview_articles(rows, max_time_gap=None)
    assert ids(unlimited) == [[1, 2]] and unlimited["settings"]["max_time_gap_seconds"] is None
    assert ids(preview.preview_articles(rows, max_time_gap=timedelta(0))) == [[1], [2]]


def test_result_is_deterministic_for_repeats_and_input_permutations():
    rows = [row(3, 90), missing_row(4), row(1), row(2, 5)]
    expected = preview.preview_articles(rows)
    assert preview.preview_articles(rows) == expected
    for order in permutations(rows):
        assert preview.preview_articles(order) == expected
    assert json.dumps(preview.preview_articles(rows), sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_inputs_and_following_calls_are_independent_of_output_mutation():
    rows = [row(1), row(2, 5)]
    rows[0]["sparse"] = {"not-used": 1e100}
    before = deepcopy(rows)
    first = preview.preview_articles(rows)
    expected = deepcopy(first)
    first["groups"][0]["representative"]["title"] = "응답 변경"
    first["groups"][0]["articles"][0]["url"] = "https://example.test/changed"
    first["groups"][0]["article_ids"].append(999)
    assert rows == before
    assert preview.preview_articles(rows) == expected
    assert rows == before


def test_all_rows_are_validated_before_any_clustering(monkeypatch):
    monkeypatch.setattr(preview, "cluster_articles", lambda *a, **k: pytest.fail("partial result not allowed"))
    with pytest.raises(preview.PreviewValidationError):
        preview.preview_articles([row(1), {**row(2), "dense": [0.0]}])


def test_validation_error_has_serializable_type_reason_and_context():
    with pytest.raises(preview.PreviewValidationError) as caught:
        preview.preview_articles([{**row(7), "dense": [0.0]}])
    error = caught.value.as_dict()
    assert isinstance(caught.value, ValueError)
    assert error["error_type"] == "PreviewValidationError" and error["code"] == "invalid_dense"
    assert error["news_id"] == 7 and error["row_index"] == 0 and error["field"] == "dense"
    assert error["reason"] and str(caught.value) == error["reason"]
    assert json.loads(json.dumps(error, allow_nan=False)) == error


def test_unexpected_core_failure_is_not_hidden(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic core failure")
    monkeypatch.setattr(preview, "cluster_articles", fail)
    with pytest.raises(RuntimeError, match="synthetic core failure"):
        preview.preview_articles([row(1)])


def test_preview_runs_when_db_network_and_model_access_are_forbidden(monkeypatch):
    original_import = builtins.__import__
    blocked = {"psycopg", "psycopg2", "sqlalchemy", "FlagEmbedding", "torch", "transformers",
               "requests", "feedparser", "dotenv"}
    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in blocked:
            pytest.fail("DB, model or network client imported")
        return original_import(name, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail("network access attempted")
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = preview.preview_articles([row(1), row(2, 5), missing_row(3)])
    assert ids(result) == [[1, 2]] and result["missing_embedding_ids"] == [3]
