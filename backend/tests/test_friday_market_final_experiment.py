import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from scripts import friday_market_final_experiment as exp


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _sat_fixture(root: Path, missing: set[str] | None = None):
    missing = {"417310"} if missing is None else missing
    targets = [f"{n:06d}" for n in range(1, 936)] + ["417310"]
    present = [symbol for symbol in targets if symbol not in missing]
    rows = [{
        "symbol": symbol, "market": "KOSPI", "bas_dd": "20261120",
        "open": "100", "high": "100", "low": "100", "close": "100",
        "volume": "1", "trade_value": "100", "market_cap": "1000",
        "listed_shares": "10", "zero_volume": False,
    } for symbol in present]
    raw = {"OutBlock_1": [{"ISU_CD": symbol, "BAS_DD": "20261120"} for symbol in present]}
    _write_json(root / "krx_raw_response_attempt1.json", raw)
    raw_digest = hashlib.sha256((root / "krx_raw_response_attempt1.json").read_bytes()).hexdigest()
    _write_json(root / "capture_targets.json", {
        "capture_summary_sha256": "a" * 64, "target_symbols": targets,
    })
    _write_json(root / "krx_normalized.json", {"rows": rows})
    _write_json(root / "krx_completeness.json", {
        "response_rows": len(present), "targets_present": len(present), "target_count": 936,
        "bas_dd_values": ["20261120"], "all_rows_bas_dd_ok": True,
        "duplicate_symbols": [], "extra_kospi_symbols": [], "parse_error_symbols": [],
        "missing_targets": sorted(missing),
    })
    _write_json(root / "fundamentals_dry_run.json", {"counts": {}})
    _write_json(root / "saturday_summary.json", {
        "trade_date": "2026-11-20",
        "krx_request": {"params": {"basDd": "20261120"}, "http_requests": 1, "attempts": [{
            "status": 200, "saved_as": "krx_raw_response_attempt1.json", "sha256": raw_digest,
        }]},
    })
    required = ["capture_targets.json", "saturday_summary.json", "krx_raw_response_attempt1.json",
                "krx_normalized.json", "krx_completeness.json", "fundamentals_dry_run.json"]
    (root / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n" for name in required
    ), encoding="utf-8")
    return {"target_symbols": targets, "capture_summary_sha256": "a" * 64}, rows


def _kis_result(symbol: str, status: str = "ok") -> dict:
    if status != "ok":
        obs = {"status": status}
    else:
        value = "0" if symbol == "417310" else "100"
        obs = {"status": "ok", "raw": {"stck_bsop_date": "20261120"},
               "open": value, "high": value, "low": value, "close": value,
               "volume": "0" if symbol == "417310" else "1", "trade_value": value}
    return {"raw": dict(obs), "adjusted": dict(obs), "output1_reference": None, "retries": 0}


