from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pipelines.market import finalize_recovery_state as state
from scripts import collect_kis_fundamentals_snapshots as snapshots


TRADE_DATE = date(2026, 11, 18)


class FakeClient:
    def close(self):
        pass


def _hash(symbols):
    value = "".join(f"{symbol}\n" for symbol in sorted(symbols))
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _price(symbol, *, metadata=False):
    row = {
        "symbol": symbol,
        "open": 100,
        "high": 110,
        "low": 90,
        "close": 105,
        "volume": 1000,
        "source": "KIS",
    }
    if metadata:
        row.update(
            market_cap=1000000,
            listed_shares=10000,
            market_metadata_source="KRX_OPEN_API",
        )
    return row


def _policy(tmp_path: Path, monkeypatch, symbols=("000001", "000002")):
    project = tmp_path / "project"
    manifest = project / "configs/recovery/manifest.json"
    manifest.parent.mkdir(parents=True)
    digest = _hash(symbols)
    manifest.write_text(
        json.dumps(
            {
                "trade_date": TRADE_DATE.isoformat(),
                "price_only_symbols": list(symbols),
                "price_only_symbols_sha256": digest,
            }
        )
    )
    policy = project / "configs/recovery/policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "trade_date": TRADE_DATE.isoformat(),
                        "status": "prices_only_complete",
                        "manifest": "configs/recovery/manifest.json",
                        "symbols_field": "price_only_symbols",
                        "symbols_sha256": digest,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(state, "PROJECT_ROOT", project)
    return policy, tuple(symbols)


def _db_state(symbols):
    return {
        "raw_rows": {symbol: _price(symbol, metadata=True) for symbol in symbols},
        "adjusted_rows": {symbol: _price(symbol) for symbol in symbols},
        "fundamental_symbols": set(),
    }


def test_only_manifest_hashed_price_only_symbols_are_suppressed(tmp_path, monkeypatch):
    policy, symbols = _policy(tmp_path, monkeypatch)
    state_root = tmp_path / "state"
    assert state.intentional_missing_symbols(
        TRADE_DATE,
        (*symbols, "005930"),
        state_root=state_root,
        policy_path=policy,
        state_loader=lambda day, values: _db_state(values),
    ) == symbols
    assert state.intentional_missing_symbols(
        date(2026, 11, 19),
        symbols,
        state_root=state_root,
        policy_path=policy,
        state_loader=lambda *_: (_ for _ in ()).throw(AssertionError("no DB")),
    ) == ()


@pytest.mark.parametrize("broken", ["raw", "adjusted", "metadata", "fundamentals"])
def test_missing_required_state_never_counts_as_complete(tmp_path, monkeypatch, broken):
    policy, symbols = _policy(tmp_path, monkeypatch)
    database = _db_state(symbols)
    if broken == "raw":
        database["raw_rows"].pop(symbols[0])
    elif broken == "adjusted":
        database["adjusted_rows"].pop(symbols[0])
    elif broken == "metadata":
        database["raw_rows"][symbols[0]]["market_cap"] = None
    else:
        database["fundamental_symbols"].add(symbols[0])
    with pytest.raises(state.IntentionalMissingStateError):
        state.intentional_missing_symbols(
            TRADE_DATE,
            symbols,
            state_root=tmp_path / "state",
            policy_path=policy,
            state_loader=lambda *_: database,
        )


def test_snapshot_or_finalize_marker_disables_suppression(tmp_path, monkeypatch):
    policy, symbols = _policy(tmp_path, monkeypatch)
    root = tmp_path / "state"
    path = root / TRADE_DATE.isoformat() / f"{symbols[0]}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(state.IntentionalMissingStateError):
        state.intentional_missing_symbols(
            TRADE_DATE,
            symbols,
            state_root=root,
            policy_path=policy,
            state_loader=lambda day, values: _db_state(values),
        )


def test_hash_drift_is_fail_closed(tmp_path, monkeypatch):
    policy, symbols = _policy(tmp_path, monkeypatch)
    payload = json.loads(policy.read_text())
    payload["entries"][0]["symbols_sha256"] = "0" * 64
    policy.write_text(json.dumps(payload))
    with pytest.raises(state.IntentionalMissingStateError):
        state.intentional_missing_symbols(
            TRADE_DATE,
            symbols,
            state_root=tmp_path / "state",
            policy_path=policy,
            state_loader=lambda day, values: _db_state(values),
        )


def test_finalize_auto_excludes_only_approved_symbols(monkeypatch, tmp_path):
    args = Namespace(
        symbols=None,
        symbol_limit=None,
        state_root=tmp_path,
        recovery_days=10,
        krx_warning_only=True,
    )
    monkeypatch.setattr(snapshots, "automatic_finalize_date", lambda _: TRADE_DATE)
    monkeypatch.setattr(snapshots, "pending_snapshot_dates", lambda *_a, **_k: (TRADE_DATE,))
    monkeypatch.setattr(snapshots, "capture_target_symbols", lambda *_: ("000001", "000002"))
    monkeypatch.setattr(snapshots, "intentional_missing_symbols", lambda *_a, **_k: ("000001",))
    monkeypatch.setattr(snapshots, "load_symbol_statuses", lambda: {})
    monkeypatch.setattr(snapshots, "symbols_needing_finalization", lambda *_: ("000001", "000002"))
    monkeypatch.setattr(snapshots, "fetch_kospi_daily", lambda _: [])
    monkeypatch.setattr(snapshots, "apply_savers", lambda: (object(), object()))
    monkeypatch.setattr(snapshots, "KisClient", FakeClient)
    captured = {}

    def finalize(symbols, *_args, **_kwargs):
        captured["symbols"] = tuple(symbols)
        return {"failed_symbols": [], "errors": {}}

    monkeypatch.setattr(snapshots, "finalize_snapshots", finalize)
    result, exit_code = snapshots._run_finalize_auto(
        args, datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
    )
    assert exit_code == 0
    assert captured["symbols"] == ("000002",)
    assert result["date_results"][TRADE_DATE.isoformat()][
        "intentional_missing_symbols"
    ] == ["000001"]


def test_real_failure_still_returns_exit_one(monkeypatch, tmp_path):
    args = Namespace(
        symbols=None,
        symbol_limit=None,
        state_root=tmp_path,
        recovery_days=10,
        krx_warning_only=True,
    )
    monkeypatch.setattr(snapshots, "automatic_finalize_date", lambda _: TRADE_DATE)
    monkeypatch.setattr(snapshots, "pending_snapshot_dates", lambda *_a, **_k: (TRADE_DATE,))
    monkeypatch.setattr(snapshots, "capture_target_symbols", lambda *_: ("000001",))
    monkeypatch.setattr(snapshots, "intentional_missing_symbols", lambda *_a, **_k: ())
    monkeypatch.setattr(snapshots, "load_symbol_statuses", lambda: {})
    monkeypatch.setattr(snapshots, "symbols_needing_finalization", lambda *_: ("000001",))
    monkeypatch.setattr(snapshots, "fetch_kospi_daily", lambda _: [])
    monkeypatch.setattr(snapshots, "apply_savers", lambda: (object(), object()))
    monkeypatch.setattr(snapshots, "KisClient", FakeClient)
    monkeypatch.setattr(
        snapshots,
        "finalize_snapshots",
        lambda *_a, **_k: {
            "failed_symbols": ["000001"],
            "errors": {"000001": {"error": "new failure"}},
        },
    )
    result, exit_code = snapshots._run_finalize_auto(
        args, datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
    )
    assert exit_code == 1
    assert result["failed_dates"] == [TRADE_DATE.isoformat()]
