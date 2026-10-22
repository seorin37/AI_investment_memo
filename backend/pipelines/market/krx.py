import os
import time
import random
from datetime import date

import requests
from dotenv import load_dotenv


load_dotenv()

KRX_URL = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd"

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_kospi_daily(
    trade_date: date,
    max_attempts: int = 3,
) -> list[dict]:
    """KRX KOSPI 일별 데이터를 요청하고 일시적 오류만 재시도한다."""

    api_key = os.getenv("KRX_API_KEY")

    if not api_key:
        raise RuntimeError("KRX_API_KEY가 설정되지 않았습니다.")

    if max_attempts < 1:
        raise ValueError("max_attempts는 1 이상이어야 합니다.")

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                KRX_URL,
                headers={"AUTH_KEY": api_key},
                params={"basDd": trade_date.strftime("%Y%m%d")},
                timeout=30,
            )

            if response.status_code in RETRY_STATUS_CODES:
                response.raise_for_status()

            # 인증 오류(401/403), 잘못된 요청(400) 등은 재시도하지 않는다.
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("KRX 응답이 JSON 객체가 아닙니다.")

            rows = data.get("OutBlock_1")

            if not isinstance(rows, list):
                raise ValueError(
                    f"예상하지 못한 KRX 응답 형식: {str(data)[:300]}"
                )

            return rows

        except (requests.Timeout, requests.ConnectionError) as exc:
            retryable = True
            error = exc

        except requests.HTTPError as exc:
            retryable = (
                exc.response is not None
                and exc.response.status_code in RETRY_STATUS_CODES
            )
            error = exc

        if not retryable or attempt == max_attempts:
            raise error

        delay = min(2 ** (attempt - 1), 30) + random.uniform(0, 0.5)

        print(
            f"[KRX 재시도] {trade_date} "
            f"{attempt}/{max_attempts}, "
            f"{delay:.1f}초 대기: {error.__class__.__name__}"
        )

        time.sleep(delay)

    raise RuntimeError("KRX 요청 재시도 횟수를 초과했습니다.")


from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_number(value, *, integer=False):
    """KRX 문자열 숫자를 Python 숫자로 변환."""
    if value is None or str(value).strip() in ("", "-"):
        return None

    try:
        number = Decimal(str(value).replace(",", "").strip())
        if not number.is_finite():
            raise ValueError(f"유효하지 않은 숫자: {value}")

        if integer:
            if number != number.to_integral_value():
                raise ValueError(f"정수가 아닌 값: {value}")
            return int(number)

        return number
    except InvalidOperation as exc:
        raise ValueError(f"숫자 변환 실패: {value}") from exc


def normalize_kospi_row(row: dict) -> dict:
    """KRX API 응답 한 행을 prices_daily 형식으로 변환."""
    if row.get("MKT_NM") != "KOSPI":
        raise ValueError("KOSPI 데이터가 아닙니다.")

    symbol = str(row["ISU_CD"]).strip()

    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"잘못된 종목코드: {symbol}")

    result = {
        "symbol": symbol,
        "trade_date": datetime.strptime(
            row["BAS_DD"], "%Y%m%d"
        ).date(),
        "open": parse_number(row["TDD_OPNPRC"]),
        "high": parse_number(row["TDD_HGPRC"]),
        "low": parse_number(row["TDD_LWPRC"]),
        "close": parse_number(row["TDD_CLSPRC"]),
        "volume": parse_number(row["ACC_TRDVOL"], integer=True),
        "trade_value": parse_number(row.get("ACC_TRDVAL")),
        "market_cap": parse_number(row.get("MKTCAP")),
        "listed_shares": parse_number(
            row.get("LIST_SHRS"), integer=True
        ),
    }

    required = ("open", "high", "low", "close", "volume")

    for field in required:
        if result[field] is None:
            raise ValueError(
                f"{symbol}: 필수 필드 {field}가 비어 있습니다."
            )

    return result



