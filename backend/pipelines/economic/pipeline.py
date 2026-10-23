
import os
from decimal import Decimal

from sqlalchemy import create_engine, text


def save_economic_observations(rows: list[dict]) -> int:
    """경제지표 관측치를 PostgreSQL에 UPSERT한다."""

    if not rows:
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL이 설정되지 않았습니다.")

    required = {"indicator_code", "observation_date", "value"}

    for row in rows:
        if not required.issubset(row):
            raise ValueError(f"필수 데이터 누락: {row}")

        value = Decimal(str(row["value"]))
        if not value.is_finite():
            raise ValueError("유효하지 않은 경제지표 값")

    stmt = text("""
        INSERT INTO economic_observations (
            indicator_code,
            observation_date,
            value
        )
        VALUES (
            :indicator_code,
            :observation_date,
            :value
        )
        ON CONFLICT (indicator_code, observation_date)
        DO UPDATE SET
            value = EXCLUDED.value
    """)

    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.begin() as conn:
            conn.execute(stmt, rows)
    finally:
        engine.dispose()

    return len(rows)



import json
import time
from datetime import date, timedelta
from pathlib import Path

from .ecos import (
    fetch_ecos_series,
    normalize_ecos_rows,
    extract_policy_rate_events,
)


ECOS_STATE_DIR = Path("logs/economic")

ECOS_SERIES = {
    "USD_KRW": "731Y003/0000003",
    "KR_GOV_3Y": "817Y002/010200000",
    "KR_GOV_10Y": "817Y002/010210000",
    "KR_GOV_30Y": "817Y002/010230000",
    "KR_POLICY_RATE": "722Y001/0101000",
}


def load_ecos_state(state_type: str) -> dict:
    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    path = ECOS_STATE_DIR / f"ecos_{state_type}.json"

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    if not isinstance(state, dict):
        raise ValueError("ECOS 상태 파일 형식 오류")

    return state


def save_ecos_state(state_type: str, state: dict) -> None:
    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    path = ECOS_STATE_DIR / f"ecos_{state_type}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    temporary.replace(path)


def backfill_ecos(
    start_date: date,
    end_date: date,
    request_interval: float = 0.5,
    resume: bool = True,
) -> dict:
    """ECOS 경제지표 5개를 지정한 기간 단위로 수집한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    completed = load_ecos_state("completed")
    failed = load_ecos_state("failed")

    results = {
        "success": 0,
        "saved_rows": 0,
        "skipped_completed": 0,
        "failed": [],
    }

    for indicator_code, series_code in ECOS_SERIES.items():
        state_key = (
            f"{indicator_code}:"
            f"{start_date.isoformat()}:"
            f"{end_date.isoformat()}"
        )

        if (
            resume
            and state_key in completed
            and state_key not in failed
        ):
            results["skipped_completed"] += 1
            print(f"[ECOS 완료 건너뛰기] {state_key}")
            continue

        print(f"[ECOS 수집 시작] {state_key}")

        try:
            raw = fetch_ecos_series(
                series_code,
                start_date,
                end_date,
            )

            rows = normalize_ecos_rows(indicator_code, raw)

            if not rows:
                raise ValueError("ECOS 관측치가 없습니다.")

            if indicator_code == "KR_POLICY_RATE":
                # 시작일 직전 기준금리를 가져와
                # 기간 첫날을 잘못된 변경 이벤트로 기록하지 않는다.
                previous_date = start_date - timedelta(days=1)

                previous_raw = fetch_ecos_series(
                    series_code,
                    previous_date,
                    previous_date,
                )
                previous_rows = normalize_ecos_rows(
                    indicator_code,
                    previous_raw,
                )

                if len(previous_rows) != 1:
                    raise ValueError(
                        "기준금리 직전 관측값 조회 실패"
                    )

                previous_value = previous_rows[0]["value"]

                rows = extract_policy_rate_events(
                    rows,
                    previous_value=previous_value,
                )

                # 전체 초기 적재 시작일의 직전 상태를
                # 실제 관측일(2019-12-31)에 보존한다.
                if start_date == date(2020, 1, 1):
                    rows = previous_rows + rows

            saved = save_economic_observations(rows)

            completed[state_key] = {
                "status": "success",
                "saved_rows": saved,
            }
            failed.pop(state_key, None)

            results["success"] += 1
            results["saved_rows"] += saved

            print(f"  저장 완료: {saved}건")

        except Exception as exc:
            completed.pop(state_key, None)

            failed[state_key] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

            results["failed"].append(state_key)
            print(f"  수집 실패: {exc}")

        finally:
            save_ecos_state("completed", completed)
            save_ecos_state("failed", failed)

            if request_interval > 0:
                time.sleep(request_interval)

    results["remaining_failures"] = len(failed)
    return results




from .fred import fetch_fred_series, normalize_fred_rows


FRED_STATE_DIR = Path("logs/economic")

FRED_SERIES = {
    "US_TREASURY_2Y": "DGS2",
    "US_TREASURY_10Y": "DGS10",
    "US_TREASURY_30Y": "DGS30",
    "WTI_SPOT": "DCOILWTICO",
}


def load_fred_state(state_type: str) -> dict:
    """FRED 수집 완료·실패 상태를 읽는다."""

    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    path = FRED_STATE_DIR / f"fred_{state_type}.json"

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    if not isinstance(state, dict):
        raise ValueError("FRED 상태 파일 형식 오류")

    return state


def save_fred_state(state_type: str, state: dict) -> None:
    """FRED 수집 상태를 JSON으로 저장한다."""

    if state_type not in {"completed", "failed"}:
        raise ValueError(f"잘못된 상태 유형: {state_type}")

    path = FRED_STATE_DIR / f"fred_{state_type}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    temporary.replace(path)


def backfill_fred(
    start_date: date,
    end_date: date,
    request_interval: float = 0.5,
    resume: bool = True,
) -> dict:
    """FRED 경제지표 4개를 기간별로 수집한다."""

    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")

    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    completed = load_fred_state("completed")
    failed = load_fred_state("failed")

    results = {
        "success": 0,
        "saved_rows": 0,
        "skipped_completed": 0,
        "failed": [],
    }

    for indicator_code, series_id in FRED_SERIES.items():
        state_key = (
            f"{indicator_code}:"
            f"{start_date.isoformat()}:"
            f"{end_date.isoformat()}"
        )

        if (
            resume
            and state_key in completed
            and state_key not in failed
        ):
            results["skipped_completed"] += 1
            print(f"[FRED 완료 건너뛰기] {state_key}")
            continue

        print(f"[FRED 수집 시작] {state_key}")

        try:
            raw = fetch_fred_series(
                series_id,
                start_date,
                end_date,
            )

            rows = normalize_fred_rows(
                indicator_code,
                raw,
            )

            if not rows:
                raise ValueError("FRED 유효 관측치가 없습니다.")

            saved = save_economic_observations(rows)

            if saved != len(rows):
                raise ValueError(
                    f"FRED 저장 건수 불일치: {indicator_code}"
                )

            completed[state_key] = {
                "status": "success",
                "saved_rows": saved,
            }
            failed.pop(state_key, None)

            results["success"] += 1
            results["saved_rows"] += saved

            print(f"  저장 완료: {saved}건")

        except Exception as exc:
            completed.pop(state_key, None)

            failed[state_key] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

            results["failed"].append(state_key)
            print(f"  수집 실패: {exc}")

        finally:
            save_fred_state("completed", completed)
            save_fred_state("failed", failed)

            if request_interval > 0:
                time.sleep(request_interval)

    results["remaining_failures"] = len(failed)
    return results
