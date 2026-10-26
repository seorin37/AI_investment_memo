"""합성 기사·벡터와 임시 라벨 파일만 사용한다. DB·모델·네트워크 사용 금지."""

import csv
import json
import math
import shutil
from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.pipelines.news import evaluate_clustering as evaluation
from backend.pipelines.news.clustering import NewsArticle

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW = {"confidence": "high", "review_status": "approved",
          "reviewed_at": "2026-01-02T00:00:00+00:00", "reviewer": "synthetic-reviewer",
          "split": "development", "reason": "합성 테스트 근거"}


def annotation(i, **kwargs):
    return replace(evaluation.ArticleLabel(
        article_id=i, title=f"합성 기사 {i}", publisher="합성 언론사",
        published_at=BASE.isoformat(), article_type="single_event",
        information_quality=("summary_available",),
        source_url=f"https://example.test/article/{i}", **REVIEW), **kwargs)


def group(*ids, event_id="E_TEST", **kwargs):
    return replace(evaluation.EventGroup(
        event_id=event_id, event_description="합성 사건", member_ids=tuple(ids),
        event_time="합성 사건 시점", evidence_urls=("https://example.test/event",),
        **REVIEW), **kwargs)


def pair(a, b, relation="different_event", **kwargs):
    return replace(evaluation.PairLabel(
        article_id_a=a, article_id_b=b, relation=relation, scope="whole_article",
        evidence_urls=("https://example.test/pair",), **REVIEW), **kwargs)


def labels(ids=(1, 2), groups=(), pairs=(), annotations=None):
    return evaluation.LabelSet(
        tuple(annotations) if annotations is not None else tuple(annotation(i) for i in ids),
        tuple(groups), tuple(pairs))


def article(i, angle=0, **kwargs):
    radians = math.radians(angle)
    return replace(NewsArticle(i, f"합성 기사 {i}", "합성 언론사", BASE,
                              [math.cos(radians), math.sin(radians)] + [0.0] * 1022),
                   **kwargs)


def write_labels(tmp_path, dataset):
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name, records, kind in [
        ("articles.csv", dataset.articles, evaluation.ArticleLabel),
        ("pair_labels.csv", dataset.pairs, evaluation.PairLabel),
    ]:
        with (tmp_path / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[f.name for f in fields(kind)])
            writer.writeheader()
            for item in records:
                row = asdict(item)
                for key in ("information_quality", "evidence_urls"):
                    if key in row:
                        row[key] = "|".join(row[key])
                writer.writerow(row)
    (tmp_path / "event_groups.json").write_text(json.dumps({
        "schema_version": 1, "dataset_id": "synthetic", "label_policy_version": "1",
        "note": "합성 테스트", "groups": [asdict(g) for g in dataset.groups],
    }), encoding="utf-8")
    return tmp_path


def unapproved(record, status="proposed"):
    return replace(record, review_status=status, reviewed_at="", reviewer="")


