from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pipelines.market import kis_recovery as recovery


def _row(symbol="000001", *, close=100, volume=10, open_=90, high=110, low=80):
    return {
        "symbol": symbol,
        "trade_date": recovery.TRADE_DATE,
        "open": Decimal(open_), "high": Decimal(high), "low": Decimal(low),
        "close": Decimal(close), "volume": volume,
    }


def _krx(*, close=100, volume=10, open_=90, high=110, low=80):
    return {
        "TDD_OPNPRC": str(open_), "TDD_HGPRC": str(high),
        "TDD_LWPRC": str(low), "TDD_CLSPRC": str(close),
        "ACC_TRDVOL": str(volume),
    }


INITIAL_EVIDENCE = (
    Path(__file__).parent / "fixtures/kis_recovery_20261118_initial.json"
)


def test_initial_outage_classification_uses_frozen_evidence():
    """Reproduce the initial split without reading mutable Finalize output."""

    manifest = recovery.load_manifest()
    frozen = json.loads(INITIAL_EVIDENCE.read_text(encoding="utf-8"))
    capture = json.loads(
        (recovery.PROJECT_ROOT / manifest["source_capture_summary"]).read_text(
            encoding="utf-8"
        )
    )
    targets = set(capture["target_symbols"])
    captured = set(capture["captured_symbols"])
    capture_failed = set(capture["failed_symbols"])
    finalize_failed = set(manifest["finalize_symbols"])
    price_only = set(manifest["price_only_symbols"])
    baseline_completed = targets - finalize_failed - price_only
    groups = {
        "targets": targets,
        "captured": captured,
        "capture_failed": capture_failed,
        "finalize_opsq0008": finalize_failed,
        "baseline_completed": baseline_completed,
    }
    assert frozen["trade_date"] == recovery.TRADE_DATE.isoformat()
    for name, symbols in groups.items():
        assert len(symbols) == frozen["groups"][name]["count"]
        assert recovery.symbol_hash(symbols) == frozen["groups"][name]["sha256"]
    assert captured | capture_failed == targets
    assert baseline_completed | finalize_failed | price_only == targets
    assert not (baseline_completed & finalize_failed)
    assert not (baseline_completed & price_only)
    assert not (finalize_failed & price_only)


def test_repository_manifest_matches_current_recovered_file_state():
    """Current state is checked separately from the initial OPSQ0008 event."""

    manifest = recovery.load_manifest()
    finalize_symbols = set(manifest["finalize_symbols"])
    price_only_symbols = set(manifest["price_only_symbols"])
    marker_symbols = {
        path.stem
        for path in (
            recovery.DEFAULT_STATE_ROOT
            / recovery.TRADE_DATE.isoformat()
            / "finalized"
        ).glob("*.json")
    }
    assert len(marker_symbols) == 804
    assert finalize_symbols <= marker_symbols
    assert not (price_only_symbols & marker_symbols)
    assert recovery.symbol_hash(finalize_symbols) == manifest["finalize_symbols_sha256"]
    assert recovery.symbol_hash(price_only_symbols) == manifest["price_only_symbols_sha256"]
    assert all(
        recovery.snapshot_path(
            recovery.DEFAULT_STATE_ROOT, recovery.TRADE_DATE, symbol
        ).is_file()
        for symbol in finalize_symbols
    )
    assert all(
        not recovery.snapshot_path(
            recovery.DEFAULT_STATE_ROOT, recovery.TRADE_DATE, symbol
        ).is_file()
        for symbol in price_only_symbols
    )


def test_batches_are_bounded_and_cover_only_requested():
    symbols = tuple(f"{i:06d}" for i in range(169))
    batches = recovery.make_batches(symbols, 25)
    assert [len(batch) for batch in batches] == [25] + [24] * 6
    assert tuple(item for batch in batches for item in batch) == symbols
    assert [len(batch) for batch in recovery.make_batches(symbols[:132], 25)] == [22] * 6
    with pytest.raises(ValueError):
        recovery.make_batches(symbols, 26)


def test_single_batch_selection_cannot_spill_into_following_batches():
    batches = recovery.make_batches(tuple(f"{i:06d}" for i in range(169)), 25)
    selected = recovery.select_batches(batches, batch_number=1, max_batches=1)
    assert len(selected) == 1
    assert selected[0][0] == 1
    assert len(selected[0][1]) == 25
    assert "000025" not in selected[0][1]


def test_finalize_seventh_batch_exists_independently_of_price_batches():
    finalize = recovery.make_batches(tuple(f"{i:06d}" for i in range(169)), 25)
    prices = recovery.make_batches(tuple(f"{i:06d}" for i in range(132)), 25)
    assert len(recovery.select_batches(finalize, batch_number=7)) == 1
    with pytest.raises(ValueError):
        recovery.select_batches(prices, batch_number=7)


def test_allowlist_rejects_an_unapproved_symbol():
    with pytest.raises(recovery.RecoverySafetyError):
        recovery.assert_allowed(["000001", "999999"], ["000001"])


