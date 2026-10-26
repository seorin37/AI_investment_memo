"""미리보기용 제한된 SELECT 조회. 연결 생성·환경설정·트랜잭션 종료는 하지 않는다.

fetch_preview_rows()는 psycopg 3 호환 connection을 빌린다. 호출자는 autocommit=False,
이미 시작된 읽기 전용 트랜잭션, 배타적으로 사용하는 연결을 제공해야 한다.
info.transaction_status.name == 'INTRANS'와 서버 transaction_read_only='on'을
확인할 수 없으면 조회를 거부한다. 성공·실패 모두 commit/rollback/close는 호출자 책임이다.
backend.app.db.get_session()은 성공 시 commit하므로 이 계약과 구분해야 한다.

실제 컬럼 근거: 0001 SQL의 news_articles/source_id → news_sources/id,
0006의 news_embedding_variants(news_id, variant, model, dense vector(1024)).
dense::text를 JSON 숫자 목록으로 파싱하므로 pgvector 어댑터 등록은 필요 없다.

조회 기간은 [since, until), 최대 7일이며 기사 제한은 1~100건이다.
limit+1 센티널을 조회해 범위에 기사가 더 있으면 조용히 자르지 않고 오류를 낸다.
기사 제한을 JOIN 전에 적용하고 바깥 SELECT도 제한해 중복 JOIN 결과를 제한한다.
같은 DB 스냅샷에서 발행시각·ID 순서가 결정적이다.

모델·variant 조건은 LEFT JOIN의 ON에 둔다. 다른 모델의 hybrid만 있으면
요청한 모델의 임베딩은 미보유로 반환한다. 모든 hybrid 행 수를 별도로 확인해
모델 필터가 같은 기사·variant의 중복·상충 행을 숨기지 않게 한다.
이 모듈은 군집 계산도 하지 않는다. 결과를 preview_articles()에 전달하면 된다.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import json

from .clustering import cosine_similarity
from .preview import DEFAULT_MAX_ARTICLES, EMBEDDING_MODEL, EMBEDDING_VARIANT, PreviewRow

MAX_QUERY_SPAN = timedelta(days=7)
MAX_QUERY_ARTICLES = DEFAULT_MAX_ARTICLES

READ_ONLY_SQL = "SELECT current_setting('transaction_read_only') AS transaction_read_only"

PREVIEW_SQL = """
SELECT a.id AS news_id, a.title, s.name AS publisher, a.published_at, a.url,
       v.news_id AS embedding_news_id, v.model, v.variant, v.dense::text AS dense,
       (SELECT count(*) FROM news_embedding_variants AS check_v
        WHERE check_v.news_id = a.id AND check_v.variant = %s) AS variant_row_count,
       (SELECT count(*) FROM news_embedding_variants AS bad_v
        WHERE bad_v.news_id = a.id AND bad_v.variant = %s
          AND (bad_v.model IS NULL OR bad_v.dense IS NULL)) AS incomplete_row_count
FROM (
    SELECT id, title, source_id, published_at, url
    FROM news_articles
    WHERE published_at >= %s AND published_at < %s
    ORDER BY published_at, id
    LIMIT %s
) AS a
LEFT JOIN news_sources AS s ON s.id = a.source_id
LEFT JOIN news_embedding_variants AS v
    ON v.news_id = a.id AND v.model = %s AND v.variant = %s