def test_seed_files_reflect_only_nine_human_approvals(tmp_path, monkeypatch):
    """실제 개발용 후보에는 사람이 승인한 9개 레코드만 반영돼야 한다."""
    seed = Path(evaluation.__file__).with_name("evaluation")
    for name in ("articles.csv", "pair_labels.csv", "event_groups.json"):
        shutil.copyfile(seed / name, tmp_path / name)
    dataset = evaluation.load_labels(tmp_path)
    assert len(dataset.articles) == 28
    assert len(dataset.groups) == 8
    assert len(dataset.pairs) == 5
    approved_groups = {g.event_id: g.member_ids for g in dataset.groups
                       if g.review_status == "approved"}
    assert approved_groups == {
        "E_HANWHA_001": (36, 175),
        "E_SEONGNAM_001": (14, 254),
        "E_BUKANG_001": (76, 245),
    }
    approved_articles = {a.article_id for a in dataset.articles
                         if a.review_status == "approved"}
    assert approved_articles == {14, 36, 76, 175, 245, 254}
    assert all(p.review_status != "approved" for p in dataset.pairs)
    records = (*dataset.articles, *dataset.groups, *dataset.pairs)
    approved = [r for r in records if r.review_status == "approved"]
    pending = [r for r in records if r.review_status != "approved"]
    assert len(records) == 41 and len(approved) == 9 and len(pending) == 32
    assert all(r.reviewer == "yebin" for r in approved)
    assert len({r.reviewed_at for r in approved}) == 1
    for record in approved:
        recorded_at = datetime.fromisoformat(record.reviewed_at)
        assert recorded_at.utcoffset() is not None
    assert all(r.review_status in {"proposed", "needs_review"}
               and r.reviewed_at == "" and r.reviewer == "" for r in pending)
    assert all(r.split == "development" for r in records)
    assert sum(p.relation == "different_event" for p in dataset.pairs) == 4
    boundary = next(p for p in dataset.pairs
                    if (p.article_id_a, p.article_id_b) == (15, 22))
    assert boundary.relation == "undecided" and boundary.review_status == "needs_review"
    assert {a.article_id for a in dataset.articles
            if a.article_type == "multi_event_briefing"} == {16, 22}

    def forbidden(*args, **kwargs):
        pytest.fail("실제 후보의 벡터 없는 상태에서 군집 계산 금지")
    monkeypatch.setattr(evaluation, "cluster_articles", forbidden)
    # 실제 기사 벡터를 주지 않으므로 성능을 계산하지 않는다.
    report = evaluation.evaluate_articles([], dataset)
    assert report["label_summary"]["approved_groups"] == 3
    assert report["label_summary"]["approved_relations"] == 3
    assert report["status"] == "평가 불가: 평가 가능한 승인 관계 없음"
    assert report["results"] == []
    assert "metrics" not in report
    assert report["exclusions"]["article_annotations"]["reason_counts"]["multi_event_briefing"] == 2
    assert report["provenance"]["dataset_id"] == "news-clustering-development-v1"
    assert report["provenance"]["label_policy_version"] == "1"


def test_file_loading_roundtrip_with_synthetic_files(tmp_path):
    expected = labels(groups=[group(1, 2)], pairs=[pair(2, 1, "same_event")])
    loaded = evaluation.load_labels(write_labels(tmp_path, expected))
    assert replace(loaded, metadata=None) == evaluation.validate_labels(expected)
    assert loaded.metadata.dataset_id == "synthetic"


@pytest.mark.parametrize("change", [
    {"article_id": 0}, {"article_id": True}, {"article_type": "unknown"},
    {"review_status": "automatic"}, {"confidence": "certain"}, {"reviewer": ""},
    {"reviewed_at": ""}, {"reviewed_at": "2026-01-01"},
    {"published_at": "2026-01-01"}, {"published_at": "bad"},
    {"source_url": "file:///tmp/article"}, {"source_url": "https://name:secret@example.test"},
    {"information_quality": ("unknown",)}, {"title": ""}, {"split": "test"},
])
def test_invalid_article_annotations_rejected(change):
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.validate_labels(labels(annotations=[annotation(1, **change), annotation(2)]))


@pytest.mark.parametrize("file_name", ["articles.csv", "pair_labels.csv"])
def test_malformed_csv_headers_rejected(tmp_path, file_name):
    write_labels(tmp_path, labels())
    (tmp_path / file_name).write_text("wrong,header\n1,2\n", encoding="utf-8")
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.load_labels(tmp_path)


@pytest.mark.parametrize("text", [
    "{bad", '{"schema_version":1,"schema_version":1}',
    '{"schema_version":99,"dataset_id":"x","label_policy_version":"1","note":"x","groups":[]}',
    '{"schema_version":1,"dataset_id":"x","label_policy_version":"1","note":"x","groups":{}}',
])
def test_malformed_json_rejected(tmp_path, text):
    write_labels(tmp_path, labels())
    (tmp_path / "event_groups.json").write_text(text, encoding="utf-8")
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.load_labels(tmp_path)


def test_duplicate_article_annotations_rejected():
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.validate_labels(labels(annotations=[annotation(1), annotation(1)]))


@pytest.mark.parametrize("groups", [
    [group(1, 2), group(3, 4)],
    [group(1, 2), group(2, 3, event_id="E_OTHER")],
    [group(1, 1)], [group(1, 5)], [group(1)],
])
def test_invalid_or_overlapping_groups_rejected(groups):
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.validate_labels(labels((1, 2, 3, 4), groups=groups))


