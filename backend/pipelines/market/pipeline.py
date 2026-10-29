"""KRX market-index and gold collection pipeline.

Individual-stock OHLCV is collected by pipelines.market.kis.
"""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .calendar import is_krx_trading_day
from .krx import fetch_gold_daily, fetch_market_index_daily
from .krx import normalize_gold_row, normalize_market_index


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FAILURE_DIR = PROJECT_ROOT / "logs" / "market"


def save_market_index(index_data: dict) -> int:
    """KOSPI/KOSDAQ 종합지수 일별 데이터를 DB에 UPSERT한다."""

    if not index_data:
        return 0

    market = index_data["market"]

    if market not in {"KOSPI", "KOSDAQ"}:
        raise ValueError(f"지원하지 않는 지수: {market}")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL이 설정되지 않았습니다.")

    stmt = text("""
        INSERT INTO market_indices (
            code,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            trade_value,
            market_cap
        )
        VALUES (
            :code,
            :trade_date,
            :open,
            :high,
            :low,
            :close,
            :volume,
            :trade_value,
            :market_cap
        )
        ON CONFLICT (code, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trade_value = EXCLUDED.trade_value,
            market_cap = EXCLUDED.market_cap
    """)

    params = {
        "code": market,
        "trade_date": index_data["trade_date"],
        "open": index_data["open"],
        "high": index_data["high"],
        "low": index_data["low"],
        "close": index_data["close"],
        "volume": index_data["volume"],
        "trade_value": index_data["trade_value"],
        "market_cap": index_data["market_cap"],
    }

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.begin() as conn:
            conn.execute(stmt, params)
    finally:
        engine.dispose()

    return 1



def index_state_file(state_type: str) -> Path:
    """KRX 지수 수집 완료·실패 기록의 파일 경로."""

    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    return FAILURE_DIR / f"krx_indices_{state_type}.json"


def load_index_state(state_type: str) -> dict:
    """KRX 지수 수집 상태를 불러온다."""

    path = index_state_file(state_type)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("KRX 지수 상태 JSON 형식이 올바르지 않습니다.")

    return data


