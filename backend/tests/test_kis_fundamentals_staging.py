from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json

import pytest

from pipelines.market import kis_fundamentals as staged
from pipelines.market.symbol_status import (
    SymbolStatus,
    load_symbol_statuses,
    select_operational_symbols,
)


TRADE_DATE = date(2026, 11, 3)
COLLECTED_AT = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)


def current_output(**overrides):
    result = {
        "per": "10",
        "pbr": "1",
        "eps": "100",
        "bps": "1000",
        "w52_hgpr": "120",
        "w52_hgpr_date": "20261001",
        "w52_lwpr": "80",
        "w52_lwpr_date": "20251101",
        "hts_avls": "1",
        "lstn_stcn": "1000",
        "stck_prpr": "100",
        "acml_vol": "1000",
    }
    result.update(overrides)
    return result


def snapshot(symbol="005930", **overrides):
    return {
        "schema_version": 1,
        "source": "KIS",
        "endpoint": "/uapi/domestic-stock/v1/quotations/inquire-price",
        "tr_id": "FHKST01010100",
        "symbol": symbol,
        "basis_trade_date": TRADE_DATE.isoformat(),
        "collected_at": COLLECTED_AT.isoformat(),
        "collected_at_kst": "2026-11-03T18:30:00+09:00",
        "raw_output": current_output(**overrides),
    }


def final_daily(symbol="005930", *, close="100", volume=1000):
    return {
        "symbol": symbol,
        "trade_date": TRADE_DATE,
        "close": Decimal(close),
        "volume": volume,
    }


def daily_api_row(close="100", volume="1000"):
    return {
        "stck_bsop_date": "20261103",
        "stck_oprc": "95",
        "stck_hgpr": "105",
        "stck_lwpr": "90",
        "stck_clpr": close,
        "acml_vol": volume,
        "acml_tr_pbmn": "100000",
    }


def krx_api_row(close="100", volume="1000"):
    return {
        "ISU_CD": "005930",
        "BAS_DD": "20261103",
        "TDD_OPNPRC": "95",
        "TDD_HGPRC": "105",
        "TDD_LWPRC": "90",
        "TDD_CLSPRC": close,
        "ACC_TRDVOL": volume,
    }


def normalized_daily(
    symbol="002410", *, open_="100", high="100", low="100",
    close="100", volume=0, trade_date=TRADE_DATE,
):
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": Decimal(open_),
        "high": Decimal(high),
        "low": Decimal(low),
        "close": Decimal(close),
        "volume": volume,
    }


def zero_volume_krx(symbol="002410", *, close="100", **overrides):
    row = {
        "ISU_CD": symbol,
        "BAS_DD": TRADE_DATE.strftime("%Y%m%d"),
        "TDD_OPNPRC": "0",
        "TDD_HGPRC": "0",
        "TDD_LWPRC": "0",
        "TDD_CLSPRC": close,
        "ACC_TRDVOL": "0",
    }
    row.update(overrides)
    return row


def test_zero_volume_ohl_representation_difference_is_strictly_allowed():
    raw = normalized_daily()
    adjusted = normalized_daily()
    assert staged.verify_raw_daily_against_krx(
        raw, zero_volume_krx(), adjusted_daily=adjusted
    ) == staged.ZERO_VOLUME_OHL_DIFFERENCE


def test_same_proven_zero_volume_pattern_is_allowed_for_other_symbols():
    raw = normalized_daily(symbol="005930")
    adjusted = normalized_daily(symbol="005930")
    assert staged.verify_raw_daily_against_krx(
        raw,
        zero_volume_krx(symbol="005930"),
        adjusted_daily=adjusted,
    ) == staged.ZERO_VOLUME_OHL_DIFFERENCE


@pytest.mark.parametrize(
    "raw,adjusted,krx",
    [
        (normalized_daily(volume=1), normalized_daily(), zero_volume_krx()),
        (normalized_daily(close="101", open_="101", high="101", low="101"), normalized_daily(), zero_volume_krx()),
        (normalized_daily(), normalized_daily(volume=1), zero_volume_krx()),
        (normalized_daily(), normalized_daily(open_="99"), zero_volume_krx()),
        (normalized_daily(), normalized_daily(), zero_volume_krx(TDD_OPNPRC="1")),
        (normalized_daily(symbol="000001"), normalized_daily(symbol="000001"), zero_volume_krx()),
        (normalized_daily(trade_date=date(2026, 11, 2)), normalized_daily(trade_date=date(2026, 11, 2)), zero_volume_krx()),
    ],
)
def test_zero_volume_exception_rejects_any_failed_condition(raw, adjusted, krx):
    with pytest.raises(staged.FundamentalsSnapshotError):
        staged.verify_raw_daily_against_krx(
            raw, krx, adjusted_daily=adjusted
        )