def test_reverse_pair_duplicate_removed_and_group_positive_not_counted_twice():
    dataset = labels(groups=[group(1, 2)],
                     pairs=[pair(1, 2, "same_event"), pair(2, 1, "same_event")])
    checked = evaluation.validate_labels(dataset)
    assert len(checked.pairs) == 1
    report = evaluation.evaluate_articles([article(1), article(2)], checked)
    assert report["label_summary"]["approved_relations"] == 1
    assert report["results"][0]["counts"] == {"TP": 1, "FP": 0, "FN": 0, "TN": 0}


@pytest.mark.parametrize("dataset", [
    labels(pairs=[pair(1, 2), pair(2, 1, "same_event")]),
    labels(groups=[group(1, 2)], pairs=[pair(1, 2)]),
    labels((1, 2, 3), pairs=[pair(1, 2, "same_event"), pair(2, 3, "same_event"), pair(1, 3)]),
    labels((1, 2, 3, 4), groups=[group(1, 2), group(3, 4, event_id="E_OTHER")],
           pairs=[pair(2, 3, "same_event")]),
])
def test_contradiction_stops_evaluation_before_clustering(dataset, monkeypatch):
    monkeypatch.setattr(evaluation, "cluster_articles",
                        lambda *a, **k: pytest.fail("모순 상태에서 군집 계산 금지"))
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.evaluate_articles([], dataset)


def test_duplicate_pair_with_different_approval_is_not_silently_merged():
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.validate_labels(labels(pairs=[pair(1, 2), unapproved(pair(2, 1))]))


def test_rejected_relation_does_not_contradict_active_group():
    checked = evaluation.validate_labels(labels(
        groups=[group(1, 2)], pairs=[pair(1, 2, review_status="rejected")]))
    assert len(checked.groups) == 1


@pytest.mark.parametrize("dataset", [
    labels(groups=[group(1, 2, split="holdout")]),
    labels(pairs=[pair(1, 2, split="holdout")]),
    labels(annotations=[annotation(1), annotation(2, split="holdout")], pairs=[pair(1, 2)]),
])
def test_split_leakage_rejected(dataset):
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.validate_labels(dataset)


def test_only_approved_relations_count():
    dataset = labels((1, 2, 3, 4), groups=[group(1, 2)],
                     pairs=[unapproved(pair(3, 4))])
    report = evaluation.evaluate_articles([article(i) for i in range(1, 5)], dataset)
    assert report["coverage"]["clustered_article_ids"] == [1, 2]
    assert report["results"][0]["counts"]["TP"] == 1
    assert report["results"][0]["counts"]["FP"] == 0


def test_approved_relation_requires_approved_article_annotations():
    dataset = labels(groups=[group(1, 2)],
                     annotations=[unapproved(annotation(1)), annotation(2)])
    report = evaluation.evaluate_articles([article(1), article(2)], dataset)
    assert report["status"] == "평가 불가: 평가 가능한 승인 관계 없음"
    assert report["results"] == []
    assert report["coverage"]["excluded_relation_count"] == 1


def test_undecided_and_representative_event_labels_excluded():
    dataset = labels((1, 2, 3, 4), pairs=[
        pair(1, 2, "undecided"), pair(3, 4, scope="representative_event")])
    report = evaluation.evaluate_articles([], dataset)
    assert report["results"] == []
    assert {r["reason"] for r in report["exclusions"]["pair_labels"]} == {
        "undecided", "representative_event"}


@pytest.mark.parametrize("article_type", ["multi_event_briefing", "insufficient_information"])
def test_non_single_article_excluded_even_if_relation_approved(article_type):
    dataset = labels(pairs=[pair(1, 2)],
                     annotations=[annotation(1, article_type=article_type), annotation(2)])
    report = evaluation.evaluate_articles([article(1), article(2)], dataset)
    assert report["results"] == []
    assert report["exclusions"]["evaluation_requests"]["reason_counts"][article_type] == 1