ORDER BY a.published_at, a.id
LIMIT %s
"""
_COLUMNS = ("news_id", "title", "publisher", "published_at", "url",
            "embedding_news_id", "model", "variant", "dense", "variant_row_count", "incomplete_row_count")


class PreviewRepositoryError(ValueError):
    """조회 조건·읽기 전용 보장·행 무결성·SELECT 실패. 원본 DB 오류 문자열은 숨긴다."""

    def __init__(self, code: str, reason: str, *, news_id: int | None = None,
                 cause_type: str | None = None):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.news_id = news_id
        self.cause_type = cause_type

    def as_dict(self) -> dict:
        return {"error_type": type(self).__name__, "code": self.code, "reason": self.reason,
                "news_id": self.news_id, "cause_type": self.cause_type}


def _utc(value, field: str) -> datetime:
    try:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise PreviewRepositoryError(
            "invalid_time", field + "에는 시간대가 있는 유효한 datetime이 필요합니다") from None


def _require_active_transaction(connection) -> None:
    status = getattr(getattr(connection, "info", None), "transaction_status", None)
    if (getattr(connection, "autocommit", None) is not False
            or getattr(status, "name", None) != "INTRANS"):
        raise PreviewRepositoryError(
            "transaction_required", "autocommit=False인 연결의 활성 트랜잭션이 필요합니다")


def _named_row(raw, columns: tuple[str, ...]) -> dict:
    if isinstance(raw, Mapping):
        if any(name not in raw for name in columns):
            raise PreviewRepositoryError("invalid_result", "SELECT 결과의 필수 컬럼이 누락됐습니다")
        return {name: raw[name] for name in columns}
    if not isinstance(raw, (tuple, list)) or len(raw) != len(columns):
        raise PreviewRepositoryError("invalid_result", "SELECT 결과 행의 형식·컬럼 수가 다릅니다")
    return dict(zip(columns, raw))


def _convert_row(raw, since: datetime, until: datetime) -> PreviewRow:
    record = _named_row(raw, _COLUMNS)
    news_id = record["news_id"]
    if isinstance(news_id, bool) or not isinstance(news_id, int) or news_id <= 0:
        raise PreviewRepositoryError("invalid_metadata", "기사 ID는 양의 정수여야 합니다")
    for field in ("title", "publisher", "url"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise PreviewRepositoryError(
                "invalid_metadata", field + "의 기사 메타데이터가 없거나 잘못됐습니다", news_id=news_id)
    published_at = _utc(record["published_at"], "published_at")
    if not since <= published_at < until:
        raise PreviewRepositoryError(
            "outside_window", "조회 기간 밖 기사가 반환됐습니다", news_id=news_id)

    count = record["variant_row_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise PreviewRepositoryError("invalid_result", "variant 행 수가 잘못됐습니다", news_id=news_id)
    if count > 1:
        raise PreviewRepositoryError(
            "embedding_conflict", "동일 기사·variant에 중복 또는 상충하는 행이 있습니다", news_id=news_id)
    incomplete = record["incomplete_row_count"]
    if (isinstance(incomplete, bool) or not isinstance(incomplete, int)
            or not 0 <= incomplete <= count):
        raise PreviewRepositoryError("invalid_result", "불완전 임베딩 행 수가 잘못됐습니다", news_id=news_id)
    if incomplete:
        raise PreviewRepositoryError(
            "incomplete_embedding", "모델 필터 이전의 hybrid 행에 필수 값 NULL이 있습니다", news_id=news_id)
    embedding_id = record["embedding_news_id"]
    model, variant, raw_dense = record["model"], record["variant"], record["dense"]
    if embedding_id is None:
        if any(value is not None for value in (model, variant, raw_dense)):
            raise PreviewRepositoryError(
                "incomplete_embedding", "임베딩 미보유 행에 일부 값만 존재합니다", news_id=news_id)
        dense = None
    else:
        if (isinstance(embedding_id, bool) or not isinstance(embedding_id, int)
                or embedding_id != news_id or count != 1):
            raise PreviewRepositoryError(
                "embedding_conflict", "임베딩 기사 ID 또는 행 수가 일치하지 않습니다", news_id=news_id)
        if any(value is None for value in (model, variant, raw_dense)):
            raise PreviewRepositoryError(
                "incomplete_embedding", "기존 임베딩 행의 필수 값이 NULL입니다", news_id=news_id)
        if model != EMBEDDING_MODEL or variant != EMBEDDING_VARIANT:
            raise PreviewRepositoryError(
                "embedding_mismatch", "다른 모델 또는 variant가 조회 결과에 섞였습니다", news_id=news_id)
        if not isinstance(raw_dense, str):
            raise PreviewRepositoryError(
                "invalid_dense", "dense::text의 문자열 결과가 필요합니다", news_id=news_id)
        try:
            dense = json.loads(raw_dense)
            # 벡터 규칙은 기존 공개 검증을 재사용한다. 군집 계산은 하지 않는다.
            cosine_similarity(dense, dense)
        except (TypeError, ValueError, OverflowError, RecursionError):
            raise PreviewRepositoryError(
                "invalid_dense", "dense는 1,024차원 유한 실수·양의 유한 norm이어야 합니다",
                news_id=news_id) from None
    return {
        "news_id": news_id, "title": record["title"], "publisher": record["publisher"],
        "published_at": published_at, "url": record["url"],
        "model": model, "variant": variant, "dense": dense,
    }


def fetch_preview_rows(
    connection, since: datetime, until: datetime, *,
    max_articles: int = DEFAULT_MAX_ARTICLES,
    model: str = EMBEDDING_MODEL,
    variant: str = EMBEDDING_VARIANT,
) -> list[PreviewRow]:
    """외부에서 받은 connection으로 SELECT만 실행해 preview_articles 입력 행 목록을 반환.

    잘못된 조건은 SQL 전에 거부한다. 읽기 전용 상태를 확인하는 SELECT와
    제한된 기사 SELECT를 같은 활성 트랜잭션에서 실행한다. 반환 시 UTC datetime과
    파싱된 벡터를 사용하며 connection 설정·수명·트랜잭션을 변경하지 않는다.
    URL의 공개 HTTP(S) 형식 등 최종 표시용 검증은 preview_articles가 수행한다.
    """
    since, until = _utc(since, "since"), _utc(until, "until")
    if not since < until or until - since > MAX_QUERY_SPAN:
        raise PreviewRepositoryError("invalid_window", "조회 기간은 양수이며 최대 7일이어야 합니다")
    if (isinstance(max_articles, bool) or not isinstance(max_articles, int)
            or not 1 <= max_articles <= MAX_QUERY_ARTICLES):
        raise PreviewRepositoryError("invalid_limit", "max_articles는 1~100의 정수여야 합니다")
    if model != EMBEDDING_MODEL or variant != EMBEDDING_VARIANT:
        raise PreviewRepositoryError("invalid_embedding_option", "BAAI/bge-m3·hybrid만 조회할 수 있습니다")
    _require_active_transaction(connection)

    phase = "cursor"
    try:
        with connection.cursor() as cursor:
            phase = "read_only_check"
            cursor.execute(READ_ONLY_SQL)
            readonly = _named_row(cursor.fetchone(), ("transaction_read_only",))
            if readonly["transaction_read_only"] != "on":
                raise PreviewRepositoryError("read_only_required", "읽기 전용 트랜잭션이 확인되지 않았습니다")
            _require_active_transaction(connection)
            phase = "article_select"
            probe_limit = max_articles + 1
            cursor.execute(PREVIEW_SQL, (
                variant, variant, since, until, probe_limit, model, variant, probe_limit,
            ))
            raw_rows = cursor.fetchall()
            _require_active_transaction(connection)
    except PreviewRepositoryError:
        raise
    except Exception as exc:
        raise PreviewRepositoryError(
            "query_failed", phase + " SELECT 처리에 실패했습니다",
            cause_type=type(exc).__name__) from None
    if not isinstance(raw_rows, (list, tuple)):
        raise PreviewRepositoryError("invalid_result", "fetchall은 행 목록을 반환해야 합니다")
    if len(raw_rows) > max_articles + 1:
        raise PreviewRepositoryError("limit_exceeded", "제한보다 많은 SELECT 결과가 반환됐습니다")

    result = []
    seen = set()
    for raw in raw_rows:
        row = _convert_row(raw, since, until)
        if row["news_id"] in seen:
            raise PreviewRepositoryError(
                "duplicate_article", "동일 기사 ID가 중복 반환됐습니다", news_id=row["news_id"])
        seen.add(row["news_id"])
        result.append(row)
    if len(result) > max_articles:
        raise PreviewRepositoryError(
            "limit_exceeded", "조회 기간의 기사 수가 제한을 초과했습니다. 기간을 좁혀 주세요")
    return sorted(result, key=lambda row: (row["published_at"], row["news_id"]))