def test_regular_trading_strict_mismatch_stays_blocked():
    raw = normalized_daily(open_="95", high="105", low="90", volume=1000)
    adjusted = dict(raw)
    with pytest.raises(staged.FundamentalsSnapshotError):
        staged.verify_raw_daily_against_krx(
            raw,
            krx_api_row(close="101", volume="1000"),
            adjusted_daily=adjusted,
        )


class ZeroVolumeDailyClient:
    def __init__(self, close="100"):
        self.close = close

    def daily_page(self, symbol, start_date, end_date, *, adjusted):
        return [{
            "stck_bsop_date": TRADE_DATE.strftime("%Y%m%d"),
            "stck_oprc": self.close,
            "stck_hgpr": self.close,
            "stck_lwpr": self.close,
            "stck_clpr": self.close,
            "acml_vol": "0",
            "acml_tr_pbmn": "0",
        }]


def test_finalize_records_zero_volume_representation_reason(tmp_path):
    staged.capture_snapshots(
        ("002410",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    result = staged.finalize_snapshots(
        ("002410",),
        TRADE_DATE,
        client=ZeroVolumeDailyClient(),
        root=tmp_path,
        krx_rows={"002410": zero_volume_krx()},
    )
    assert result["ready_symbols"] == ["002410"]
    assert result["failed_symbols"] == []
    assert result["krx_comparison"]["002410"] == {
        "status": "matched",
        "reason": staged.ZERO_VOLUME_OHL_DIFFERENCE,
    }
    assert staged.ZERO_VOLUME_OHL_DIFFERENCE in result["warnings"]["002410"]


def test_price_and_volume_mismatch_preserve_eps_bps():
    row, warnings = staged.normalize_staged_fundamentals(
        snapshot(stck_prpr="101", acml_vol="999"),
        final_daily(),
    )

    assert row["eps"] == Decimal("100")
    assert row["bps"] == Decimal("1000")
    assert row["reference_price"] == Decimal("101")
    assert row["final_close"] == Decimal("100")
    assert "stck_prpr:final_close_mismatch" in warnings
    assert "acml_vol:final_volume_mismatch" in warnings


def test_negative_provider_ratios_are_null_without_losing_other_fields():
    row, warnings = staged.normalize_staged_fundamentals(
        snapshot(per="-3.5", pbr="-0.2", eps="-50", bps="-100"),
        final_daily(),
    )

    assert row["per"] is None
    assert row["pbr"] is None
    assert row["eps"] == Decimal("-50")
    assert row["bps"] == Decimal("-100")
    assert "per:negative_nullified" in warnings
    assert "pbr:negative_nullified" in warnings
    assert staged.analysis_ratios(row) == {
        "analysis_per": None,
        "analysis_pbr": None,
    }


@pytest.mark.parametrize(
    "eps,bps,expected_eps,expected_bps",
    [
        ("0", "0", Decimal("0"), Decimal("0")),
        ("-1", "-2", Decimal("-1"), Decimal("-2")),
        ("", "", None, None),
    ],
)
def test_eps_bps_zero_negative_and_null_are_preserved(
    eps, bps, expected_eps, expected_bps
):
    row, _warnings = staged.normalize_staged_fundamentals(
        snapshot(eps=eps, bps=bps),
        final_daily(),
    )

    assert row["eps"] == expected_eps
    assert row["bps"] == expected_bps
    assert staged.analysis_ratios(row) == {
        "analysis_per": None,
        "analysis_pbr": None,
    }


def test_invalid_w52_pair_does_not_discard_other_fields():
    row, warnings = staged.normalize_staged_fundamentals(
        snapshot(w52_hgpr="bad", w52_hgpr_date="20261001"),
        final_daily(),
    )

    assert row["w52_high"] is None
    assert row["w52_high_date"] is None
    assert row["w52_low"] == Decimal("80")
    assert row["eps"] == Decimal("100")
    assert any("w52_hgpr" in warning for warning in warnings)


class CaptureClient:
    def __init__(self):
        self.calls = []

    def current_price(self, symbol):
        self.calls.append(symbol)
        return current_output()


def test_capture_is_atomic_and_duplicate_run_skips_api(tmp_path):
    client = CaptureClient()
    first = staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=client,
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    second = staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=client,
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )

    assert first["captured_symbols"] == ["005930"]
    assert second["skipped_symbols"] == ["005930"]
    assert client.calls == ["005930"]
    saved = staged.load_snapshot(tmp_path, TRADE_DATE, "005930")
    assert saved["collected_at"] == COLLECTED_AT
    assert saved["raw_output"]["eps"] == "100"


class DailyClient:
    def __init__(self):
        self.calls = []

    def daily_page(self, symbol, start_date, end_date, *, adjusted):
        self.calls.append((symbol, start_date, end_date, adjusted))
        return [daily_api_row()]


def test_finalize_combines_staged_response_and_is_idempotent(tmp_path):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    prices = {}
    fundamentals = {}

    def save_prices(raw_rows, adjusted_rows):
        for kind, rows in (("raw", raw_rows), ("adjusted", adjusted_rows)):
            for row in rows:
                prices[(kind, row["symbol"], row["trade_date"])] = row
        return len(raw_rows) + len(adjusted_rows)

    def save_fundamentals(rows):
        for row in rows:
            fundamentals[(row["symbol"], row["basis_trade_date"])] = row
        return len(rows)

    first_client = DailyClient()
    result = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=first_client,
        root=tmp_path,
        price_saver=save_prices,
        fundamentals_saver=save_fundamentals,
    )
    assert result["failed_symbols"] == []
    assert result["saved_symbols"] == ["005930"]
    assert staged.is_finalized(tmp_path, TRADE_DATE, "005930") is True

    second_client = DailyClient()
    second = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=second_client,
        root=tmp_path,
        price_saver=save_prices,
        fundamentals_saver=save_fundamentals,
    )
    assert second["failed_symbols"] == []
    assert second["saved_symbols"] == []
    assert second["skipped_symbols"] == ["005930"]
    assert second_client.calls == []

    assert len(prices) == 2
    assert len(fundamentals) == 1
    row = fundamentals[("005930", TRADE_DATE)]
    assert row["collected_at"] == COLLECTED_AT
    assert row["final_close"] == Decimal("100")
    assert result["analysis_ratios"]["005930"] == {
        "analysis_per": Decimal("1"),
        "analysis_pbr": Decimal("0.1"),
    }