def test_missing_embedding_excludes_pairs_and_does_not_shrink_group_recall():
    dataset = labels((1, 2, 3), groups=[group(1, 2, 3)])
    report = evaluation.evaluate_articles([article(1), article(2), article(3, dense=None)], dataset)
    assert report["coverage"]["embedding_missing_ids"] == [3]
    assert report["coverage"]["embedding_missing_rate"] == pytest.approx(1 / 3)
    assert report["coverage"]["evaluated_relation_count"] == 1
    assert report["coverage"]["excluded_relation_count"] == 2
    event = report["results"][0]["events"][0]
    assert event["recall"] is None and event["split_count"] is None
    assert event["status"] == "incomplete"
    assert report["results"][0]["event_macro_recall"] is None


def test_missing_article_input_reported_separately():
    report = evaluation.evaluate_articles([article(1)], labels(pairs=[pair(1, 2)]))
    assert report["coverage"]["article_input_missing_ids"] == [2]
    assert report["coverage"]["embedding_missing_ids"] == []
    assert report["results"] == []


@pytest.mark.parametrize("vector", [[1.0], [0.0] * 1024,
                                  [math.nan] + [0.0] * 1023,
                                  [math.inf] + [0.0] * 1023,
                                  [True] + [0.0] * 1023, "bad"])
def test_invalid_vectors_excluded(vector):
    report = evaluation.evaluate_articles([article(1), article(2, dense=vector)],
                                         labels(pairs=[pair(1, 2)]))
    assert report["coverage"]["invalid_embedding_ids"] == [2]
    assert report["results"] == []


def test_naive_article_time_is_validation_error_without_editing_input():
    value = article(2, published_at=datetime(2026, 1, 1))
    with pytest.raises(evaluation.InputValidationError, match="published_at"):
        evaluation.evaluate_articles([article(1), value], labels(pairs=[pair(1, 2)]))
    assert value.published_at.tzinfo is None


def test_duplicate_input_ids_rejected():
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.evaluate_articles([article(1), article(1)], labels(pairs=[pair(1, 2)]))


def test_complete_link_groups_determine_confusion_and_event_statistics():
    dataset = labels(range(1, 7),
                     groups=[group(1, 3, event_id="E_A"), group(2, 4, event_id="E_B"),
                             group(5, 6, event_id="E_C")],
                     pairs=[pair(1, 2), pair(2, 3), pair(3, 4)])
    values = [article(i, angle) for i, angle in enumerate([0, 35, 80, 180, 260, 265], 1)]
    row = evaluation.evaluate_articles(values, dataset, thresholds=[0.65])["results"][0]
    assert row["counts"] == {"TP": 1, "FP": 1, "FN": 2, "TN": 2}
    assert row["false_merges"] == [[1, 2]]
    assert row["false_splits"] == [[1, 3], [2, 4]]
    assert row["metrics"]["precision"] == pytest.approx(0.5)
    assert row["metrics"]["recall"] == pytest.approx(1 / 3)
    assert row["metrics"]["f1"] == pytest.approx(0.4)
    assert row["metrics"]["different_event_separation_rate"] == pytest.approx(2 / 3)
    events = {e["event_id"]: e for e in row["events"]}
    assert events["E_A"]["recall"] == 0 and events["E_A"]["split_count"] == 2
    assert events["E_C"]["recall"] == 1 and events["E_C"]["split_count"] == 1
    assert row["event_macro_recall"] == pytest.approx(1 / 3)
    # 2-3 벡터 점수는 기준 이상이어도 실제 complete-link 결과에서는 서로 분리된다.
    assert not any(2 in c["ids"] and 3 in c["ids"] for c in row["clusters"])


def test_zero_denominators_are_none():
    positive = evaluation.evaluate_articles([article(1), article(2, 180)],
                                            labels(groups=[group(1, 2)]))["results"][0]
    assert positive["metrics"] == {"precision": None, "recall": 0.0, "f1": 0.0,
                                   "different_event_separation_rate": None}
    negative = evaluation.evaluate_articles([article(1), article(2, 180)],
                                            labels(pairs=[pair(1, 2)]))["results"][0]
    assert negative["metrics"] == {"precision": None, "recall": None, "f1": None,
                                   "different_event_separation_rate": 1.0}


