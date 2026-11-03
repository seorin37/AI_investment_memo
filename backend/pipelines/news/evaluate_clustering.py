"""개발용 클러스터 평가: 파일 로딩과 메모리 계산만 수행한다.

load_labels(directory) -> LabelSet; evaluate_articles(articles, labels) -> dict.
DB·모델·네트워크·결과 파일 저장·CLI는 없다. 기사 주석과 관계 모두 사람이
승인해야 평가한다. 기본 임계값은 실험용이며 운영 기준이 아니다.
부분 라벨의 지표는 알려진 관계에만 한정된다. 그룹 완전 복원은 주장하지 않는다.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from itertools import combinations
from numbers import Real
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from .clustering import NewsArticle, cluster_articles, cosine_similarity

THRESHOLDS = (0.60, 0.65, 0.70)
STATUSES = {"proposed", "needs_review", "approved", "rejected"}
SPLITS = {"development", "holdout"}
TYPES = {"single_event", "multi_event_briefing", "insufficient_information"}
RELATIONS = {"same_event", "different_event", "undecided"}
SCOPES = {"whole_article", "representative_event"}
QUALITY = {"summary_missing", "summary_invalid", "summary_partial", "title_only_evidence",
           "full_text_checked", "summary_available"}
CONFIDENCES = {"high", "medium", "low"}


class LabelValidationError(ValueError):
    """형식·승인·사건 관계의 모순을 발견하면 평가를 중단한다."""


class InputValidationError(LabelValidationError):
    """입력 기사 오류. FN 등 모델 성능 오류로 기록하지 않는다."""


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    label_policy_version: str
    schema_version: int
    # 로딩 당시 파일 원본 바이트의 SHA-256. 데이터의 사실성·벡터 출처 증명이 아니다.
    source_file_hashes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ArticleLabel:
    article_id: int
    title: str
    publisher: str
    published_at: str
    article_type: str
    information_quality: tuple[str, ...]
    source_url: str
    reason: str
    confidence: str
    review_status: str
    reviewed_at: str
    reviewer: str
    split: str


@dataclass(frozen=True)
class EventGroup:
    event_id: str
    event_description: str
    member_ids: tuple[int, ...]
    event_time: str
    evidence_urls: tuple[str, ...]
    reason: str
    confidence: str
    review_status: str
    reviewed_at: str
    reviewer: str
    split: str


@dataclass(frozen=True)
class PairLabel:
    article_id_a: int
    article_id_b: int
    relation: str
    scope: str
    evidence_urls: tuple[str, ...]
    reason: str
    confidence: str
    review_status: str
    reviewed_at: str
    reviewer: str
    split: str


@dataclass(frozen=True)
class LabelSet:
    articles: tuple[ArticleLabel, ...]
    groups: tuple[EventGroup, ...]
    pairs: tuple[PairLabel, ...]
    metadata: DatasetMetadata | None = None


def _require(condition, message):
    if not condition:
        raise LabelValidationError(message)


def _id(value):
    _require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
             "기사 ID는 양의 정수여야 합니다")
    return value


def _csv_id(value):
    _require(isinstance(value, str) and value.isascii() and value.isdecimal(),
             "CSV 기사 ID 형식 오류")
    return _id(int(value))


def _url(value):
    _require(isinstance(value, str), "URL 형식 오류")
    parsed = urlsplit(value)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.hostname)
             and parsed.username is None and parsed.password is None, "공개 원문 URL 필요")


def _time(value):
    try:
        parsed = datetime.fromisoformat(value)
        _require(parsed.utcoffset() is not None, "시각에 시간대 필요")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise LabelValidationError("유효한 시간대 포함 ISO 시각 필요") from exc


def _review(record):
    for field in ("reason", "reviewed_at", "reviewer", "split", "review_status", "confidence"):
        _require(isinstance(getattr(record, field), str), f"{field}는 문자열이어야 합니다")
    _require(bool(record.reason.strip()), "판단 근거 필요")
    _require(record.confidence in CONFIDENCES, "신뢰도 오류")
    _require(record.review_status in STATUSES, "검토 상태 오류")
    _require(record.split in SPLITS, "분할 오류")
    if record.reviewed_at:
        _time(record.reviewed_at)
    if record.review_status == "approved":
        _require(bool(record.reviewer.strip()) and bool(record.reviewed_at),
                 "승인 라벨에는 실제 검토자와 검토 시각 필요")


def validate_labels(labels: LabelSet) -> LabelSet:
    """중복 쌍을 정규화하고 모순은 미승인 후보 단계에서도 중단한다.

    완전히 같은 역순 쌍은 한 번만 유지한다. 메타데이터가 다른 중복은
    승인 상태를 임의 병합하지 않고 오류로 처리한다. rejected 관계는 모순
    검사와 평가에서 사용하지 않는다. 쌍의 전이성은 모순 검사에만 사용하며
    평가 정답 쌍을 자동 확장하는 데 사용하지 않는다.
    """
    _require(isinstance(labels, LabelSet), "LabelSet 필요")
    if labels.metadata is not None:
        meta = labels.metadata
        _require(isinstance(meta, DatasetMetadata), "DatasetMetadata 필요")
        _require(isinstance(meta.dataset_id, str) and bool(meta.dataset_id.strip())
                 and isinstance(meta.label_policy_version, str)
                 and bool(meta.label_policy_version.strip()), "데이터셋·라벨 정책 버전 필요")
        _require(type(meta.schema_version) is int and meta.schema_version == 1,
                 "지원하지 않는 메타데이터 스키마")
        _require(isinstance(meta.source_file_hashes, tuple), "파일 해시 목록 형식 오류")
        names = set()
        for entry in meta.source_file_hashes:
            _require(isinstance(entry, tuple) and len(entry) == 2, "파일 해시 형식 오류")
            name, digest = entry
            _require(isinstance(name, str) and name in {
                "articles.csv", "event_groups.json", "pair_labels.csv"
            } and name not in names, "해시 파일 이름 중복 또는 오류")
            _require(isinstance(digest, str) and len(digest) == 64
                     and all(c in "0123456789abcdef" for c in digest), "SHA-256 형식 오류")
            names.add(name)
        _require(not names or len(names) == 3, "라벨 파일 3개의 해시 필요")
    articles = {}
    for article in labels.articles:
        _require(isinstance(article, ArticleLabel), "ArticleLabel 필요")
        _id(article.article_id)
        _require(article.article_id not in articles, "중복 기사 ID")
        _review(article)
        _require(article.article_type in TYPES, "기사 유형 오류")
        _require(isinstance(article.information_quality, tuple)
                 and all(isinstance(q, str) and q in QUALITY for q in article.information_quality), "정보 품질 오류")
        _require(isinstance(article.title, str) and bool(article.title.strip())
                 and isinstance(article.publisher, str) and bool(article.publisher.strip()),
                 "제목·언론사 필요")
        _time(article.published_at)
        _url(article.source_url)
        articles[article.article_id] = article

    groups, event_ids, membership = [], set(), {}
    for group in labels.groups:
        _require(isinstance(group, EventGroup), "EventGroup 필요")
        _review(group)
        _require(isinstance(group.event_id, str) and bool(group.event_id.strip())
                 and group.event_id not in event_ids, "중복 또는 빈 사건 ID")
        _require(isinstance(group.event_description, str) and bool(group.event_description.strip())
                 and isinstance(group.event_time, str), "사건 설명·시점 형식 오류")
        event_ids.add(group.event_id)
        _require(isinstance(group.member_ids, tuple) and len(group.member_ids) >= 2,
                 "그룹에는 최소 2건 필요")
        for article_id in group.member_ids:
            _id(article_id)
            _require(article_id in articles, "그룹의 기사 주석 누락")
            _require(articles[article_id].split == group.split, "사건의 분할 누출")
            if group.review_status != "rejected" and articles[article_id].article_type == "single_event":
                _require(article_id not in membership, "단일 사건 기사의 중복 그룹 배정")
                membership[article_id] = group.event_id
        _require(len(set(group.member_ids)) == len(group.member_ids), "그룹 내부 중복 기사 ID")
        _require(isinstance(group.evidence_urls, tuple) and bool(group.evidence_urls),
                 "그룹 근거 URL 필요")
        for url in group.evidence_urls:
            _url(url)
        groups.append(replace(group, member_ids=tuple(sorted(group.member_ids))))

    pairs = {}
    for pair in labels.pairs:
        _require(isinstance(pair, PairLabel), "PairLabel 필요")
        _review(pair)
        a, b = sorted((_id(pair.article_id_a), _id(pair.article_id_b)))
        _require(a != b, "자기 자신과의 쌍")
        _require(pair.relation in RELATIONS and pair.scope in SCOPES, "관계 또는 범위 오류")
        _require(a in articles and b in articles, "쌍의 기사 주석 누락")
        _require(articles[a].split == articles[b].split == pair.split, "쌍의 분할 누출")
        _require(isinstance(pair.evidence_urls, tuple) and bool(pair.evidence_urls),
                 "쌍 근거 URL 필요")
        for url in pair.evidence_urls:
            _url(url)
        canonical = replace(pair, article_id_a=a, article_id_b=b)
        key = (a, b, pair.scope)
        _require(key not in pairs or pairs[key] == canonical, "모순 또는 메타데이터가 다른 중복 쌍")
        pairs[key] = canonical

    # 동일 사건의 동치 관계에 별개 사건이 섞이는지 검사한다.
    parents = {i: i for i in articles}

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(a, b):
        parents[root(a)] = root(b)

    for group in groups:
        if group.review_status != "rejected":
            for i in group.member_ids[1:]:
                union(group.member_ids[0], i)
    for pair in pairs.values():
        if (pair.review_status != "rejected" and pair.scope == "whole_article"
                and pair.relation == "same_event"):
            union(pair.article_id_a, pair.article_id_b)
    component_events = {}
    for article_id, event_id in membership.items():
        component_events.setdefault(root(article_id), set()).add(event_id)
    _require(all(len(values) <= 1 for values in component_events.values()),
             "서로 다른 사건 그룹을 동일 사건 쌍으로 연결")
    for pair in pairs.values():
        if (pair.review_status != "rejected" and pair.scope == "whole_article"
                and pair.relation == "different_event"):
            _require(root(pair.article_id_a) != root(pair.article_id_b), "동일·별개 사건 모순")
    return LabelSet(tuple(sorted(articles.values(), key=lambda x: x.article_id)),
                    tuple(sorted(groups, key=lambda x: x.event_id)),
                    tuple(pairs[k] for k in sorted(pairs)), labels.metadata)


def _csv_rows(raw: bytes, record_type, file_name: str):
    # 해시를 구한 동일한 원본 바이트를 파싱한다. 파일을 다시 읽지 않는다.
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        reader = csv.DictReader(stream)
        expected = [f.name for f in fields(record_type)]
        _require(reader.fieldnames is not None
                 and len(reader.fieldnames) == len(set(reader.fieldnames))
                 and set(reader.fieldnames) == set(expected), f"{file_name}: CSV 열 오류")
        rows = []
        for row in reader:
            _require(set(row) == set(expected) and all(isinstance(v, str) for v in row.values()),
                     f"{file_name}: CSV 행 오류")
            # 제목·언론사는 원본 값을 보존해 입력과 정확히 비교한다.
            rows.append({k: v if k in {"title", "publisher"} else v.strip()
                         for k, v in row.items()})
        return rows


def _unique_json_object(items):
    result = {}
    for key, value in items:
        _require(key not in result, "JSON 중복 키")
        result[key] = value
    return result


def load_labels(directory: str | Path) -> LabelSet:
    """3개 라벨 파일을 읽기만 한다. 모델·DB를 사용하지 않는다."""
    directory = Path(directory)
    try:
        raw = {name: (directory / name).read_bytes() for name in
               ("articles.csv", "event_groups.json", "pair_labels.csv")}
        articles = []
        for row in _csv_rows(raw["articles.csv"], ArticleLabel, "articles.csv"):
            row["article_id"] = _csv_id(row["article_id"])
            row["information_quality"] = tuple(filter(None, row["information_quality"].split("|")))
            articles.append(ArticleLabel(**row))
        pairs = []
        for row in _csv_rows(raw["pair_labels.csv"], PairLabel, "pair_labels.csv"):
            for key in ("article_id_a", "article_id_b"):
                row[key] = _csv_id(row[key])
            row["evidence_urls"] = tuple(filter(None, row["evidence_urls"].split("|")))
            pairs.append(PairLabel(**row))
        document = json.loads(raw["event_groups.json"].decode("utf-8-sig"),
                              object_pairs_hook=_unique_json_object)
        _require(isinstance(document, dict) and set(document) == {
            "schema_version", "dataset_id", "label_policy_version", "note", "groups"
        }, "사건 JSON 문서 형식 오류")
        _require(type(document["schema_version"]) is int and document["schema_version"] == 1,
                 "지원하지 않는 스키마 버전")
        for key in ("dataset_id", "label_policy_version", "note"):
            _require(isinstance(document[key], str) and bool(document[key].strip()),
                     "데이터 버전·설명 필요")
        _require(isinstance(document["groups"], list), "groups는 목록이어야 합니다")
        groups = []
        expected = {f.name for f in fields(EventGroup)}
        for row in document["groups"]:
            _require(isinstance(row, dict) and set(row) == expected, "사건 레코드 형식 오류")
            _require(isinstance(row["member_ids"], list) and isinstance(row["evidence_urls"], list),
                     "사건 기사·URL 목록 형식 오류")
            groups.append(EventGroup(**{**row, "member_ids": tuple(row["member_ids"]),
                                        "evidence_urls": tuple(row["evidence_urls"])}))
        meta = DatasetMetadata(
            dataset_id=document["dataset_id"],
            label_policy_version=document["label_policy_version"],
            schema_version=document["schema_version"],
            source_file_hashes=tuple((name, hashlib.sha256(content).hexdigest())
                                     for name, content in sorted(raw.items())),
        )
        return validate_labels(LabelSet(tuple(articles), tuple(groups), tuple(pairs), meta))
    except LabelValidationError:
        raise
    except (ValueError, TypeError, KeyError, csv.Error, UnicodeError) as exc:
        raise LabelValidationError("라벨 파일 형식 오류") from exc


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _fraction(numerator, denominator, population):
    return {"numerator": numerator, "denominator": denominator,
            "value": _ratio(numerator, denominator), "population": population}


def _exclusion_summary(ids, reasons, population):
    ids = sorted(ids)
    excluded = [{"id": i, "reasons": list(reasons[i])} for i in ids if reasons.get(i)]
    return {
        "population": population, "population_ids": ids, "population_count": len(ids),
        "excluded_articles": excluded, "excluded_count": len(excluded),
        "reason_counts": dict(Counter(r for record in excluded for r in record["reasons"])),
        "reason_counts_are_nonexclusive": True,
        "exclusion_rate": _fraction(len(excluded), len(ids), population),
    }


def _coverage(requested, valid, reasons, eligible, relations, checked):
    missing = sorted(i for i in requested if "embedding_missing" in reasons.get(i, []))
    invalid = sorted(i for i in requested if "invalid_embedding" in reasons.get(i, []))
    absent = sorted(i for i in requested if "article_input_missing" in reasons.get(i, []))
    return {
        "article_population": "approved_relation_endpoints",
        "relation_population": "approved_same_or_different_event_pairs",
        "requested_article_ids": sorted(requested),
        "requested_article_count": len(requested), "valid_article_count": len(valid),
        "excluded_article_count": len(requested) - len(valid),
        "embedding_checked_article_ids": sorted(checked),
        "embedding_unchecked_article_ids": sorted(set(requested) - set(checked)),
        "embedding_missing_ids": missing,
        "embedding_missing_rate": _ratio(len(missing), len(checked)),
        "article_input_missing_ids": absent, "invalid_embedding_ids": invalid,
        "approved_relation_count": len(relations), "evaluated_relation_count": len(eligible),
        "excluded_relation_count": len(relations) - len(eligible),
        "relation_coverage": _ratio(len(eligible), len(relations)),
        "rate_details": {
            "article_exclusion": _fraction(len(requested) - len(valid), len(requested),
                                          "approved_relation_endpoints"),
            "embedding_missing": _fraction(len(missing), len(checked),
                                            "metadata_checked_supplied_requested_articles"),
            "relation_coverage": _fraction(len(eligible), len(relations),
                                           "approved_same_or_different_event_pairs"),
        },
    }


def _provenance(labels):
    # 정규화된 실제 평가 라벨의 해시도 구해 메모리에서 바뀐 라벨을 구분한다.
    effective = {"articles": [asdict(x) for x in labels.articles],
                 "groups": [asdict(x) for x in labels.groups],
                 "pairs": [asdict(x) for x in labels.pairs]}
    raw = json.dumps(effective, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    meta = labels.metadata
    return {
        "dataset_id": meta.dataset_id if meta else None,
        "label_policy_version": meta.label_policy_version if meta else None,
        "schema_version": meta.schema_version if meta else None,
        "label_source": "files" if meta and meta.source_file_hashes else "in_memory",
        "version_status": "provided" if meta else "unavailable",
        "source_file_sha256": dict(meta.source_file_hashes) if meta else {},
        "effective_labels_sha256": hashlib.sha256(raw).hexdigest(),
        "evaluator_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "hash_scope": "파일 해시는 로딩 당시 원본 바이트의 식별자이며 사실성·벡터 출처를 보증하지 않는다. "
                      "effective_labels_sha256은 정규화된 현재 라벨만 식별한다.",
    }


def _check_input_metadata(article, annotation):
    problems = []
    if article.news_id != annotation.article_id:
        problems.append("news_id")
    if not isinstance(article.title, str) or article.title != annotation.title:
        problems.append("title")
    if not isinstance(article.publisher, str) or article.publisher != annotation.publisher:
        problems.append("publisher")
    try:
        if not isinstance(article.published_at, datetime):
            raise ValueError
        if article.published_at.utcoffset() is None:
            raise ValueError
        actual = article.published_at.astimezone(timezone.utc)
        if actual != _time(annotation.published_at):
            problems.append("published_at")
    except (TypeError, ValueError, OverflowError):
        problems.append("published_at")
    if problems:
        # 비밀정보·본문 값은 오류 메시지에 담지 않는다.
        raise InputValidationError(
            f"입력 기사 검증 실패: ID={annotation.article_id}, fields={','.join(problems)}. "
            "라벨 자료와 일치하는 메타데이터가 필요합니다."
        )


def evaluate_articles(
    articles: Iterable[NewsArticle], labels: LabelSet, *,
    thresholds: Iterable[float] = THRESHOLDS,
    max_time_gap: timedelta | None = timedelta(hours=24),
    split: str = "development",
) -> dict:
    """승인된 기사 주석과 관계만 평가한다. 결과는 JSON 직렬화 가능한 dict.

    임베딩 없는 기사를 단독 기사로 대체하지 않는다. 승인 관계의 유효한
    끝점만 고정해 모든 임계값에 같은 입력을 전달한다. 누락 멤버가 있는
    사건의 전체 Recall·분할 수는 None으로 남겨 완전 복원으로 오인하지 않는다.
    """
    labels = validate_labels(labels)
    _require(split in SPLITS, "평가 분할 오류")
    thresholds = tuple(thresholds)
    _require(bool(thresholds) and all(isinstance(t, Real) and not isinstance(t, bool)
             and math.isfinite(t) and -1 <= t <= 1 for t in thresholds), "임계값 오류")
    _require(len(set(thresholds)) == len(thresholds), "중복 임계값")
    _require(max_time_gap is None or (isinstance(max_time_gap, timedelta)
             and max_time_gap >= timedelta(0)), "시간 범위 오류")
    metadata = {a.article_id: a for a in labels.articles if a.split == split}
    groups = [g for g in labels.groups if g.split == split]
    pairs = [p for p in labels.pairs if p.split == split]
    relations = {}
    excluded_groups, excluded_labels = [], []
    for group in groups:
        if group.review_status == "approved":
            for pair in combinations(group.member_ids, 2):
                relations[pair] = "same_event"
        else:
            excluded_groups.append({"event_id": group.event_id, "reason": group.review_status})
    for pair in pairs:
        reason = (pair.review_status if pair.review_status != "approved" else
                  "undecided" if pair.relation == "undecided" else
                  "representative_event" if pair.scope != "whole_article" else None)
        if reason:
            excluded_labels.append({"ids": [pair.article_id_a, pair.article_id_b], "reason": reason})
        else:
            relations[(pair.article_id_a, pair.article_id_b)] = pair.relation

    annotation_reasons = {}
    for i, annotation in metadata.items():
        flags = []
        if annotation.review_status != "approved":
            flags.append("article_not_approved")
        if annotation.article_type != "single_event":
            flags.append(annotation.article_type)
        if flags:
            annotation_reasons[i] = flags
    report = {
        "status": "평가 불가: 승인 라벨 없음", "split": split,
        "provenance": _provenance(labels),
        "input_validation": {
            "status": "not_run_no_approved_relations", "checked_article_ids": [],
            "checked_fields": ["news_id", "title", "publisher", "published_at"],
            "unverified_fields": ["source_url", "embedding_model", "embedding_variant",
                                  "embedding_input_text"],
            "note": "확인은 제공된 라벨 스냅샷과 입력의 일치 여부에 한정된다. DB·원문·벡터 출처는 검증하지 않는다.",
        },
        "label_summary": {
            "articles": len(metadata), "groups": len(groups),
            "approved_groups": sum(g.review_status == "approved" for g in groups),
            "pair_records": len(pairs), "approved_relations": len(relations),
        },
        "settings": {"thresholds": list(thresholds),
                     "max_time_gap_seconds": max_time_gap.total_seconds()
                     if max_time_gap is not None else None},
        "exclusions": {
            "groups": excluded_groups, "pair_labels": excluded_labels, "relations": [],
            "article_annotations": _exclusion_summary(
                metadata, annotation_reasons, "selected_split_article_annotations"),
            "evaluation_requests": _exclusion_summary(
                [], {}, "approved_relation_endpoints"),
        },
        "coverage": _coverage([], {}, {}, {}, relations, []), "results": [],
        "note": "승인된 알려진 관계만 채점한다. 라벨 없는 교차 쌍은 정답 미확정이다.",
    }
    # 승인 전에는 벡터 검증·군집 계산이나 성능 점수를 만들지 않는다.
    if not relations:
        return report

    inputs = {}
    known_ids = {a.article_id for a in labels.articles}
    for article in articles:
        if not isinstance(article, NewsArticle):
            raise InputValidationError("NewsArticle 입력 필요")
        try:
            _id(article.news_id)
        except LabelValidationError as exc:
            raise InputValidationError("입력 기사 ID는 양의 정수여야 합니다") from exc
        if article.news_id not in known_ids:
            raise InputValidationError(f"라벨에 없는 입력 기사 ID: {article.news_id}")
        if article.news_id in inputs:
            raise InputValidationError(f"입력 기사 ID 중복: {article.news_id}")
        inputs[article.news_id] = article
    requested = sorted({i for pair in relations for i in pair})
    valid = {}
    reasons = {}
    checked = []
    for i in requested:
        annotation = metadata[i]
        rejected = []
        if annotation.review_status != "approved":
            rejected.append("article_not_approved")
        if annotation.article_type != "single_event":
            rejected.append(annotation.article_type)
        if not rejected:
            if i not in inputs:
                rejected.append("article_input_missing")
            else:
                article = inputs[i]
                _check_input_metadata(article, annotation)
                checked.append(i)
                if article.dense is None:
                    rejected.append("embedding_missing")
                else:
                    try:
                        cosine_similarity(article.dense, article.dense)
                    except (ValueError, TypeError, OverflowError):
                        rejected.append("invalid_embedding")
                    if not rejected:
                        valid[i] = replace(article, dense=tuple(article.dense))
        if rejected:
            reasons[i] = rejected
    eligible = {p: relation for p, relation in sorted(relations.items())
                if all(i in valid for i in p)}
    for pair in sorted(relations):
        if pair not in eligible:
            report["exclusions"]["relations"].append({
                "ids": list(pair), "reasons": {str(i): reasons[i] for i in pair if i in reasons}})
    report["exclusions"]["evaluation_requests"] = _exclusion_summary(
        requested, reasons, "approved_relation_endpoints")
    report["coverage"] = _coverage(requested, valid, reasons, eligible, relations, checked)
    report["input_validation"].update(
        status="checked_for_listed_articles" if checked else "not_run_no_eligible_articles",
        checked_article_ids=checked,
        unverified_input_ids=sorted(set(inputs) - set(checked)),
    )
    if not eligible:
        report["status"] = "평가 불가: 평가 가능한 승인 관계 없음"
        return report

    # 한쪽 끝점만 남은 관계도 다른 그룹의 병합에 영향을 줄 수 있으므로 입력에서 제외한다.
    selected_ids = sorted({i for pair in eligible for i in pair})
    frozen_input = tuple(valid[i] for i in selected_ids)
    report["coverage"]["clustered_article_ids"] = selected_ids
    report["coverage"]["ignored_input_ids"] = sorted(set(inputs) - set(selected_ids))
    report["status"] = "평가 완료"
    for threshold in thresholds:
        preview = cluster_articles(frozen_input, threshold=threshold, max_time_gap=max_time_gap)
        assignment = {i: index for index, c in enumerate(preview.clusters) for i in c.article_ids}
        counts = dict.fromkeys(("TP", "FP", "FN", "TN"), 0)
        false_merges, false_splits = [], []
        for (a, b), truth in eligible.items():
            joined = assignment[a] == assignment[b]
            category = ("TP" if joined else "FN") if truth == "same_event" else ("FP" if joined else "TN")
            counts[category] += 1
            if category == "FP":
                false_merges.append([a, b])
            if category == "FN":
                false_splits.append([a, b])
        tp, fp, fn, tn = (counts[k] for k in ("TP", "FP", "FN", "TN"))
        event_results = []
        for group in groups:
            if group.review_status != "approved":
                continue
            missing = sorted(set(group.member_ids) - set(assignment))
            total = len(group.member_ids) * (len(group.member_ids) - 1) // 2
            event_results.append({
                "event_id": group.event_id, "member_ids": list(group.member_ids),
                "expected_pair_count": total, "excluded_member_ids": missing,
                "status": "incomplete" if missing else "evaluated",
                "recall": None if missing else sum(assignment[a] == assignment[b]
                    for a, b in combinations(group.member_ids, 2)) / total,
                "split_count": None if missing else len({assignment[i] for i in group.member_ids}),
                "exact_group_recovery": None,
            })
        recalls = [e["recall"] for e in event_results if e["recall"] is not None]
        report["results"].append({
            "threshold": threshold, "clustered_article_ids": selected_ids,
            "clusters": [{"ids": list(c.article_ids), "representative_id": c.representative.news_id,
                          "minimum_similarity": c.min_similarity} for c in preview.clusters],
            "counts": counts,
            "metrics": {"precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
                        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
                        "different_event_separation_rate": _ratio(tn, tn + fp)},
            "false_merges": false_merges, "false_splits": false_splits,
            "unlabeled_predicted_merges": [list(p) for c in preview.clusters
                for p in combinations(c.article_ids, 2) if p not in eligible],
            "events": event_results, "event_macro_recall": _ratio(sum(recalls), len(recalls)),
            "incomplete_event_count": sum(e["status"] == "incomplete" for e in event_results),
        })
    return report
