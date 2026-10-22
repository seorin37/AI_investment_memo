
import os
import time
from datetime import date, timedelta
from .calendar import is_krx_trading_day

import json
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text



from .krx import fetch_gold_daily, normalize_gold_row
from .krx import fetch_market_index_daily, normalize_market_index
from .krx import (
    fetch_kospi_daily,
    normalize_kospi_row,
    normalize_kospi_stock,
)


load_dotenv()

TEST_SYMBOLS = {
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "105560",  # KB금융
}


# 프로젝트 루트 기준으로 실패 기록 저장
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FAILURE_DIR = PROJECT_ROOT / "logs" / "market"


def failure_file(scope: str) -> Path:
    """수집 범위별 실패 기록 경로."""
    if scope not in {"test", "all"}:
        raise ValueError(f"잘못된 수집 범위: {scope}")

    return FAILURE_DIR / f"krx_failed_{scope}.json"


def load_failures(scope: str) -> dict:
    """기존 실패 기록을 읽는다."""
    path = failure_file(scope)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("실패 기록 JSON 형식이 올바르지 않습니다.")

    return data


def save_failures(scope: str, failures: dict) -> None:
    """실패 기록을 JSON으로 저장한다."""
    path = failure_file(scope)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 작성 중 오류가 나도 기존 파일을 보존하도록 임시 파일 사용
    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)

    temp_path.replace(path)



def completion_file(scope: str) -> Path:
    """수집 완료 날짜 기록 파일 경로."""
    if scope not in {"test", "all"}:
        raise ValueError(f"잘못된 수집 범위: {scope}")

    return FAILURE_DIR / f"krx_completed_{scope}.json"


def load_completions(scope: str) -> dict:
    """기존 수집 완료 기록을 읽는다."""
    path = completion_file(scope)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("수집 완료 기록 JSON 형식이 올바르지 않습니다.")

    return data


def save_completions(scope: str, completions: dict) -> None:
    """완료 날짜를 JSON 파일에 저장한다."""
    path = completion_file(scope)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(completions, f, ensure_ascii=False, indent=2)

    temp_path.replace(path)