def test_automatic_dates_and_inactive_universe_filter():
    sunday = datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc)
    monday = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)

    assert staged.automatic_capture_date(sunday) is None
    assert staged.automatic_finalize_date(monday) == date(2026, 11, 6)
    statuses = {
        "002785": SymbolStatus(
            "002785", "converted", date(2026, 11, 10), "converted", "official"
        ),
        "002787": SymbolStatus(
            "002787", "converted", date(2026, 11, 10), "converted", "official"
        ),
        "004415": SymbolStatus(
            "004415", "delisted", None, "delisted", "official"
        ),
    }
    assert staged.operational_symbols(
        ("002780", "002785", "002787", "004415", "005930"),
        trade_date=date(2026, 11, 10),
        statuses=statuses,
    ) == (("002780", "005930"), ("002785", "002787", "004415"))
    assert staged.operational_symbols(
        ("002780", "002785", "002787"),
        trade_date=date(2026, 11, 9),
        statuses=statuses,
    ) == (("002780", "002785", "002787"), ())


def test_operational_selection_retains_temporary_absence_and_adds_new_listing():
    statuses = {}
    selection = select_operational_symbols(
        ("005930", "000080", "0126Z0"),
        TRADE_DATE,
        observed_krx_symbols=("005930", "0126Z0"),
        statuses=statuses,
    )

    assert selection["symbols"] == ("000080", "005930", "0126Z0")
    assert selection["temporarily_absent_symbols"] == ("000080",)
    assert selection["pending_master_sync_symbols"] == ()

    pending_sync = select_operational_symbols(
        ("005930",),
        TRADE_DATE,
        observed_krx_symbols=("005930", "0126Z0"),
        statuses=statuses,
    )
    assert pending_sync["symbols"] == ("005930",)
    assert pending_sync["pending_master_sync_symbols"] == ("0126Z0",)


def test_reviewed_status_registry_activates_conversion_on_effective_date():
    statuses = load_symbol_statuses()

    assert statuses["002785"].is_terminal_on(date(2026, 11, 9)) is False
    assert statuses["002785"].is_terminal_on(date(2026, 11, 10)) is True
    assert statuses["002787"].is_terminal_on(date(2026, 11, 10)) is True
    assert statuses["004415"].is_terminal_on(date(2020, 1, 1)) is True
    assert statuses["011155"].is_terminal_on(date(2020, 1, 1)) is True
    assert statuses["417310"].is_terminal_on(date(2026, 11, 19)) is False
    assert statuses["417310"].is_terminal_on(date(2026, 11, 20)) is True