def test_lone_star_has_six_positive_pairs_but_one_event():
    ids = (10, 59, 106, 201)
    report = evaluation.evaluate_articles([article(i) for i in ids],
                                         labels(ids, groups=[group(*ids, event_id="E_LONESTAR_001")]))
    assert report["label_summary"]["approved_relations"] == 6
    assert report["label_summary"]["approved_groups"] == 1
    for row in report["results"]:
        assert row["counts"]["TP"] == 6
        assert len(row["events"]) == 1
        assert row["events"][0]["expected_pair_count"] == 6


def test_thresholds_receive_identical_frozen_input_and_time_gap(monkeypatch):
    original = evaluation.cluster_articles
    calls = []
    def spy(articles, **kwargs):
        calls.append((articles, kwargs))
        return original(articles, **kwargs)
    monkeypatch.setattr(evaluation, "cluster_articles", spy)
    values = [article(1), article(2, 49)]
    report = evaluation.evaluate_articles(iter(values), labels(groups=[group(1, 2)]),
                                          max_time_gap=timedelta(hours=12))
    assert [kw["threshold"] for _, kw in calls] == [0.60, 0.65, 0.70]
    assert all(data is calls[0][0] for data, _ in calls)
    assert all(kw["max_time_gap"] == timedelta(hours=12) for _, kw in calls)
    assert [r["counts"]["TP"] for r in report["results"]] == [1, 1, 0]
    assert isinstance(calls[0][0][0].dense, tuple)
    assert isinstance(values[0].dense, list)


def test_time_window_is_not_used_to_remove_same_event_ground_truth():
    report = evaluation.evaluate_articles(
        [article(1), article(2, published_at=BASE + timedelta(hours=25))],
        labels(groups=[group(1, 2)],
               annotations=[annotation(1), annotation(2, published_at=(
                   BASE + timedelta(hours=25)).isoformat())]))
    assert report["results"][0]["counts"]["FN"] == 1


def test_unlabeled_cross_pairs_are_not_negative_or_exact_recovery():
    dataset = labels((1, 2, 3, 4),
                     groups=[group(1, 2), group(3, 4, event_id="E_OTHER")])
    row = evaluation.evaluate_articles([article(i) for i in range(1, 5)], dataset)["results"][0]
    assert len(row["clusters"]) == 1
    assert row["counts"] == {"TP": 2, "FP": 0, "FN": 0, "TN": 0}
    assert row["unlabeled_predicted_merges"] == [[1, 3], [1, 4], [2, 3], [2, 4]]
    assert all(e["exact_group_recovery"] is None for e in row["events"])


def test_positive_pair_transitivity_not_expanded_into_scored_pairs():
    dataset = labels((1, 2, 3), pairs=[pair(1, 2, "same_event"), pair(2, 3, "same_event")])
    row = evaluation.evaluate_articles([article(i) for i in (1, 2, 3)], dataset)["results"][0]
    assert row["counts"]["TP"] == 2
    assert row["unlabeled_predicted_merges"] == [[1, 3]]


def test_unapproved_extra_input_cannot_change_clusters():
    dataset = labels((1, 2, 3), pairs=[pair(1, 2)])
    row = evaluation.evaluate_articles([article(1), article(2, 80), article(3, 40)],
                                       dataset)["results"][0]
    assert row["counts"]["TN"] == 1
    assert row["clustered_article_ids"] == [1, 2]


@pytest.mark.parametrize("kwargs", [
    {"thresholds": []}, {"thresholds": [0.65, 0.65]}, {"thresholds": [True]},
    {"thresholds": [math.nan]}, {"thresholds": [2]}, {"max_time_gap": -1},
    {"max_time_gap": timedelta(seconds=-1)}, {"split": "unknown"},
])
def test_invalid_evaluation_settings_rejected(kwargs):
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.evaluate_articles([], labels(), **kwargs)


def test_report_is_json_serializable():
    report = evaluation.evaluate_articles([article(1), article(2)], labels(groups=[group(1, 2)]))
    json.dumps(report, ensure_ascii=False, allow_nan=False)


