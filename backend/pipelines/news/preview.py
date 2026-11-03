"""DB 조회 행을 메모리에서 검증·변환하는 독립 클러스터링 미리보기.

DB·파일·네트워크·모델 접근은 없다. preview_articles()는 이름이 있는 매핑의
반복자를 받는다. 각 행의 필수 키는 PreviewRow와 같다. published_at은 시간대
있는 datetime, dense는 기존 clustering이 받는 숫자 Sequence여야 한다.
SQL의 id는 호출자가 news_id로, 언론사 이름은 publisher로 매핑해야 한다.
pgvector 문자열·JSON·시각 문자열의 암묵적 파싱은 하지 않는다.

LEFT JOIN에서 임베딩 행이 없는 경우를 표현하려면 model, variant, dense를
모두 None으로 전달한다. 일부만 NULL인 행은 누락이 아니라 입력 오류다.
추가 키는 사용하거나 응답에 복사하지 않는다. 입력과 벡터는 수정하지 않는다.

0.65·24시간·최대 100건은 소규모 개발용 미리보기 설정이며 운영 기준이 아니다.
hybrid 행의 dense 코사인만 사용한다. sparse 가중합을 계산하지 않는다.
오류는 PreviewValidationError로 중단하며 as_dict()로 종류·원인을 얻는다.
기존 cluster_articles의 예기치 않은 오류는 숨기거나 성공으로 바꾸지 않는다.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import math
from numbers import Real
from typing import TypedDict
from urllib.parse import urlsplit

from .clustering import (
    DEFAULT_MAX_TIME_GAP,
    DEFAULT_THRESHOLD,
    NewsArticle,
    cluster_articles,
    cosine_similarity,
)

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_VARIANT = "hybrid"
DEFAULT_MAX_ARTICLES = 100


class PreviewRow(TypedDict):
    """모든 키가 필수. model/variant/dense가 모두 None일 때만 임베딩 누락."""

    news_id: int
    title: str
    publisher: str
    published_at: datetime
    url: str
    model: str | None
    variant: str | None
    dense: Sequence[float] | None


class PreviewValidationError(ValueError):
    """부분 결과를 반환하지 않는 입력·옵션 검증 오류. 원본 벡터는 포함하지 않는다."""

    def __init__(self, code: str, reason: str, *, row_index: int | None = None,
                 news_id: int | None = None, field: str | None = None):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.row_index = row_index
        self.news_id = news_id
        self.field = field

    def as_dict(self) -> dict:
        return {
            "error_type": type(self).__name__, "code": self.code, "reason": self.reason,
            "row_index": self.row_index, "news_id": self.news_id, "field": self.field,
        }


_REQUIRED_FIELDS = tuple(PreviewRow.__annotations__)


def _convert_row(row: Mapping, index: int) -> tuple[NewsArticle | None, dict]:
    news_id = row["news_id"]
    context = {"row_index": index, "news_id": news_id}
    for field in ("title", "publisher", "url"):
        if not isinstance(row[field], str) or not row[field].strip():
            raise PreviewValidationError(
                "invalid_metadata", "필수 메타데이터는 공백이 아닌 문자열이어야 합니다",
                field=field, **context)
    try:
        parsed = urlsplit(row["url"])
        valid_url = (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and not any(char.isspace() or ord(char) < 32 for char in row["url"]))
        parsed.port  # 잘못된 포트·IPv6 표기는 ValueError로 거부한다.
    except ValueError:
        valid_url = False
    if not valid_url:
        raise PreviewValidationError(
            "invalid_url", "url에는 인증정보 없는 유효한 HTTP(S) 원문 URL이 필요합니다",
            field="url", **context)

    published_at = row["published_at"]
    try:
        if not isinstance(published_at, datetime) or published_at.utcoffset() is None:
            raise ValueError
        published_utc = published_at.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PreviewValidationError(
            "invalid_published_at", "published_at은 시간대가 있는 유효한 datetime이어야 합니다",
            field="published_at", **context) from exc
    display = {
        "news_id": news_id, "title": row["title"], "publisher": row["publisher"],
        "published_at": published_utc.isoformat(), "url": row["url"],
    }
    dense, model, variant = row["dense"], row["model"], row["variant"]
    if dense is None:
        if model is not None or variant is not None:
            raise PreviewValidationError(
                "inconsistent_embedding", "누락 임베딩은 dense·model·variant가 모두 None이어야 합니다",
                field="dense", **context)
        return None, display
    if model != EMBEDDING_MODEL:
        raise PreviewValidationError(
            "model_mismatch", "지원하는 임베딩 모델은 BAAI/bge-m3입니다",
            field="model", **context)
    if variant != EMBEDDING_VARIANT:
        raise PreviewValidationError(
            "variant_mismatch", "미리보기에는 hybrid 임베딩 행이 필요합니다",
            field="variant", **context)
    try:
        # 차원·숫자·유한값·norm 검증도 기존 공개 함수의 규칙을 재사용한다.
        cosine_similarity(dense, dense)
        frozen_dense = tuple(float(value) for value in dense)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PreviewValidationError(
            "invalid_dense", "dense에는 1,024개의 유한한 실수와 양의 유한 L2 norm이 필요합니다",
            field="dense", **context) from exc
    return NewsArticle(news_id, row["title"], row["publisher"], published_utc, frozen_dense), display


def preview_articles(
    rows: Iterable[Mapping[str, object]], *,
    threshold: float = DEFAULT_THRESHOLD,
    max_time_gap: timedelta | None = DEFAULT_MAX_TIME_GAP,
    max_articles: int = DEFAULT_MAX_ARTICLES,
) -> dict:
    """검증 후 기존 complete-link를 한 번 호출하고 JSON 직렬화 가능한 dict를 반환.

    모든 입력을 먼저 검증하므로 오류가 있으면 부분 군집 결과는 만들지 않는다.
    max_articles는 누락 임베딩을 포함한 입력 행 수에 적용한다.
    max_time_gap=None은 시간 제한 해제다. 시각은 UTC ISO 8601로 반환한다.
    생성 시각·난수·영구 사건 ID 없이 동일 입력과 설정의 결과를 결정적으로 유지한다.
    입력에 없는 기사나 임베딩의 누락 여부는 이 함수가 알 수 없다.
    """
    if isinstance(max_articles, bool) or not isinstance(max_articles, int) or max_articles <= 0:
        raise PreviewValidationError(
            "invalid_option", "max_articles는 양의 정수여야 합니다", field="max_articles")
    if (isinstance(threshold, bool) or not isinstance(threshold, Real)
            or not -1 <= threshold <= 1 or not math.isfinite(threshold)):
        raise PreviewValidationError(
            "invalid_option", "threshold는 -1 이상 1 이하의 유한한 실수여야 합니다",
            field="threshold")
    if max_time_gap is not None and (
        not isinstance(max_time_gap, timedelta) or max_time_gap < timedelta(0)
    ):
        raise PreviewValidationError(
            "invalid_option", "max_time_gap은 0 이상의 timedelta 또는 None이어야 합니다",
            field="max_time_gap")
    if isinstance(rows, (str, bytes, bytearray, Mapping)):
        raise PreviewValidationError("invalid_rows", "rows는 기사 매핑들의 반복자여야 합니다")
    try:
        iterator = iter(rows)
    except TypeError as exc:
        raise PreviewValidationError("invalid_rows", "rows는 기사 매핑들의 반복자여야 합니다") from exc

    metadata = {}
    valid = {}
    missing = []
    for index, row in enumerate(iterator):
        if index >= max_articles:
            raise PreviewValidationError(
                "article_limit_exceeded", "입력 기사 수가 max_articles를 초과했습니다", row_index=index)
        if not isinstance(row, Mapping):
            raise PreviewValidationError("invalid_row", "각 기사 행은 매핑이어야 합니다", row_index=index)
        absent = [name for name in _REQUIRED_FIELDS if name not in row]
        if absent:
            raise PreviewValidationError(
                "missing_fields", "필수 필드 누락: " + ", ".join(absent), row_index=index)
        news_id = row["news_id"]
        if isinstance(news_id, bool) or not isinstance(news_id, int) or news_id <= 0:
            raise PreviewValidationError(
                "invalid_news_id", "news_id는 양의 정수여야 합니다", row_index=index, field="news_id")
        if news_id in metadata:
            raise PreviewValidationError(
                "duplicate_news_id", "동일 news_id가 중복 입력됐습니다",
                row_index=index, news_id=news_id, field="news_id")
        article, display = _convert_row(row, index)
        metadata[news_id] = display
        if article is None:
            missing.append(news_id)
        else:
            valid[news_id] = article

    preview = cluster_articles(
        tuple(valid[i] for i in sorted(valid)),
        threshold=float(threshold), max_time_gap=max_time_gap,
    )
    groups = [{
        "representative_id": cluster.representative.news_id,
        "article_ids": list(cluster.article_ids),
        "article_count": cluster.article_count,
        "min_similarity": cluster.min_similarity,
        "representative": dict(metadata[cluster.representative.news_id]),
        "articles": [dict(metadata[i]) for i in cluster.article_ids],
    } for cluster in preview.clusters]
    return {
        "preview": True,
        "settings": {
            "threshold": float(threshold), "threshold_status": "experimental",
            "max_time_gap_seconds": max_time_gap.total_seconds() if max_time_gap is not None else None,
            "embedding_model": EMBEDDING_MODEL, "embedding_variant": EMBEDDING_VARIANT,
            "similarity_metric": "dense_cosine", "algorithm": "complete_link",
            "max_articles": max_articles,
        },
        "input_article_count": len(metadata),
        "processed_article_count": len(valid),
        "missing_embedding_ids": sorted(missing),
        "groups": groups,
    }
