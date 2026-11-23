from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from pipelines.market import friday
from pipelines.market.krx import KrxDailySnapshot
from pipelines.market.symbol_status import SymbolStatus
from scripts import collect_friday_market_data as friday_cli


TRADE_DATE = date(2026, 11, 20)
NOW = datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc)
ACTIVE = ("000001", "000002")
TERMINAL = "417310"
TARGETS = (*ACTIVE, TERMINAL)


def _capture(root):
    day = root / TRADE_DATE.isoformat()
    day.mkdir(parents=True)
    summary = {
        "trade_date": TRADE_DATE.isoformat(),
        "target_count": len(TARGETS),
        "target_symbols": list(TARGETS),
        "captured_symbols": list(TARGETS),
        "skipped_symbols": [],
        "failed_symbols": [],
        "errors": {},
    }
    (day / "capture_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    for symbol in TARGETS:
        payload = {
            "schema_version": 1,
            "source": "KIS",
            "endpoint": "/uapi/domestic-stock/v1/quotations/inquire-price",
            "tr_id": "FHKST01010100",
            "symbol": symbol,
            "basis_trade_date": TRADE_DATE.isoformat(),
            "collected_at": "2026-11-20T11:00:00+00:00",
            "collected_at_kst": "2026-11-20T20:00:00+09:00",
            "raw_output": {
                "per": "10", "pbr": "2", "eps": "100", "bps": "500",
                "w52_hgpr": "150", "w52_hgpr_date": "20261001",
                "w52_lwpr": "70", "w52_lwpr_date": "20251103",
                "hts_avls": "1", "lstn_stcn": "1000",
                "stck_prpr": "100", "acml_vol": "10",
            },
        }
        (day / f"{symbol}.json").write_text(json.dumps(payload), encoding="utf-8")


def _krx_row(symbol, *, zero=False):
    return {
        "MKT_NM": "KOSPI", "ISU_CD": symbol, "BAS_DD": "20261120",
        "TDD_OPNPRC": "0" if zero else "90",
        "TDD_HGPRC": "0" if zero else "110",
        "TDD_LWPRC": "0" if zero else "80",
        "TDD_CLSPRC": "100", "ACC_TRDVOL": "0" if zero else "10",
        "ACC_TRDVAL": "0" if zero else "1000", "MKTCAP": "100000",
        "LIST_SHRS": "1000",
    }


def _snapshot(rows):
    raw = json.dumps({"OutBlock_1": rows}, separators=(",", ":")).encode()
    return KrxDailySnapshot(
        endpoint="mock://krx", trade_date=TRADE_DATE, status_code=200,
        content_type="application/json", raw_content=raw, rows=rows,
    )


def _statuses():
    return {
        TERMINAL: SymbolStatus(
            symbol=TERMINAL, status="delisted", effective_date=TRADE_DATE,
            reason="official delisting", source="KRX",
        )
    }


class FakeKis:
    request_interval = 0.5

    def __init__(self, *, fail=(), no_row=(), adjusted_difference=False):
        self.fail = set(fail)
        self.no_row = set(no_row)
        self.adjusted_difference = adjusted_difference
        self.calls = []

    def daily_page(self, symbol, start, end, *, adjusted):
        self.calls.append((symbol, adjusted))
        if symbol in self.fail:
            raise RuntimeError("mock KIS failure")
        if symbol in self.no_row:
            return []
        zero = symbol == "000002"
        close = "50" if adjusted and self.adjusted_difference and symbol == "000001" else "100"
        return [{
            "stck_bsop_date": "20261120",
            "stck_oprc": close if zero or adjusted and close == "50" else "90",
            "stck_hgpr": close if zero or adjusted and close == "50" else "110",
            "stck_lwpr": close if zero or adjusted and close == "50" else "80",
            "stck_clpr": close,
            "acml_vol": "0" if zero else "10",
            "acml_tr_pbmn": "0" if zero else "1000",
        }]

    def request_metrics(self):
        return {"quotation": len(self.calls), "retries": 0, "rate_limit_errors": 0}


def _saturday(tmp_path, *, saver=None, rows=None):
    capture_root = tmp_path / "capture"
    state_root = tmp_path / "state"
    _capture(capture_root)
    saved = {}

    def default_saver(raw, fundamentals):
        saved["raw"] = raw
        saved["fundamentals"] = fundamentals
        return {"raw_inserted": len(raw), "fundamentals_inserted": len(fundamentals)}

    calls = []
    result = friday.run_saturday(
        TRADE_DATE,
        capture_root=capture_root,
        state_root=state_root,
        fetcher=lambda day: calls.append(day) or _snapshot(
            rows if rows is not None else [_krx_row("000001"), _krx_row("000002", zero=True)]
        ),
        saver=saver or default_saver,
        statuses=_statuses(),
        now=lambda: NOW,
    )
    return result, state_root, capture_root, saved, calls


def test_saturday_stores_only_verified_raw_and_separate_ratios(tmp_path):
    result, state_root, _capture_root, saved, calls = _saturday(tmp_path)

    assert result["status"] == friday.RAW_READY
    assert calls == [TRADE_DATE]
    assert result["validation"]["response_count"] == 2
    assert result["validation"]["unverified_no_krx"] == [TERMINAL]
    assert result["validation"]["zero_volume_symbols"] == ["000002"]
    assert all(row["source"] == "KRX_OPEN_API" for row in saved["raw"])
    assert all("adjustment_basis" not in row for row in saved["raw"])
    assert saved["raw"][1]["open"] == 0
    assert saved["fundamentals"][0]["per"] == Decimal("10")
    assert saved["fundamentals"][0]["analysis_per"] == Decimal("1.000000")
    assert saved["fundamentals"][0]["reference_price"] == Decimal("100")
    assert (state_root / TRADE_DATE.isoformat() / "krx_raw_response.json").is_file()
    assert friday.verify_manifest(
        state_root / TRADE_DATE.isoformat(),
        ("capture_evidence.json", "krx_raw_response.json", "krx_normalized.json"),
    )


def test_saturday_complete_rerun_makes_no_api_or_db_call(tmp_path):
    result, state_root, capture_root, _saved, _calls = _saturday(tmp_path)
    assert result["status"] == friday.RAW_READY
    second = friday.run_saturday(
        TRADE_DATE, capture_root=capture_root, state_root=state_root,
        fetcher=lambda _day: pytest.fail("API must not be called"),
        saver=lambda *_: pytest.fail("DB must not be written"), statuses=_statuses(),
    )
    assert second["status"] == friday.RAW_READY
    assert second["already_complete"] is True


def test_db_failure_reuses_preserved_krx_raw_on_recovery(tmp_path):
    attempts = []

    def failing_saver(*_args):
        raise ConnectionError("central DB down")

    first, state_root, capture_root, _saved, calls = _saturday(tmp_path, saver=failing_saver)
    assert first["status"] == friday.RETRY_REQUIRED
    assert len(calls) == 1

    second = friday.run_saturday(
        TRADE_DATE, capture_root=capture_root, state_root=state_root,
        fetcher=lambda _day: pytest.fail("preserved KRX raw must be reused"),
        saver=lambda raw, fund: attempts.append((raw, fund)) or {"raw_inserted": 2},
        statuses=_statuses(), now=lambda: NOW,
    )
    assert second["status"] == friday.RAW_READY
    assert second["request"]["http_requests"] == 0
    assert len(attempts) == 1


def test_krx_timeout_creates_retry_state_without_db_write(tmp_path):
    capture_root = tmp_path / "capture"
    state_root = tmp_path / "state"
    _capture(capture_root)
    saved = []
    result = friday.run_saturday(
        TRADE_DATE, capture_root=capture_root, state_root=state_root,
        fetcher=lambda _day: (_ for _ in ()).throw(TimeoutError("KRX timeout")),
        saver=lambda *_: saved.append(True), statuses=_statuses(), now=lambda: NOW,
    )
    assert result["status"] == friday.RETRY_REQUIRED
    assert result["error_type"] == "TimeoutError"
    assert saved == []
    assert not (state_root / TRADE_DATE.isoformat() / "krx_raw_response.json").exists()


def test_unapproved_missing_or_extra_krx_symbol_blocks(tmp_path):
    result, *_ = _saturday(tmp_path, rows=[_krx_row("000001")])
    assert result["status"] == friday.RETRY_REQUIRED
    assert "종목 집합 불일치" in result["error"]


def test_monday_verifies_raw_and_saves_only_kis_adjusted(tmp_path):
    saturday, state_root, _capture_root, _saved, _calls = _saturday(tmp_path)
    assert saturday["status"] == friday.RAW_READY
    client = FakeKis(adjusted_difference=True)
    adjusted = {}

    result = friday.run_monday(
        TRADE_DATE,
        client=client,
        state_root=state_root,
        db_state_loader=lambda day, symbols: {
            "raw_symbols": set(ACTIVE),
            "fundamental_symbols": set(ACTIVE),
            "adjusted_symbols": set(),
        },
        adjusted_saver=lambda row: adjusted.setdefault(row["symbol"], row) and "inserted",
        deadline=datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc),
        request_cap=204,
        now=lambda: NOW,
    )

    assert result["status"] == friday.ADJUSTED_FINALIZED
    assert result["completed_symbols"] == list(ACTIVE)
    assert result["unverified_no_krx"] == [TERMINAL]
    assert result["zero_volume_representation_symbols"] == ["000002"]
    assert result["raw_vs_adjusted_diff_symbols"] == ["000001"]
    assert all(row["source"] == "KIS" for row in adjusted.values())
    assert all(row["adjustment_basis"] == "KIS_FID_ORG_ADJ_PRC_0_V1" for row in adjusted.values())
    assert client.calls == [
        ("000001", False), ("000001", True),
        ("000002", False), ("000002", True),
    ]

    verifying = []
    second_client = FakeKis(fail=set(ACTIVE))
    second = friday.run_monday(
        TRADE_DATE, client=second_client, state_root=state_root,
        db_state_loader=lambda *_: {
            "raw_symbols": set(ACTIVE), "fundamental_symbols": set(ACTIVE),
            "adjusted_symbols": set(ACTIVE),
        },
        adjusted_saver=lambda row: verifying.append(row["symbol"]) or "existing",
        deadline=datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc), now=lambda: NOW,
    )
    assert second["already_complete"] is True
    assert second_client.calls == []
    assert verifying == list(ACTIVE)