def normalize_kospi_stock(row: dict) -> dict:
    """KRX 일별 시세 원본에서 KOSPI 종목 마스터 정보를 추출한다."""

    if row.get("MKT_NM") != "KOSPI":
        raise ValueError("KOSPI 종목이 아닙니다.")

    symbol = str(row.get("ISU_CD", "")).strip()
    name = str(row.get("ISU_NM") or "").strip()

    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"유효하지 않은 종목코드: {symbol}")

    if not name:
        raise ValueError(f"종목명이 없습니다: {symbol}")

    return {
        "symbol": symbol,
        "name": name,
        "market": "KOSPI",
        "sector": "general",
    }




def fetch_market_index_daily(
    trade_date: date,
    market: str,
    max_attempts: int = 3,
) -> dict:
    """KRX KOSPI/KOSDAQ 종합지수를 재시도 정책과 함께 조회한다."""

    api_ids = {
        "KOSPI": ("kospi_dd_trd", "코스피"),
        "KOSDAQ": ("kosdaq_dd_trd", "코스닥"),
    }

    if market not in api_ids:
        raise ValueError(f"지원하지 않는 시장: {market}")

    if max_attempts < 1:
        raise ValueError("max_attempts는 1 이상이어야 합니다.")

    api_id, index_name = api_ids[market]

    api_key = os.getenv("KRX_API_KEY")
    if not api_key:
        raise ValueError("KRX_API_KEY가 설정되지 않았습니다.")

    url = f"https://data-dbg.krx.co.kr/svc/apis/idx/{api_id}"
    retry_statuses = {429, 500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                headers={"AUTH_KEY": api_key},
                params={"basDd": trade_date.strftime("%Y%m%d")},
                timeout=30,
            )

            if response.status_code in retry_statuses:
                response.raise_for_status()

            response.raise_for_status()

            data = response.json()
            rows = data.get("OutBlock_1")

            if not isinstance(rows, list):
                raise ValueError(
                    "KRX 지수 API 응답 형식이 올바르지 않습니다."
                )

            matches = [
                row for row in rows
                if row.get("IDX_CLSS") == market
                and row.get("IDX_NM", "").strip() == index_name
            ]

            if not matches:
                if not rows:
                    return {}

                raise ValueError(
                    f"{market} 종합지수를 찾을 수 없습니다."
                )

            if len(matches) != 1:
                raise ValueError(
                    f"{market} 종합지수 중복 응답: {len(matches)}건"
                )

            return matches[0]

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
                retryable = status in retry_statuses

            if not retryable or attempt == max_attempts:
                raise

            delay = min(2 ** (attempt - 1), 30)

            print(
                f"[KRX 지수 재시도] {market} {trade_date} "
                f"{attempt}/{max_attempts}, "
                f"{delay}초 대기: {type(exc).__name__}"
            )

            time.sleep(delay)

    raise RuntimeError("KRX 지수 조회 재시도 횟수를 초과했습니다.")





def normalize_market_index(row: dict) -> dict:
    """KRX 종합지수 원본을 DB 저장용 데이터로 정제한다."""

    market = row.get("IDX_CLSS")
    expected_names = {
        "KOSPI": "코스피",
        "KOSDAQ": "코스닥",
    }

    if market not in expected_names:
        raise ValueError(f"지원하지 않는 지수 시장: {market}")

    if row.get("IDX_NM", "").strip() != expected_names[market]:
        raise ValueError("종합지수 데이터가 아닙니다.")

    result = {
        "market": market,
        "trade_date": date.fromisoformat(
            f"{row['BAS_DD'][:4]}-{row['BAS_DD'][4:6]}-{row['BAS_DD'][6:8]}"
        ),
        "open": parse_number(row.get("OPNPRC_IDX")),
        "high": parse_number(row.get("HGPRC_IDX")),
        "low": parse_number(row.get("LWPRC_IDX")),
        "close": parse_number(row.get("CLSPRC_IDX")),
        "change": parse_number(row.get("CMPPREVDD_IDX")),
        "change_rate": parse_number(row.get("FLUC_RT")),
        "volume": parse_number(row.get("ACC_TRDVOL"), integer=True),
        "trade_value": parse_number(row.get("ACC_TRDVAL")),
        "market_cap": parse_number(row.get("MKTCAP")),
    }

    # 가격 필수값 검증
    if any(
        result[key] is None
        for key in ("open", "high", "low", "close")
    ):
        raise ValueError(
            f"{market} {result['trade_date']} 지수 가격 누락"
        )

    return result