def test_monday_input_allows_only_417310_missing(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    result = exp.validate_monday_inputs(tmp_path, info, date(2026, 11, 20))
    assert result["capture_targets"] == 936
    assert result["kis_query_targets"] == 936
    assert result["krx_comparison_targets"] == 935
    assert result["unverified_no_krx"] == ["417310"]


@pytest.mark.parametrize("missing", [{"000001"}, {"417310", "000001"}])
def test_monday_input_blocks_other_or_additional_missing(tmp_path, missing):
    info, _ = _sat_fixture(tmp_path, missing)
    with pytest.raises(exp.MondayInputError):
        exp.validate_monday_inputs(tmp_path, info, date(2026, 11, 20))


def test_monday_input_blocks_sha256_mismatch(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    with (tmp_path / "krx_raw_response_attempt1.json").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(exp.MondayInputError, match="SHA-256"):
        exp.validate_monday_inputs(tmp_path, info, date(2026, 11, 20))


def test_unverified_zero_price_is_not_compared_and_935_continue(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    results = {symbol: _kis_result(symbol) for symbol in info["target_symbols"]}
    compared = exp.compare_all(tmp_path, results, info["target_symbols"], date(2026, 11, 20))
    assert compared["summary"]["krx_comparison_targets"] == 935
    assert compared["summary"]["ohlcv_exact_all"] == "935/935"
    assert compared["summary"]["unverified_no_krx"] == ["417310"]
    assert compared["per_symbol"]["417310"]["category"] == "unverified_no_krx"
    assert "fields" not in compared["per_symbol"]["417310"]
    assert "ohlcv_match" not in compared["per_symbol"]["417310"]


def test_kis_failure_prevents_unverified_success(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    results = {symbol: _kis_result(symbol) for symbol in info["target_symbols"]}
    results["000001"] = _kis_result("000001", "error")
    summary = exp.compare_all(tmp_path, results, info["target_symbols"], date(2026, 11, 20))["summary"]
    assert exp.monday_result_status([], None, summary) == "complete_with_symbol_failures"


def test_only_official_krx_absence_is_unverified_success(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    results = {symbol: _kis_result(symbol) for symbol in info["target_symbols"]}
    results["417310"] = _kis_result("417310", "no_row")
    summary = exp.compare_all(tmp_path, results, info["target_symbols"], date(2026, 11, 20))["summary"]
    assert exp.monday_result_status([], None, summary) == "complete_with_unverified_symbols"


def test_kis_error_on_unverified_symbol_still_prevents_success(tmp_path):
    info, _ = _sat_fixture(tmp_path)
    results = {symbol: _kis_result(symbol) for symbol in info["target_symbols"]}
    results["417310"] = _kis_result("417310", "error")
    summary = exp.compare_all(tmp_path, results, info["target_symbols"], date(2026, 11, 20))["summary"]
    assert exp.monday_result_status([], None, summary) == "complete_with_symbol_failures"


def test_invalid_input_blocks_before_client_creation(tmp_path, monkeypatch):
    info = {"target_symbols": [f"{n:06d}" for n in range(936)], "capture_summary_sha256": "a" * 64}
    monkeypatch.setattr(exp, "frozen_targets", lambda *_: info)
    monkeypatch.setattr(exp, "validate_monday_inputs", lambda *_: (_ for _ in ()).throw(exp.MondayInputError("bad")))
    called = False
    def client_factory(_cap):
        nonlocal called
        called = True
        raise AssertionError("KIS client must not be created")
    rc = exp.run_monday(tmp_path / "monday", tmp_path / "saturday", client_factory=client_factory,
                        now=lambda: datetime(2026, 11, 23, 8, 0, tzinfo=exp.SEOUL))
    assert rc == 13
    assert called is False


def test_deadline_and_request_limit_are_unchanged():
    assert exp.MON_DEADLINE == datetime(2026, 11, 23, 8, 45, tzinfo=exp.SEOUL)
    assert 2 * 936 + exp.REQUEST_CAP_EXTRA == 2072


def test_delayed_recovery_has_scoped_45_minute_deadline():
    started = datetime(2026, 11, 23, 9, 50, tzinfo=exp.SEOUL)
    assert exp.monday_effective_deadline(
        started, date(2026, 11, 20), delayed_recovery=True
    ) == started + timedelta(minutes=45)
    assert exp.monday_effective_deadline(
        started, date(2026, 11, 20), delayed_recovery=False
    ) == exp.MON_DEADLINE


@pytest.mark.parametrize("started,trade_date", [
    (datetime(2026, 11, 24, 8, 0, tzinfo=exp.SEOUL), date(2026, 11, 20)),
    (datetime(2026, 11, 23, 8, 0, tzinfo=exp.SEOUL), date(2026, 11, 19)),
])
def test_delayed_recovery_rejects_other_date_or_trade_date(started, trade_date):
    with pytest.raises(exp.MondayInputError):
        exp.monday_effective_deadline(started, trade_date, delayed_recovery=True)