def test_macro_event_recall_weights_large_and_small_events_equally():
    ids = (10, 59, 106, 201, 5, 6)
    dataset = labels(ids, groups=[
        group(10, 59, 106, 201, event_id="E_LARGE"),
        group(5, 6, event_id="E_SMALL"),
    ])
    values = [article(i) for i in (10, 59, 106, 201)] + [article(5, 90), article(6, 180)]
    row = evaluation.evaluate_articles(values, dataset)["results"][0]
    assert row["counts"]["TP"] == 6 and row["counts"]["FN"] == 1
    assert row["metrics"]["recall"] == pytest.approx(6 / 7)
    assert row["event_macro_recall"] == pytest.approx(0.5)


def test_development_and_holdout_are_evaluated_separately():
    dataset = labels(
        annotations=[annotation(1), annotation(2), annotation(3, split="holdout"),
                     annotation(4, split="holdout")],
        groups=[group(1, 2), group(3, 4, event_id="E_HOLDOUT", split="holdout")],
    )
    values = [article(i) for i in (1, 2, 3, 4)]
    development = evaluation.evaluate_articles(values, dataset)
    holdout = evaluation.evaluate_articles(values, dataset, split="holdout")
    assert development["coverage"]["clustered_article_ids"] == [1, 2]
    assert holdout["coverage"]["clustered_article_ids"] == [3, 4]
    assert development["label_summary"]["approved_relations"] == 1
    assert holdout["label_summary"]["approved_relations"] == 1


@pytest.mark.parametrize("change,field", [
    ({"title": "다른 제목"}, "title"),
    ({"publisher": "다른 언론사"}, "publisher"),
    ({"published_at": BASE + timedelta(hours=25)}, "published_at"),
    ({"title": None}, "title"),
    ({"title": ""}, "title"),
    ({"publisher": None}, "publisher"),
    ({"publisher": ""}, "publisher"),
    ({"published_at": None}, "published_at"),
    ({"published_at": BASE.isoformat()}, "published_at"),
])
def test_input_metadata_mismatch_or_missing_stops_before_clustering(change, field, monkeypatch):
    monkeypatch.setattr(evaluation, "cluster_articles",
                        lambda *a, **k: pytest.fail("입력 불일치에서 군집 계산 금지"))
    with pytest.raises(evaluation.InputValidationError, match=field):
        evaluation.evaluate_articles([article(1), article(2, **change)],
                                     labels(groups=[group(1, 2)]))


def test_metadata_checked_even_when_embedding_is_missing():
    with pytest.raises(evaluation.InputValidationError, match="title"):
        evaluation.evaluate_articles([article(1), article(2, title="다른 제목", dense=None)],
                                     labels(pairs=[pair(1, 2)]))


def test_unknown_article_id_is_input_validation_error():
    with pytest.raises(evaluation.InputValidationError, match="99"):
        evaluation.evaluate_articles([article(1), article(99)], labels(pairs=[pair(1, 2)]))


def test_equivalent_timezones_are_same_timestamp():
    kst = timezone(timedelta(hours=9))
    report = evaluation.evaluate_articles(
        [article(1), article(2, published_at=BASE.astimezone(kst))],
        labels(groups=[group(1, 2)]))
    assert report["input_validation"]["checked_article_ids"] == [1, 2]
    assert report["results"][0]["counts"]["TP"] == 1


def test_label_missing_metadata_cannot_be_treated_as_verified():
    dataset = labels(groups=[group(1, 2)],
                     annotations=[annotation(1), annotation(2, published_at="")])
    with pytest.raises(evaluation.LabelValidationError):
        evaluation.evaluate_articles([article(1), article(2)], dataset)


def test_snapshot_comparison_does_not_claim_vector_or_url_verification():
    report = evaluation.evaluate_articles([article(1), article(2)], labels(groups=[group(1, 2)]))
    validation = report["input_validation"]
    assert validation["checked_fields"] == ["news_id", "title", "publisher", "published_at"]
    assert set(validation["unverified_fields"]) == {
        "source_url", "embedding_model", "embedding_variant", "embedding_input_text"}
    assert report["provenance"]["dataset_id"] is None
    assert report["provenance"]["version_status"] == "unavailable"