def save_prices(rows: list[dict]) -> int:
    """KRX 주가 데이터를 PostgreSQL에 UPSERT."""

    if not rows:
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")

    engine = create_engine(database_url, pool_pre_ping=True)

    query = text("""
        INSERT INTO prices_daily (
            symbol, trade_date, open, high, low, close,
            volume, trade_value, market_cap, listed_shares
        )
        VALUES (
            :symbol, :trade_date, :open, :high, :low, :close,
            :volume, :trade_value, :market_cap, :listed_shares
        )
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trade_value = EXCLUDED.trade_value,
            market_cap = EXCLUDED.market_cap,
            listed_shares = EXCLUDED.listed_shares
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, rows)
    finally:
        engine.dispose()

    return len(rows)



def save_stocks_and_prices(raw_rows: list[dict]) -> int:
    """KOSPI 종목 마스터와 일별 주가를 하나의 트랜잭션으로 저장한다."""

    if not raw_rows:
        return 0

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL이 설정되지 않았습니다.")

    # 1. DB 작업 전에 모든 원본 데이터 정제
    stocks_by_symbol = {}
    price_rows = []

    for row in raw_rows:
        stock = normalize_kospi_stock(row)
        price = normalize_kospi_row(row)

        stocks_by_symbol[stock["symbol"]] = stock
        price_rows.append(price)

    stock_rows = list(stocks_by_symbol.values())

    # 2. 종목 마스터 INSERT
    stock_stmt = text("""
        INSERT INTO stocks (
            symbol,
            name,
            market,
            sector,
            updated_at
        )
        VALUES (
            :symbol,
            :name,
            :market,
            :sector,
            NOW()
        )
        ON CONFLICT (symbol) DO NOTHING
    """)

    # 3. 일별 주가 UPSERT
    price_stmt = text("""
        INSERT INTO prices_daily (
            symbol,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            trade_value,
            market_cap,
            listed_shares
        )
        VALUES (
            :symbol,
            :trade_date,
            :open,
            :high,
            :low,
            :close,
            :volume,
            :trade_value,
            :market_cap,
            :listed_shares
        )
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trade_value = EXCLUDED.trade_value,
            market_cap = EXCLUDED.market_cap,
            listed_shares = EXCLUDED.listed_shares
    """)

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        # 4. 종목 등록과 가격 저장을 동일 트랜잭션에서 실행
        with engine.begin() as conn:
            conn.execute(stock_stmt, stock_rows)
            conn.execute(price_stmt, price_rows)

    finally:
        engine.dispose()

    return len(price_rows)




def collect_prices(
    trade_date: date,
    symbols: set[str] | None = None,
) -> dict:
    """KRX 전체 응답과 필터링 결과를 구분하여 수집한다."""

    # 1. 해당 날짜의 KOSPI 전체 데이터 조회
    raw_rows = fetch_kospi_daily(trade_date)

    # 2. 전체 KOSPI 응답이 비어 있는 경우
    if not raw_rows:
        return {
            "status": "empty_market",
            "saved_rows": 0,
            "market_rows": 0,
        }

    # 3. 테스트 대상 종목만 선택 (전체 수집이면 필터링 생략)
    if symbols is not None:
        selected_rows = [
            row for row in raw_rows
            if row["ISU_CD"] in symbols
        ]
    else:
        selected_rows = raw_rows

    # 4. 선택된 종목이 없는 경우
    if not selected_rows:
        return {
            "status": "no_matching_symbols",
            "saved_rows": 0,
            "market_rows": len(raw_rows),
        }

    # 5. 정제 및 DB 저장
    normalized_rows = [
        normalize_kospi_row(row)
        for row in selected_rows
    ]

    saved = save_prices(normalized_rows)

    return {
        "status": "success",
        "saved_rows": saved,
        "market_rows": len(raw_rows),
    }






def backfill_prices(
    start_date: date,
    end_date: date,
    symbols: set[str] | None = None,
    request_interval: float = 0.5,
    scope: str = "test",
    resume: bool = True,
) -> dict:
    """기간별 주가 수집. 완료 날짜는 재실행 시 건너뛴다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    failure_file(scope)

    if scope != "test" or symbols != TEST_SYMBOLS:
        raise ValueError("현재는 테스트 4개 종목 수집만 지원합니다.")

    failures = load_failures(scope)
    completions = load_completions(scope)

    results = {
        "success_dates": 0,
        "empty_dates": 0,
        "no_matching_dates": 0,
        "skipped_completed": 0,
        "failed_dates": [],
        "total_rows": 0,
    }

    current_date = start_date

    while current_date <= end_date:
        date_key = current_date.isoformat()

        # 지원 범위 밖 날짜는 예외를 발생시킴
        is_trading_day = is_krx_trading_day(current_date)

        if not is_trading_day:
            print(f"[휴장일 건너뛰기] {current_date}")
            current_date += timedelta(days=1)
            continue

        # 정상 완료된 날짜만 건너뛰기
        # 실패 기록이 남아 있다면 재수집 우선
        if (
            resume
            and date_key in completions
            and date_key not in failures
        ):
            results["skipped_completed"] += 1
            print(f"[수집 완료 건너뛰기] {current_date}")
            current_date += timedelta(days=1)
            continue

        print(f"[수집 시작] {current_date}")

        try:
            collection = collect_prices(
                trade_date=current_date,
                symbols=symbols,
            )

            status = collection["status"]
            saved = collection["saved_rows"]

            if status == "success":
                failures.pop(date_key, None)

                completions[date_key] = {
                    "status": "success",
                    "saved_rows": saved,
                }

                results["success_dates"] += 1
                results["total_rows"] += saved
                print(f"  저장 처리: {saved}건")

            elif status == "no_matching_symbols":
                failures.pop(date_key, None)

                completions[date_key] = {
                    "status": "no_matching_symbols",
                    "saved_rows": 0,
                }

                results["no_matching_dates"] += 1
                print(f"  대상 종목 없음: {current_date}")

            elif status == "empty_market":
                completions.pop(date_key, None)

                failures[date_key] = {
                    "error_type": "EmptyMarket",
                    "error": "KRX 전체 KOSPI 응답이 비어 있습니다.",
                }

                results["empty_dates"] += 1
                print(f"  전체 시장 데이터 없음 - 확인 필요: {current_date}")

            else:
                raise ValueError(f"알 수 없는 수집 상태: {status}")

        except Exception as exc:
            completions.pop(date_key, None)

            failures[date_key] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

            results["failed_dates"].append(date_key)
            print(f"  수집 실패: {exc}")

        # 날짜별로 완료/실패 기록 저장
        save_completions(scope, completions)
        save_failures(scope, failures)

        current_date += timedelta(days=1)

        if current_date <= end_date:
            time.sleep(request_interval)

    results["remaining_failures"] = len(failures)

    return results







def retry_failed_prices(
    scope: str = "test",
    request_interval: float = 0.5,
) -> dict:
    """실패 기록에 남아 있는 날짜만 다시 수집한다."""

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    failure_file(scope)

    if scope != "test":
        raise ValueError("현재는 테스트 4개 종목만 지원합니다.")

    # 실패 기록과 완료 기록을 모두 불러옴
    failures = load_failures(scope)
    completions = load_completions(scope)

    results = {
        "attempted_dates": 0,
        "success_dates": 0,
        "no_matching_dates": [],
        "empty_dates": [],
        "failed_dates": [],
        "skipped_holidays": 0,
        "total_rows": 0,
    }

    if not failures:
        print("재수집할 실패 날짜가 없습니다.")
        results["remaining_failures"] = 0
        return results

    dates = sorted(failures.keys())

    for index, date_key in enumerate(dates):
        trade_date = date.fromisoformat(date_key)

        # 거래소 캘린더 기준 휴장일이면 실패 기록 정리
        if not is_krx_trading_day(trade_date):
            failures.pop(date_key, None)
            completions.pop(date_key, None)

            results["skipped_holidays"] += 1

            save_completions(scope, completions)
            save_failures(scope, failures)

            print(f"[휴장일 기록 정리] {date_key}")
            continue

        print(f"[재수집 시작] {date_key}")
        results["attempted_dates"] += 1

        try:
            collection = collect_prices(
                trade_date=trade_date,
                symbols=TEST_SYMBOLS,
            )

            status = collection["status"]
            saved = collection["saved_rows"]

            if status == "success":
                failures.pop(date_key, None)

                completions[date_key] = {
                    "status": "success",
                    "saved_rows": saved,
                }

                results["success_dates"] += 1
                results["total_rows"] += saved

                print(f"  재수집 성공: {saved}건")

            elif status == "no_matching_symbols":
                failures.pop(date_key, None)

                completions[date_key] = {
                    "status": "no_matching_symbols",
                    "saved_rows": 0,
                }

                results["no_matching_dates"].append(date_key)
                print(f"  대상 종목 없음: {date_key}")

            elif status == "empty_market":
                completions.pop(date_key, None)

                failures[date_key] = {
                    "error_type": "EmptyMarket",
                    "error": "KRX 전체 KOSPI 응답이 비어 있습니다.",
                }

                results["empty_dates"].append(date_key)
                print(f"  전체 시장 데이터 없음 - 확인 필요: {date_key}")

            else:
                raise ValueError(f"알 수 없는 수집 상태: {status}")

        except Exception as exc:
            completions.pop(date_key, None)

            failures[date_key] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

            results["failed_dates"].append(date_key)
            print(f"  재수집 실패: {exc}")

        # 날짜별 완료 기록과 실패 기록을 함께 저장
        save_completions(scope, completions)
        save_failures(scope, failures)

        if index < len(dates) - 1:
            time.sleep(request_interval)

    results["remaining_failures"] = len(failures)

    return results




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





if __name__ == "__main__":
    result = backfill_prices(
        start_date=date(2020, 1, 1),
        end_date=date(2026, 10, 20),
        symbols=TEST_SYMBOLS,
        request_interval=0.5,
        scope="test",
        resume=True,
    )

    print("\n========== 전체 기간 수집 결과 ==========")
    print(f"수집 성공 날짜: {result['success_dates']}일")
    print(f"완료 기록으로 건너뛴 날짜: {result['skipped_completed']}일")
    print(f"전체 시장 데이터 없는 날짜: {result['empty_dates']}일")
    print(f"대상 종목 없는 날짜: {result['no_matching_dates']}일")
    print(f"저장 처리한 데이터: {result['total_rows']}건")
    print(f"실패한 날짜: {result['failed_dates']}")
    print(f"남아 있는 실패 기록: {result['remaining_failures']}건")




