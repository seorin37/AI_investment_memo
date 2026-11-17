"""ECOS·FRED API 키가 예외 메시지·상태 파일·로그에 남지 않게 가린다."""

from __future__ import annotations

import os
import re
from typing import Any


MASK = "***"

# 환경변수에 들어 있는 실제 키 값도 함께 가린다 (형식과 무관하게 남는 경우 대비).
SECRET_ENV_NAMES = ("ECOS_API_KEY", "FRED_API_KEY")
_MIN_LITERAL_LENGTH = 8

# ECOS: https://ecos.bok.or.kr/api/StatisticSearch/<KEY>/json/...
#       urllib3 메시지처럼 호스트 없이 경로만 남는 경우도 포함
_ECOS_PATH_KEY = re.compile(
    r"(/api/(?:Statistic[A-Za-z]*|KeyStatisticList)/)[^/?#\s'\"]+"
)
# FRED: ...?series_id=DGS2&api_key=<KEY>&...  (HTML 이스케이프된 &amp; 포함)
_QUERY_API_KEY = re.compile(
    r"((?:[?&]|&amp;)api_key=)[^&#\s'\"]+",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """문자열 안의 ECOS 경로 키와 api_key 쿼리 값을 ***로 바꾼다."""

    if not text:
        return text
    redacted = _ECOS_PATH_KEY.sub(rf"\g<1>{MASK}", text)
    redacted = _QUERY_API_KEY.sub(rf"\g<1>{MASK}", redacted)
    for name in SECRET_ENV_NAMES:
        value = (os.getenv(name) or "").strip()
        if len(value) >= _MIN_LITERAL_LENGTH:
            redacted = redacted.replace(value, MASK)
    return redacted


def redact_value(value: Any) -> Any:
    """상태 JSON처럼 중첩된 dict·list 안의 문자열을 모두 가린다."""

    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {redact_value(key): redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def error_message(exc: BaseException) -> str:
    """저장·출력용 예외 메시지. 키를 가린 문자열만 돌려준다."""

    return redact_secrets(str(exc))


def scrub_exception(exc: BaseException) -> BaseException:
    """다시 던질 예외의 메시지에서 키를 가린다. 예외 타입과 response 속성은 유지한다.

    requests 예외의 원인(urllib3 MaxRetryError 등)에도 URL이 들어 있으므로
    연결된 원인 예외의 메시지도 함께 가린다.
    """

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        try:
            current.args = tuple(
                redact_secrets(arg) if isinstance(arg, str) else
                redact_secrets(str(arg)) if isinstance(arg, BaseException) else arg
                for arg in current.args
            )
        except (AttributeError, TypeError):
            pass
        current = current.__cause__ or current.__context__
    return exc