def test_exclusion_populations_and_rate_components_are_separate():
    annotations = [annotation(1), annotation(2)] + [
        unapproved(annotation(i)) for i in (3, 4, 5)]
    report = evaluation.evaluate_articles([article(1), article(2)],
        labels(annotations=annotations, pairs=[pair(1, 2)]))
    all_annotations = report["exclusions"]["article_annotations"]
    requested = report["exclusions"]["evaluation_requests"]
    assert all_annotations["population_count"] == 5
    assert all_annotations["excluded_count"] == 3
    assert all_annotations["exclusion_rate"]["numerator"] == 3
    assert all_annotations["exclusion_rate"]["denominator"] == 5
    assert all_annotations["exclusion_rate"]["value"] == pytest.approx(3 / 5)
    assert requested["population_ids"] == [1, 2]
    assert requested["excluded_count"] == 0
    assert requested["exclusion_rate"]["numerator"] == 0
    assert requested["exclusion_rate"]["denominator"] == 2
    assert "articles" not in report["exclusions"]
    assert "article_reason_counts" not in report["exclusions"]
    assert report["coverage"]["requested_article_count"] == 2
    assert report["coverage"]["excluded_article_count"] == 0
    fraction = report["coverage"]["rate_details"]["relation_coverage"]
    assert fraction == {"numerator": 1, "denominator": 1, "value": 1.0,
                        "population": "approved_same_or_different_event_pairs"}


def test_multiple_reasons_count_article_once_for_exclusion_rate():
    dataset = labels(pairs=[pair(1, 2)], annotations=[
        unapproved(annotation(1, article_type="multi_event_briefing")), annotation(2)])
    report = evaluation.evaluate_articles([article(1), article(2)], dataset)
    summary = report["exclusions"]["evaluation_requests"]
    assert sum(summary["reason_counts"].values()) == 2
    assert summary["excluded_count"] == 1
    assert summary["exclusion_rate"]["value"] == 0.5
    assert summary["reason_counts_are_nonexclusive"] is True


def test_embedding_missing_fraction_has_explicit_inspected_population():
    dataset = labels((1, 2, 3), groups=[group(1, 2, 3)])
    report = evaluation.evaluate_articles([article(1), article(2, dense=None)], dataset)
    coverage = report["coverage"]
    assert coverage["requested_article_ids"] == [1, 2, 3]
    assert coverage["embedding_checked_article_ids"] == [1, 2]
    assert coverage["embedding_unchecked_article_ids"] == [3]
    fraction = coverage["rate_details"]["embedding_missing"]
    assert fraction == {"numerator": 1, "denominator": 2, "value": 0.5,
                        "population": "metadata_checked_supplied_requested_articles"}


def test_no_approved_relations_has_zero_denominators_and_no_verification():
    dataset = labels(pairs=[unapproved(pair(1, 2))])
    report = evaluation.evaluate_articles([], dataset)
    assert report["results"] == []
    assert report["exclusions"]["evaluation_requests"]["population_count"] == 0
    assert report["exclusions"]["evaluation_requests"]["exclusion_rate"]["value"] is None
    assert report["coverage"]["rate_details"]["relation_coverage"]["value"] is None
    assert report["input_validation"]["status"] == "not_run_no_approved_relations"


def test_synthetic_unapproved_records_cannot_produce_scores(tmp_path, monkeypatch):
    """실제 후보의 승인 여부와 독립적으로 미승인 차단을 합성 데이터로 검증한다."""
    synthetic = labels(
        annotations=[unapproved(annotation(i)) for i in (1, 2, 3)],
        groups=[unapproved(group(1, 2))],
        pairs=[unapproved(pair(2, 3))],
    )
    dataset = evaluation.load_labels(write_labels(tmp_path, synthetic))
    records = (*dataset.articles, *dataset.groups, *dataset.pairs)
    assert all(r.review_status != "approved" and not r.reviewed_at and not r.reviewer
               for r in records)
    assert all(r.split == "development" for r in records)
    monkeypatch.setattr(evaluation, "cluster_articles",
                        lambda *a, **k: pytest.fail("미승인 라벨의 점수 계산 금지"))
    # 유효한 합성 벡터를 주어도 미승인 관계는 군집 계산에 진입하지 않는다.
    report = evaluation.evaluate_articles([article(i) for i in (1, 2, 3)], dataset)
    assert report["status"] == "평가 불가: 승인 라벨 없음"
    assert report["label_summary"]["approved_relations"] == 0
    assert report["results"] == []
    assert "metrics" not in report
    assert report["input_validation"]["status"] == "not_run_no_approved_relations"


