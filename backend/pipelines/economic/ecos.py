
import os
import time
from datetime import date
from decimal import Decimal, InvalidOperation

import requests

from .redaction import scrub_exception


ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"


def fetch_ecos_series(
    series_code: str,
    start_date: date,
    end_date: date,
    max_attempts: int = 3,
) -> list[dict]:
    """ECOS 일별 시계열을 페이지 단위로 조회한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if max_attempts < 1:
        raise ValueError("max_attempts는 1 이상이어야 합니다.")

    api_key = os.getenv("ECOS_API_KEY")

    if not api_key:
        raise ValueError("ECOS_API_KEY가 설정되지 않았습니다.")

    stat_code, item_code = series_code.split("/", 1)

    all_rows = []
    page_size = 1000
    page_start = 1

    while True:
        page_end = page_start + page_size - 1

        url = (
            f"{ECOS_BASE_URL}/{api_key}/json/kr/"
            f"{page_start}/{page_end}/{stat_code}/D/"
            f"{start_date:%Y%m%d}/{end_date:%Y%m%d}/{item_code}"
        )

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                if "StatisticSearch" not in data:
                    raise ValueError(f"ECOS API 오류 응답: {data}")

                result = data["StatisticSearch"]

                rows = result.get("row", [])
                total_count = int(result["list_total_count"])

                if not isinstance(rows, list):
                    raise ValueError("ECOS row 형식 오류")

                all_rows.extend(rows)
                break

            except (
                requests.Timeout,
                requests.ConnectionError,
                requests.HTTPError,
            ) as exc:
                retryable = isinstance(
                    exc, (requests.Timeout, requests.ConnectionError)
                )

                if isinstance(exc, requests.HTTPError):
                    status = (
                        exc.response.status_code
                        if exc.response is not None
                        else None
                    )
                    retryable = status in {429, 500, 502, 503, 504}

                if not retryable or attempt == max_attempts:
                    # 요청 URL 경로에 키가 들어 있어 예외 메시지에서 가린다
                    scrub_exception(exc)
                    raise

                delay = min(2 ** (attempt - 1), 30)
                print(
                    f"[ECOS 재시도] {series_code} "
                    f"{attempt}/{max_attempts}, {delay}초 대기"
                )
                time.sleep(delay)

        if len(all_rows) >= total_count:
            break

        if not rows:
            raise ValueError("ECOS 페이지 응답이 비어 있어 수집을 중단합니다.")

        page_start += page_size

    return all_rows


def normalize_ecos_rows(
    indicator_code: str,
    rows: list[dict],
) -> list[dict]:
    """ECOS 원본 데이터를 economic_observations 저장용으로 정제한다."""

    normalized = []

    for row in rows:
        raw_date = str(row["TIME"]).strip()
        raw_value = str(row["DATA_VALUE"]).strip()

        if len(raw_date) != 8 or not raw_date.isdigit():
            raise ValueError(f"ECOS 날짜 형식 오류: {raw_date}")

        observation_date = date(
            int(raw_date[:4]),
            int(raw_date[4:6]),
            int(raw_date[6:8]),
        )

        if raw_value in {"", "-", "."}:
            continue

        try:
            value = Decimal(raw_value.replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError(
                f"ECOS 수치 변환 오류: {raw_value}"
            ) from exc

        if not value.is_finite():
            raise ValueError(f"ECOS 비정상 수치: {raw_value}")

        normalized.append({
            "indicator_code": indicator_code,
            "observation_date": observation_date,
            "value": value,
        })

    normalized.sort(key=lambda item: item["observation_date"])

    dates = [item["observation_date"] for item in normalized]

    if len(dates) != len(set(dates)):
        raise ValueError(f"ECOS 날짜 중복: {indicator_code}")

    return normalized



def extract_policy_rate_events(
    rows: list[dict],
    previous_value: Decimal | None = None,
) -> list[dict]:
    """
    ECOS 일별 기준금리에서 변경 이벤트만 추출한다.

    previous_value:
        수집 시작일 직전의 마지막 기준금리.
        None이면 첫 번째 관측치를 초기 상태로 저장한다.
    """

    if not rows:
        return []

    sorted_rows = sorted(
        rows,
        key=lambda item: item["observation_date"],
    )

    events = []
    last_value = previous_value

    for row in sorted_rows:
        current_value = row["value"]

        if last_value is None or current_value != last_value:
            events.append(row.copy())

        last_value = current_value

    return events
