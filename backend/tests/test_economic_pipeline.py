from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pipelines.economic import pipeline


def observation(code: str, day: date, value: str) -> dict:
    return {
        "indicator_code": code,
        "observation_date": day,
        "value": Decimal(value),
    }


def test_indicator_definitions_match_active_ecos_and_fred_series():
    for code, series_code in pipeline.ECOS_SERIES.items():
        definition = pipeline.ECONOMIC_INDICATORS[code]
        assert definition["source"] == "ECOS"
        assert definition["series_code"] == series_code
    for code, series_code in pipeline.FRED_SERIES.items():
        definition = pipeline.ECONOMIC_INDICATORS[code]
        assert definition["source"] == "FRED"
        assert definition["series_code"] == series_code


def test_observation_save_registers_masters_in_same_transaction(monkeypatch):
    calls = []

    class Result:
        rowcount = 0

    class Connection:
        def execute(self, statement, params):
            calls.append((str(statement), params))
            return Result()

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def begin(self):
            return Begin()

        def dispose(self):
            pass

    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/test")
    monkeypatch.setattr(pipeline, "create_engine", lambda *_args, **_kwargs: Engine())
    rows = [
        observation("USD_KRW", date(2026, 10, 29), "1430.5"),
        observation("US_TREASURY_10Y", date(2026, 10, 29), "4.1"),
    ]

    assert pipeline.save_economic_observations(rows) == 2
    assert len(calls) == 2
    master_sql, master_params = calls[0]
    observation_sql, observation_params = calls[1]
    assert "INSERT INTO economic_indicators" in master_sql
    assert "ON CONFLICT (code) DO NOTHING" in master_sql
    assert "DO UPDATE" not in master_sql
    assert {row["code"] for row in master_params} == {
        "USD_KRW",
        "US_TREASURY_10Y",
    }
    assert "INSERT INTO economic_observations" in observation_sql
    assert observation_params == rows


def test_unknown_indicator_is_rejected_before_observation_insert(monkeypatch):
    calls = []

    class Connection:
        def execute(self, statement, params):
            calls.append(str(statement))

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def begin(self):
            return Begin()

        def dispose(self):
            pass

    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/test")
    monkeypatch.setattr(pipeline, "create_engine", lambda *_args, **_kwargs: Engine())

    with pytest.raises(ValueError, match="정의되지 않은 경제지표"):
        pipeline.save_economic_observations([
            observation("UNKNOWN", date(2026, 10, 29), "1")
        ])
    assert calls == []


def test_policy_rate_uses_preperiod_value_but_does_not_save_it(monkeypatch):
    start = date(2020, 1, 1)
    end = date(2020, 12, 31)
    saved = []
    monkeypatch.setattr(
        pipeline,
        "ECOS_SERIES",
        {"KR_POLICY_RATE": "722Y001/0101000"},
    )
    monkeypatch.setattr(pipeline, "load_ecos_state", lambda _kind: {})
    monkeypatch.setattr(pipeline, "save_ecos_state", lambda *_args: None)

    def fetch(_series, requested_start, requested_end):
        return "previous" if requested_end < start else "range"

    def normalize(_code, raw):
        if raw == "previous":
            return [observation("KR_POLICY_RATE", date(2019, 12, 31), "1.25")]
        return [
            observation("KR_POLICY_RATE", date(2019, 12, 31), "1.25"),
            observation("KR_POLICY_RATE", date(2020, 1, 1), "1.25"),
            observation("KR_POLICY_RATE", date(2020, 3, 17), "0.75"),
            observation("KR_POLICY_RATE", date(2021, 1, 1), "0.50"),
        ]

    monkeypatch.setattr(pipeline, "fetch_ecos_series", fetch)
    monkeypatch.setattr(pipeline, "normalize_ecos_rows", normalize)
    monkeypatch.setattr(
        pipeline,
        "save_economic_observations",
        lambda rows: saved.extend(rows) or len(rows),
    )

    result = pipeline.backfill_ecos(start, end, request_interval=0, resume=False)

    assert result["failed"] == []
    assert [row["observation_date"] for row in saved] == [date(2020, 3, 17)]


def test_fred_drops_rows_outside_requested_period(monkeypatch):
    start = date(2020, 1, 1)
    end = date(2020, 1, 2)
    saved = []
    monkeypatch.setattr(pipeline, "FRED_SERIES", {"WTI_SPOT": "DCOILWTICO"})
    monkeypatch.setattr(pipeline, "load_fred_state", lambda _kind: {})
    monkeypatch.setattr(pipeline, "save_fred_state", lambda *_args: None)
    monkeypatch.setattr(pipeline, "fetch_fred_series", lambda *_args: ["raw"])
    monkeypatch.setattr(
        pipeline,
        "normalize_fred_rows",
        lambda *_args: [
            observation("WTI_SPOT", date(2019, 12, 31), "61"),
            observation("WTI_SPOT", date(2020, 1, 2), "62"),
            observation("WTI_SPOT", date(2020, 1, 3), "63"),
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "save_economic_observations",
        lambda rows: saved.extend(rows) or len(rows),
    )

    result = pipeline.backfill_fred(start, end, request_interval=0, resume=False)

    assert result["failed"] == []
    assert [row["observation_date"] for row in saved] == [date(2020, 1, 2)]