def test_versions_and_original_byte_hashes_survive_validation_and_report(tmp_path):
    import hashlib
    write_labels(tmp_path, labels(groups=[group(1, 2)]))
    loaded = evaluation.load_labels(tmp_path)
    checked = evaluation.validate_labels(loaded)
    assert checked.metadata == loaded.metadata
    report = evaluation.evaluate_articles([article(1), article(2)], checked)
    provenance = report["provenance"]
    expected = {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
                for name in ("articles.csv", "event_groups.json", "pair_labels.csv")}
    assert provenance["source_file_sha256"] == expected
    assert provenance["dataset_id"] == "synthetic"
    assert provenance["label_policy_version"] == "1"
    assert provenance["schema_version"] == 1
    assert provenance["label_source"] == "files"
    assert len(provenance["evaluator_code_sha256"]) == 64
    assert evaluation.evaluate_articles([article(1), article(2)], loaded)["provenance"] == provenance


def test_hash_uses_raw_bytes_not_normalized_csv(tmp_path):
    write_labels(tmp_path, labels(groups=[group(1, 2)]))
    first = evaluation.load_labels(tmp_path)
    path = tmp_path / "articles.csv"
    original = path.read_bytes()
    path.write_bytes(original.replace(b"\r\n", b"\n"))
    assert path.read_bytes() != original
    second = evaluation.load_labels(tmp_path)
    assert first.articles == second.articles
    assert dict(first.metadata.source_file_hashes)["articles.csv"] != dict(
        second.metadata.source_file_hashes)["articles.csv"]
    first_report = evaluation.evaluate_articles([article(1), article(2)], first)
    second_report = evaluation.evaluate_articles([article(1), article(2)], second)
    assert first_report["provenance"]["effective_labels_sha256"] == second_report[
        "provenance"]["effective_labels_sha256"]


def test_report_keeps_loaded_hashes_if_source_file_changes_after_loading(tmp_path):
    import hashlib
    write_labels(tmp_path, labels(groups=[group(1, 2)]))
    loaded = evaluation.load_labels(tmp_path)
    before = dict(loaded.metadata.source_file_hashes)
    path = tmp_path / "event_groups.json"
    path.write_bytes(path.read_bytes() + b"\n")
    report = evaluation.evaluate_articles([article(1), article(2)], loaded)
    assert report["provenance"]["source_file_sha256"] == before
    assert before["event_groups.json"] != hashlib.sha256(path.read_bytes()).hexdigest()


def test_effective_label_hash_detects_changes_in_memory(tmp_path):
    write_labels(tmp_path, labels(groups=[group(1, 2)]))
    loaded = evaluation.load_labels(tmp_path)
    changed = replace(loaded, groups=(replace(loaded.groups[0], reason="메모리에서 바뀐 근거"),))
    first = evaluation.evaluate_articles([article(1), article(2)], loaded)["provenance"]
    second = evaluation.evaluate_articles([article(1), article(2)], changed)["provenance"]
    assert first["source_file_sha256"] == second["source_file_sha256"]
    assert first["effective_labels_sha256"] != second["effective_labels_sha256"]


def test_loader_preserves_exact_title_whitespace_for_comparison(tmp_path):
    dataset = labels(groups=[group(1, 2)],
                     annotations=[annotation(1), annotation(2, title=" 합성 기사 2 ")])
    write_labels(tmp_path, dataset)
    loaded = evaluation.load_labels(tmp_path)
    assert loaded.articles[1].title == " 합성 기사 2 "
    with pytest.raises(evaluation.InputValidationError, match="title"):
        evaluation.evaluate_articles([article(1), article(2)], loaded)