def test_terminal_symbol_present_in_krx_is_never_saved(tmp_path):
    rows = [_krx_row("000001"), _krx_row("000002", zero=True), _krx_row(TERMINAL)]
    result, _state, _capture, saved, _calls = _saturday(tmp_path, rows=rows)
    assert result["status"] == friday.RAW_READY
    assert result["validation"]["terminal_symbols_present_in_response"] == [TERMINAL]
    assert {row["symbol"] for row in saved["raw"]} == set(ACTIVE)


def test_monday_kis_failure_is_retry_required_and_does_not_save_failed_symbol(tmp_path):
    _sat, state_root, *_ = _saturday(tmp_path)
    client = FakeKis(fail={"000002"})
    saved = []
    result = friday.run_monday(
        TRADE_DATE, client=client, state_root=state_root,
        db_state_loader=lambda *_: {
            "raw_symbols": set(ACTIVE), "fundamental_symbols": set(ACTIVE), "adjusted_symbols": set(),
        },
        adjusted_saver=lambda row: saved.append(row["symbol"]) or "inserted",
        deadline=datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc), now=lambda: NOW,
    )
    assert result["status"] == friday.RETRY_REQUIRED
    assert result["failed_symbols"] == ["000002"]
    assert saved == ["000001"]


def test_monday_no_row_is_not_success(tmp_path):
    _sat, state_root, *_ = _saturday(tmp_path)
    result = friday.run_monday(
        TRADE_DATE, client=FakeKis(no_row={"000002"}), state_root=state_root,
        db_state_loader=lambda *_: {
            "raw_symbols": set(ACTIVE), "fundamental_symbols": set(ACTIVE), "adjusted_symbols": set(),
        },
        adjusted_saver=lambda _row: "inserted",
        deadline=datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc), now=lambda: NOW,
    )
    assert result["status"] == friday.RETRY_REQUIRED
    assert result["failed_symbols"] == ["000002"]
    assert "각각 한 건" in result["errors"]["000002"]