def save_index_state(state_type: str, state: dict) -> None:
    """KRX 지수 수집 상태를 저장한다."""

    path = index_state_file(state_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    temp_path.replace(path)





def backfill_market_indices(
    start_date: date,
    end_date: date,
    request_interval: float = 0.5,
    resume: bool = True,
) -> dict:
    """KOSPI/KOSDAQ 지수를 날짜별로 수집하고 완료·실패 상태를 관리한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    markets = ("KOSPI", "KOSDAQ")

    completed = load_index_state("completed")
    failed = load_index_state("failed")

    results = {
        "success": 0,
        "skipped_completed": 0,
        "skipped_holidays": 0,
        "empty_market": 0,
        "failed": [],
    }

    current_date = start_date

    while current_date <= end_date:
        # 휴장일은 API 호출 없이 건너뛰기
        if not is_krx_trading_day(current_date):
            results["skipped_holidays"] += 1
            print(f"[지수 휴장일] {current_date}")
            current_date += timedelta(days=1)
            continue

        for market in markets:
            state_key = f"{current_date.isoformat()}:{market}"

            # 실패 기록이 없고 이미 완료됐다면 건너뛰기
            if (
                resume
                and state_key in completed
                and state_key not in failed
            ):
                results["skipped_completed"] += 1
                print(f"[지수 완료 건너뛰기] {state_key}")
                continue

            print(f"[지수 수집 시작] {state_key}")

            try:
                raw = fetch_market_index_daily(
                    trade_date=current_date,
                    market=market,
                )

                if not raw:
                    completed.pop(state_key, None)
                    failed[state_key] = {
                        "error_type": "EmptyMarket",
                        "error": "KRX 지수 응답이 비어 있습니다.",
                    }
                    results["empty_market"] += 1
                    print(f"  지수 데이터 없음 - 확인 필요: {state_key}")

                else:
                    normalized = normalize_market_index(raw)

                    if (
                        normalized["market"] != market
                        or normalized["trade_date"] != current_date
                    ):
                        raise ValueError(
                            f"지수 식별 정보 불일치: {state_key}"
                        )

                    saved = save_market_index(normalized)

                    if saved != 1:
                        raise ValueError(
                            f"지수 저장 건수 이상: {state_key}, {saved}건"
                        )

                    completed[state_key] = {"status": "success"}
                    failed.pop(state_key, None)

                    results["success"] += 1
                    print(f"  지수 저장 완료: {state_key}")

            except Exception as exc:
                completed.pop(state_key, None)
                failed[state_key] = {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

                results["failed"].append(state_key)
                print(f"  지수 수집 실패: {state_key}: {exc}")

            finally:
                # 성공·실패·빈 응답 모두 즉시 기록
                save_index_state("completed", completed)
                save_index_state("failed", failed)

                # 빈 응답이나 예외가 발생해도 요청 간격 유지
                if request_interval > 0:
                    time.sleep(request_interval)

        current_date += timedelta(days=1)

    results["remaining_failures"] = len(failed)

    return results


def save_gold_price(gold_data: dict) -> int:
    """KRX 금 99.99K 일별 가격을 PostgreSQL에 UPSERT한다."""

    if not gold_data:
        return 0

    if gold_data["product_code"] != "04020000":
        raise ValueError("지원하지 않는 금 상품입니다.")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL이 설정되지 않았습니다.")

    stmt = text("""
        INSERT INTO commodity_prices_daily (
            product_code,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            trade_value
        )
        VALUES (
            :product_code,
            :trade_date,
            :open,
            :high,
            :low,
            :close,
            :volume,
            :trade_value
        )
        ON CONFLICT (product_code, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trade_value = EXCLUDED.trade_value
    """)

    params = {
        "product_code": gold_data["product_code"],
        "trade_date": gold_data["trade_date"],
        "open": gold_data["open"],
        "high": gold_data["high"],
        "low": gold_data["low"],
        "close": gold_data["close"],
        "volume": gold_data["volume"],
        "trade_value": gold_data["trade_value"],
    }

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.begin() as conn:
            conn.execute(stmt, params)
    finally:
        engine.dispose()

    return 1



def gold_state_file(state_type: str) -> Path:
    """KRX 금 수집 완료·실패 기록 파일 경로."""

    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    return FAILURE_DIR / f"krx_gold_{state_type}.json"


def load_gold_state(state_type: str) -> dict:
    """KRX 금 수집 상태를 읽는다."""

    path = gold_state_file(state_type)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("KRX 금 수집 상태 JSON 형식이 올바르지 않습니다.")

    return data


def save_gold_state(state_type: str, state: dict) -> None:
    """KRX 금 수집 상태를 JSON으로 저장한다."""

    path = gold_state_file(state_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    temp_path.replace(path)



def backfill_gold_prices(
    start_date: date,
    end_date: date,
    request_interval: float = 0.5,
    resume: bool = True,
) -> dict:
    """KRX 금 99.99K의 일별 가격을 수집한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    completed = load_gold_state("completed")
    failed = load_gold_state("failed")

    results = {
        "success": 0,
        "skipped_completed": 0,
        "skipped_holidays": 0,
        "empty_market": 0,
        "failed": [],
    }

    current_date = start_date

    while current_date <= end_date:
        date_key = current_date.isoformat()

        # 기본적으로 XKRX 캘린더 사용
        if not is_krx_trading_day(current_date):
            results["skipped_holidays"] += 1
            print(f"[금 휴장일 건너뛰기] {date_key}")
            current_date += timedelta(days=1)
            continue

        if resume and date_key in completed and date_key not in failed:
            results["skipped_completed"] += 1
            print(f"[금 수집 완료 건너뛰기] {date_key}")
            current_date += timedelta(days=1)
            continue

        print(f"[금 수집 시작] {date_key}")

        try:
            raw = fetch_gold_daily(current_date)

            if not raw:
                completed.pop(date_key, None)
                failed[date_key] = {
                    "error_type": "EmptyMarket",
                    "error": "KRX 금 99.99K 응답이 비어 있습니다.",
                }
                results["empty_market"] += 1
                print(f"  금 데이터 없음 - 확인 필요: {date_key}")

            else:
                normalized = normalize_gold_row(raw)

                if normalized["trade_date"] != current_date:
                    raise ValueError(
                        f"금 거래일 불일치: 요청={date_key}, "
                        f"응답={normalized['trade_date']}"
                    )

                saved = save_gold_price(normalized)

                if saved != 1:
                    raise ValueError(
                        f"금 저장 건수 이상: {date_key}, {saved}건"
                    )

                completed[date_key] = {
                    "status": "success",
                    "product_code": "04020000",
                }
                failed.pop(date_key, None)

                results["success"] += 1
                print(f"  금 저장 완료: {date_key}")

        except Exception as exc:
            completed.pop(date_key, None)
            failed[date_key] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            results["failed"].append(date_key)
            print(f"  금 수집 실패: {date_key}: {exc}")

        finally:
            save_gold_state("completed", completed)
            save_gold_state("failed", failed)

            # 빈 응답이나 오류 발생 시에도 요청 간격 유지
            if request_interval > 0:
                time.sleep(request_interval)

        current_date += timedelta(days=1)

    results["remaining_failures"] = len(failed)
    return results