def test_capped_session_blocks_before_excess_call():
    class Delegate:
        calls = 0
        def get(self, *args, **kwargs):
            self.calls += 1
            return object()
        def close(self):
            pass
    delegate = Delegate()
    session = recovery.CappedSession(delegate, 2)
    session.get("a")
    session.get("b")
    with pytest.raises(recovery.RequestBudgetExceeded):
        session.get("c")
    assert delegate.calls == 2


def test_price_recovery_skips_existing_without_api(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("API must not be called")
    monkeypatch.setattr(recovery, "fetch_daily_range", forbidden)
    result = recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(),
        krx_rows={}, existing_symbols=["000001"],
    )
    assert result.skipped_existing == ["000001"]


def test_raw_or_adjusted_failure_prevents_save(monkeypatch):
    calls = []
    def fake_fetch(client, symbol, start, end, *, adjusted):
        if adjusted:
            raise RuntimeError("adjusted failed")
        return [_row(symbol)], False
    monkeypatch.setattr(recovery, "fetch_daily_range", fake_fetch)
    result = recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(),
        krx_rows={"000001": _krx()}, saver=lambda raw, adjusted: calls.append(1),
    )
    assert not calls
    assert "000001" in result.failed


@pytest.mark.parametrize("krx_row", [_krx(close=101), _krx(volume=11)])
def test_close_or_volume_mismatch_blocks_save(monkeypatch, krx_row):
    monkeypatch.setattr(
        recovery, "fetch_daily_range",
        lambda client, symbol, start, end, *, adjusted: ([_row(symbol)], False),
    )
    calls = []
    result = recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(),
        krx_rows={"000001": krx_row}, saver=lambda raw, adjusted: calls.append(1),
    )
    assert not calls
    assert "000001" in result.blocked_krx


def test_zero_volume_ohl_representation_is_allowed(monkeypatch):
    row = _row(volume=0, open_=100, high=100, low=100)
    monkeypatch.setattr(
        recovery, "fetch_daily_range",
        lambda client, symbol, start, end, *, adjusted: ([dict(row, symbol=symbol)], False),
    )
    calls = []
    result = recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(),
        krx_rows={"000001": _krx(volume=0, open_=0, high=0, low=0)},
        saver=lambda raw, adjusted: calls.append((raw, adjusted)),
    )
    assert len(calls) == 1
    assert result.comparisons["000001"]["zero_volume_ohl_difference_allowed"]


def test_price_only_path_never_creates_snapshot_or_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(
        recovery, "fetch_daily_range",
        lambda client, symbol, start, end, *, adjusted: ([_row(symbol)], False),
    )
    recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(),
        krx_rows={"000001": _krx()}, saver=lambda raw, adjusted: 2,
    )
    assert list(tmp_path.rglob("*")) == []


def test_metadata_always_uses_missing_only():
    seen = {}
    def saver(rows, *, missing_only):
        seen["missing_only"] = missing_only
        return {"updated_rows": len(rows), "deferred_keys": []}
    result = recovery.save_metadata_missing_only(
        [{"symbol": "000001", "trade_date": recovery.TRADE_DATE}],
        allowed_symbols=["000001"], saver=saver,
    )
    assert seen["missing_only"] is True
    assert result["updated_rows"] == 1


def test_consecutive_opsq_and_checkpoint_resume(monkeypatch, tmp_path):
    assert recovery.opsq0008_streak(["OPSQ0008", "OPSQ0008", "x", "OPSQ0008"]) == 2
    assert recovery.should_stop_for_opsq0008(["OPSQ0008"] * 5, 5)
    assert not recovery.should_stop_for_opsq0008(["OPSQ0008"] * 4, 5)
    path = tmp_path / "checkpoint.json"
    recovery.atomic_json(path, {
        "trade_date": recovery.TRADE_DATE.isoformat(),
        "saved_symbols": ["000001"],
    })
    assert recovery.checkpoint_symbols(path) == {"000001"}
    monkeypatch.setattr(
        recovery, "fetch_daily_range",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must skip")),
    )
    result = recovery.recover_price_batch(
        ["000001"], allowed_symbols=["000001"], client=object(), krx_rows={},
        checkpointed_symbols=recovery.checkpoint_symbols(path),
    )
    assert result.skipped_existing == ["000001"]


def test_regular_collection_windows_and_active_service_are_blocked():
    seoul = ZoneInfo("Asia/Seoul")
    with pytest.raises(recovery.RecoverySafetyError):
        recovery.assert_safe_execution_window(
            now=datetime(2026, 11, 19, 8, 0, tzinfo=seoul),
            active_checker=lambda unit: False,
        )
    with pytest.raises(recovery.RecoverySafetyError):
        recovery.assert_safe_execution_window(
            now=datetime(2026, 11, 19, 12, 0, tzinfo=seoul),
            active_checker=lambda unit: unit.endswith("capture.service"),
        )


def test_manifest_hash_changes_when_list_changes():
    manifest = recovery.load_manifest()
    changed = list(manifest["finalize_symbols"])
    changed[-1] = "999999"
    assert recovery.symbol_hash(changed) != manifest["finalize_symbols_sha256"]