def test_terminal_inactive_marker_stops_retry_without_api_or_db_changes(tmp_path):
    staged.capture_snapshots(
        ("002785", "005930"),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    status = SymbolStatus(
        "002785", "converted", TRADE_DATE, "converted", "official"
    )

    assert staged.mark_terminal_inactive(tmp_path, TRADE_DATE, "002785", status)
    assert staged.is_finalized(tmp_path, TRADE_DATE, "002785")
    assert staged.symbols_needing_finalization(
        tmp_path, TRADE_DATE, ("002785", "005930")
    ) == ("005930",)
    marker = json.loads(
        staged.finalization_path(tmp_path, TRADE_DATE, "002785").read_text()
    )
    assert marker["status"] == "terminal_inactive"
    assert marker["raw_rows"] == marker["adjusted_rows"] == 0
    assert staged.snapshot_path(tmp_path, TRADE_DATE, "002785").exists()


def test_pending_dates_keep_failed_session_for_later_recovery(tmp_path):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )

    assert staged.pending_snapshot_dates(
        tmp_path,
        TRADE_DATE,
        recovery_days=10,
    ) == (TRADE_DATE,)
    assert staged.symbols_needing_finalization(
        tmp_path,
        TRADE_DATE,
        ("005930",),
    ) == ("005930",)

    assert staged.capture_target_symbols(tmp_path, TRADE_DATE) == ("005930",)

    mismatch = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
        krx_rows={"005930": krx_api_row(close="101")},
        price_saver=lambda *_args: 2,
        fundamentals_saver=lambda _rows: 1,
    )
    assert mismatch["failed_symbols"] == ["005930"]
    assert staged.is_finalized(tmp_path, TRADE_DATE, "005930") is False


def test_missing_or_corrupt_snapshot_fails_before_daily_api(tmp_path):
    client = DailyClient()
    missing = staged.finalize_snapshots(
        ("005930",), TRADE_DATE, client=client, root=tmp_path
    )
    assert missing["failed_symbols"] == ["005930"]
    assert client.calls == []

    path = staged.snapshot_path(tmp_path, TRADE_DATE, "005930")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    corrupt = staged.finalize_snapshots(
        ("005930",), TRADE_DATE, client=client, root=tmp_path
    )
    assert corrupt["failed_symbols"] == ["005930"]
    assert client.calls == []


def test_dry_run_never_calls_database_savers(tmp_path):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    result = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
    )

    assert result["dry_run"] is True
    assert result["ready_symbols"] == ["005930"]
    assert result["saved_symbols"] == []


def test_optional_krx_verification_accepts_match_and_blocks_mismatch(tmp_path):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    matched = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
        krx_rows={"005930": krx_api_row()},
    )
    mismatched = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
        krx_rows={"005930": krx_api_row(close="101")},
    )

    assert matched["ready_symbols"] == ["005930"]
    assert mismatched["failed_symbols"] == ["005930"]
    assert "KRX 공식" in mismatched["errors"]["005930"]["error"]


@pytest.mark.parametrize(
    "krx_rows,expected_status",
    [
        ({"005930": krx_api_row(close="101")}, "mismatched"),
        ({}, "missing"),
    ],
)
def test_krx_warning_only_does_not_block_apply(
    tmp_path, krx_rows, expected_status
):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )
    saved = {"prices": 0, "fundamentals": 0}

    result = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
        krx_rows=krx_rows,
        krx_strict=False,
        price_saver=lambda raw, adjusted: saved.update(
            prices=len(raw) + len(adjusted)
        ) or saved["prices"],
        fundamentals_saver=lambda rows: saved.update(
            fundamentals=len(rows)
        ) or saved["fundamentals"],
    )

    assert result["failed_symbols"] == []
    assert result["saved_symbols"] == ["005930"]
    assert result["krx_comparison"]["005930"]["status"] == expected_status
    assert any(
        warning.startswith(f"krx:{expected_status}:")
        for warning in result["warnings"]["005930"]
    )
    assert saved == {"prices": 2, "fundamentals": 1}
    assert result["records"]["005930"]["fundamentals"] == {
        "eps": Decimal("100"),
        "bps": Decimal("1000"),
        "per": Decimal("10"),
        "pbr": Decimal("1"),
        "reference_price": Decimal("100"),
        "final_close": Decimal("100"),
        "collected_at": COLLECTED_AT,
    }
    assert result["records"]["005930"]["analysis_per"] == Decimal("1")
    assert result["records"]["005930"]["analysis_pbr"] == Decimal("0.1")


def test_krx_lookup_failure_warning_only_does_not_block_apply(tmp_path):
    staged.capture_snapshots(
        ("005930",),
        TRADE_DATE,
        client=CaptureClient(),
        root=tmp_path,
        now=lambda: COLLECTED_AT,
    )

    result = staged.finalize_snapshots(
        ("005930",),
        TRADE_DATE,
        client=DailyClient(),
        root=tmp_path,
        krx_rows={},
        krx_strict=False,
        krx_lookup_error="TimeoutError: unavailable",
        price_saver=lambda raw, adjusted: len(raw) + len(adjusted),
        fundamentals_saver=lambda rows: len(rows),
    )

    assert result["failed_symbols"] == []
    assert result["saved_symbols"] == ["005930"]
    assert result["krx_comparison"]["005930"] == {
        "status": "unavailable",
        "error": "TimeoutError: unavailable",
    }