def fetch_gold_daily(
    trade_date: date,
    max_attempts: int = 3,
) -> dict:
    """KRX 금 99.99K 일별 원본 데이터를 조회한다."""

    if max_attempts < 1:
        raise ValueError("max_attempts는 1 이상이어야 합니다.")

    api_key = os.getenv("KRX_API_KEY")
    if not api_key:
        raise ValueError("KRX_API_KEY가 설정되지 않았습니다.")

    url = "https://data-dbg.krx.co.kr/svc/apis/gen/gold_bydd_trd"
    retry_statuses = {429, 500, 502, 503, 504}

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                headers={"AUTH_KEY": api_key},
                params={"basDd": trade_date.strftime("%Y%m%d")},
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            rows = data.get("OutBlock_1")

            if not isinstance(rows, list):
                raise ValueError("KRX 금시장 응답 형식이 올바르지 않습니다.")

            matches = [
                row for row in rows
                if str(row.get("ISU_CD", "")).strip() == "04020000"
            ]

            if not matches:
                if not rows:
                    return {}

                raise ValueError("금 99.99K 종목을 찾을 수 없습니다.")

            if len(matches) != 1:
                raise ValueError("금 99.99K 종목이 중복 반환됐습니다.")

            return matches[0]

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
                retryable = status in retry_statuses

            if not retryable or attempt == max_attempts:
                raise

            delay = min(2 ** (attempt - 1), 30)
            print(
                f"[KRX 금 재시도] {trade_date} "
                f"{attempt}/{max_attempts}, {delay}초 대기"
            )
            time.sleep(delay)

    raise RuntimeError("KRX 금시장 조회 재시도 횟수 초과")




def normalize_gold_row(row: dict) -> dict:
    """KRX 금 99.99K 원본을 DB 저장용으로 정제한다."""

    symbol = str(row.get("ISU_CD", "")).strip()

    if symbol != "04020000":
        raise ValueError(f"수집 대상이 아닌 금 상품: {symbol}")

    trade_date = date.fromisoformat(
        f"{row['BAS_DD'][:4]}-{row['BAS_DD'][4:6]}-{row['BAS_DD'][6:8]}"
    )

    result = {
        "product_code": symbol,
        "trade_date": trade_date,
        "open": parse_number(row.get("TDD_OPNPRC")),
        "high": parse_number(row.get("TDD_HGPRC")),
        "low": parse_number(row.get("TDD_LWPRC")),
        "close": parse_number(row.get("TDD_CLSPRC")),
        "volume": parse_number(row.get("ACC_TRDVOL"), integer=True),
        "trade_value": parse_number(row.get("ACC_TRDVAL")),
    }

    # 금 종가는 DB에서 NOT NULL이므로 반드시 확인
    if result["close"] is None or result["close"] <= 0:
        raise ValueError("금 종가가 누락되었거나 유효하지 않습니다.")

    # 가격 관계 검증
    prices = [result[k] for k in ("open", "high", "low", "close")]

    if all(p is not None for p in prices):
        if (
            result["high"] < result["low"]
            or result["high"] < result["open"]
            or result["high"] < result["close"]
            or result["low"] > result["open"]
            or result["low"] > result["close"]
        ):
            raise ValueError("금 OHLC 가격 관계가 올바르지 않습니다.")

    return result

