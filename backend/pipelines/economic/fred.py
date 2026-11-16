
import os
import time
from datetime import date
from decimal import Decimal, InvalidOperation

import requests

from .redaction import scrub_exception


FRED_BASE_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
)


def fetch_fred_series(
    series_id: str,
    start_date: date,
    end_date: date,
    max_attempts: int = 3,
) -> list[dict]:
    """FRED 시계열 관측치를 조회한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if max_attempts < 1:
        raise ValueError("max_attempts는 1 이상이어야 합니다.")

    if not series_id:
        raise ValueError("FRED 시리즈 코드가 비어 있습니다.")

    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY가 설정되지 않았습니다.")

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date.isoformat(),
        "observation_end": end_date.isoformat(),
    }

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                FRED_BASE_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            rows = data.get("observations")

            if not isinstance(rows, list):
                raise ValueError(
                    f"FRED 응답 형식 오류: {series_id}"
                )

            return rows

        except (
            requests.Timeout,
            requests.ConnectionError,
            requests.HTTPError,
        ) as exc:
            retryable = isinstance(
                exc,
                (requests.Timeout, requests.ConnectionError),
            )

            if isinstance(exc, requests.HTTPError):
                status = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )
                retryable = status in {
                    429, 500, 502, 503, 504
                }

            if not retryable or attempt == max_attempts:
                # api_key 쿼리 파라미터가 예외 메시지의 URL에 남지 않게 가린다
                scrub_exception(exc)
                raise

            delay = min(2 ** (attempt - 1), 30)

            print(
                f"[FRED 재시도] {series_id} "
                f"{attempt}/{max_attempts}, "
                f"{delay}초 대기"
            )

            time.sleep(delay)

    raise RuntimeError("FRED 재시도 횟수 초과")


def normalize_fred_rows(
    indicator_code: str,
    rows: list[dict],
) -> list[dict]:
    """FRED 관측치를 economic_observations 저장용으로 정제한다."""

    normalized = []

    for row in rows:
        raw_date = str(row["date"]).strip()
        raw_value = str(row["value"]).strip()

        observation_date = date.fromisoformat(raw_date)

        # FRED 결측값은 0으로 대체하지 않는다.
        if raw_value in {"", ".", "-"}:
            continue

        try:
            value = Decimal(raw_value.replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError(
                f"FRED 수치 변환 오류: {raw_value}"
            ) from exc

        if not value.is_finite():
            raise ValueError(
                f"FRED 비정상 수치: {raw_value}"
            )

        normalized.append({
            "indicator_code": indicator_code,
            "observation_date": observation_date,
            "value": value,
        })

    normalized.sort(
        key=lambda item: item["observation_date"]
    )

    dates = [
        item["observation_date"]
        for item in normalized
    ]

    if len(dates) != len(set(dates)):
        raise ValueError(
            f"FRED 날짜 중복: {indicator_code}"
        )

    return normalized
