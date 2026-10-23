"""기존 BGE-M3 dense 벡터로 만드는 읽기 전용 뉴스 그룹 미리보기.

DB·모델·수집 코드를 호출하지 않는 순수 함수 모듈이다. threshold=0.65는
소규모 평가를 위한 실험용 임시값이며, 운영 검증 전 기준이다.
유사도가 높아도 동일 사건으로 확정하지 않는다.

complete-link: 모든 교차 기사 쌍의 유사도가 threshold 이상이고 발행시각
차이가 max_time_gap 이하인 그룹만 병합한다. 가능한 병합 중 최소 유사도가
가장 높은 것을 선택하고, 동점이면 기사 ID 튜플 순으로 결정한다. 따라서
A-B, B-C만 가까운 경우 A-B-C를 한 그룹으로 연결하지 않는다.

기본 시간 범위는 실험용 24시간이고 None이면 시간 제한을 끈다. 결과는 ID순으로
안정적으로 정렬한다. 대표는 가장 이른 발행 기사(동시각이면 최소 ID)이며,
대표성·품질·원보도 여부를 판정한 것은 아니다. 결과 발행시각은 UTC로 통일한다.
단독 기사도 반환하며 비교할 쌍이 없으므로 min_similarity=None이다.

dense=None은 누락 ID로 보고한다. 누락 외의 잘못된 입력과 중복 ID는 ValueError로
전체 호출을 중단한다. 입력 목록에 아예 없는 기사의 누락은 판단할 수 없다.
전체 쌍 비교와 탐욕적인 병합을 사용하므로 소규모 미리보기용이다. 모든 조건을
만족하는 최대 크기 그룹이나, 유일한 사건 분류를 보장하지 않는다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations
from numbers import Real
from typing import Iterable, Sequence


DENSE_DIMENSIONS = 1024
# 운영 검증 전 실험용 임시 임계값. 운영 임계값으로 확정하지 않는다.
DEFAULT_THRESHOLD = 0.65
DEFAULT_MAX_TIME_GAP = timedelta(hours=24)


@dataclass(frozen=True)
class NewsArticle:
    news_id: int
    title: str
    publisher: str
    published_at: datetime
    dense: Sequence[float] | None = None


@dataclass(frozen=True)
class ArticlePreview:
    """벡터를 포함하지 않는 표시용 기사 정보. published_at은 UTC."""

    news_id: int
    title: str
    publisher: str
    published_at: datetime


@dataclass(frozen=True)
class ClusterPreview:
    representative: ArticlePreview
    article_ids: tuple[int, ...]
    min_similarity: float | None

    @property
    def article_count(self) -> int:
        return len(self.article_ids)


@dataclass(frozen=True)
class ClusteringResult:
    clusters: tuple[ClusterPreview, ...]
    missing_embedding_ids: tuple[int, ...]


def _normalize_dense(vector: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)):
        raise ValueError("dense vector must be a sequence of 1024 numbers")
    if len(vector) != DENSE_DIMENSIONS:
        raise ValueError("dense vector must have 1024 dimensions")
    if any(isinstance(x, bool) or not isinstance(x, Real) for x in vector):
        raise ValueError("dense vector must contain real numbers")
    try:
        values = tuple(float(x) for x in vector)
    except (ValueError, OverflowError) as exc:
        raise ValueError("dense vector values must be finite") from exc
    if not all(math.isfinite(x) for x in values):
        raise ValueError("dense vector values must be finite")
    norm = math.hypot(*values)
    if not 0 < norm < math.inf:
        raise ValueError("dense vector must have a nonzero finite L2 norm")
    return tuple(x / norm for x in values)


def _unit_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    # 부동소수점 반올림으로 [-1, 1]을 미세하게 벗어나는 경우만 보정한다.
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right))))


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """1,024차원 두 벡터를 실제 L2 norm으로 정규화해 코사인 유사도를 계산한다."""
    return _unit_similarity(_normalize_dense(left), _normalize_dense(right))


def _complete_link_score(
    left: tuple[int, ...], right: tuple[int, ...],
    pair_scores: dict[tuple[int, int], float], threshold: float,
) -> float | None:
    score = 1.0
    for a in left:
        for b in right:
            similarity = pair_scores.get((min(a, b), max(a, b)))
            if similarity is None or similarity < threshold:
                return None
            score = min(score, similarity)
    return score


def cluster_articles(
    articles: Iterable[NewsArticle], *, threshold: float = DEFAULT_THRESHOLD,
    max_time_gap: timedelta | None = DEFAULT_MAX_TIME_GAP,
) -> ClusteringResult:
    """메모리의 기사만 complete-link로 묶는다. DB 쓰기나 모델 실행은 하지 않는다.

    threshold는 [-1, 1]의 유한한 수, max_time_gap은 0 이상의 timedelta 또는
    None이다. 두 조건 모두 경계값을 포함한다. 입력과 입력 벡터는 수정하지 않는다.
    """
    if (isinstance(threshold, bool) or not isinstance(threshold, Real)
            or not -1 <= threshold <= 1 or not math.isfinite(threshold)):
        raise ValueError("threshold must be a finite number between -1 and 1")
    if max_time_gap is not None and (
        not isinstance(max_time_gap, timedelta) or max_time_gap < timedelta(0)
    ):
        raise ValueError("max_time_gap must be a nonnegative timedelta or None")

    metadata: dict[int, ArticlePreview] = {}
    units: dict[int, tuple[float, ...]] = {}
    missing = []
    for article in articles:
        if not isinstance(article, NewsArticle):
            raise ValueError("articles must contain NewsArticle instances")
        news_id = article.news_id
        if isinstance(news_id, bool) or not isinstance(news_id, int) or news_id <= 0:
            raise ValueError("news_id must be a positive integer")
        if news_id in metadata:
            raise ValueError(f"duplicate news_id: {news_id}")
        if not isinstance(article.title, str) or not article.title.strip():
            raise ValueError(f"news_id={news_id}: title is required")
        if not isinstance(article.publisher, str) or not article.publisher.strip():
            raise ValueError(f"news_id={news_id}: publisher is required")
        published = article.published_at
        try:
            if not isinstance(published, datetime) or published.utcoffset() is None:
                raise ValueError("timezone-aware datetime required")
            published_utc = published.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"news_id={news_id}: published_at must be a valid timezone-aware datetime") from exc
        metadata[news_id] = ArticlePreview(
            news_id, article.title, article.publisher, published_utc,
        )
        if article.dense is None:
            missing.append(news_id)
        else:
            try:
                units[news_id] = _normalize_dense(article.dense)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"news_id={news_id}: invalid dense vector: {exc}") from exc

    ids = sorted(units)
    pair_scores = {}
    for a, b in combinations(ids, 2):
        if (max_time_gap is None
                or abs(metadata[a].published_at - metadata[b].published_at) <= max_time_gap):
            pair_scores[a, b] = _unit_similarity(units[a], units[b])

    groups = [(news_id,) for news_id in ids]
    while True:
        best = None
        for left, right in combinations(groups, 2):
            score = _complete_link_score(left, right, pair_scores, threshold)
            if score is None:
                continue
            key = (left, right)
            if best is None or score > best[0] or (score == best[0] and key < best[1]):
                best = (score, key)
        if best is None:
            break
        left, right = best[1]
        groups.remove(left)
        groups.remove(right)
        groups.append(tuple(sorted(left + right)))
        groups.sort()

    clusters = []
    for group in groups:
        representative_id = min(group, key=lambda i: (metadata[i].published_at, i))
        minimum = min((pair_scores[a, b] for a, b in combinations(group, 2)), default=None)
        clusters.append(ClusterPreview(metadata[representative_id], group, minimum))
    return ClusteringResult(tuple(clusters), tuple(sorted(missing)))