def test_monday_blocks_before_api_on_sha_or_db_preflight_failure(tmp_path):
    _sat, state_root, *_ = _saturday(tmp_path)
    raw = state_root / TRADE_DATE.isoformat() / "krx_raw_response.json"
    raw.write_bytes(raw.read_bytes() + b"\n")
    client = FakeKis()
    result = friday.run_monday(
        TRADE_DATE, client=client, state_root=state_root,
        db_state_loader=lambda *_: pytest.fail("DB preflight must follow SHA validation"),
        adjusted_saver=lambda _row: pytest.fail("must not save"),
        deadline=datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc), now=lambda: NOW,
    )
    assert result["status"] == friday.RETRY_REQUIRED
    assert "SHA-256" in result["error"]
    assert client.calls == []


def test_automatic_dates_and_recovery_scope():
    saturday = datetime(2026, 11, 21, 8, 0, tzinfo=friday.SEOUL)
    monday = datetime(2026, 11, 23, 8, 0, tzinfo=friday.SEOUL)
    assert friday.automatic_trade_date(saturday, "saturday") == TRADE_DATE
    assert friday.automatic_trade_date(monday, "monday") == TRADE_DATE
    assert friday.monday_deadline(TRADE_DATE, monday, delayed_recovery=False).hour == 8
    with pytest.raises(friday.FridayInputError):
        friday.validate_recovery_trade_date(date(2026, 11, 19), monday)


def test_cli_db_lock_failure_is_retryable_before_provider_calls(monkeypatch, capsys):
    @contextmanager
    def broken_lock():
        raise ConnectionError("central DB unavailable")
        yield False

    monkeypatch.setattr(friday_cli, "_enabled", lambda: True)
    monkeypatch.setattr(friday_cli, "_trade_date", lambda *_: (TRADE_DATE, True))
    monkeypatch.setattr(friday_cli, "daily_refresh_lock", broken_lock)
    monkeypatch.setattr(
        friday_cli, "assert_friday_schema",
        lambda: pytest.fail("schema/API stage must not start"),
    )
    rc = friday_cli.main(["saturday-recovery", "--trade-date", "2026-11-20"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["status"] == friday.RETRY_REQUIRED
    assert payload["error_type"] == "ConnectionError"
