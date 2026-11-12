from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import diagnose_kis_daily_stability as diagnostic


SEOUL = ZoneInfo("Asia/Seoul")


class FakeClient:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def daily_page(self, symbol, start_date, end_date, *, adjusted):
        self.calls.append(("daily", symbol, start_date, end_date, adjusted))
        return [
            {
                "stck_bsop_date": "20261103",
                "stck_oprc": "100",
                "stck_hgpr": "120",
                "stck_lwpr": "90",
                "stck_clpr": "110",
                "acml_vol": "7",
            }
        ]

    def current_price(self, symbol):
        self.calls.append(("current", symbol))
        return {
            "stck_prpr": "110",
            "acml_vol": "7",
            "stck_sdpr": "109",
            "per": "2.2",
            "pbr": "1.1",
            "eps": "50",
            "bps": "100",
            "rprs_mrkt_kor_name": "KOSPI",
        }


def fixed_now():
    return datetime(2026, 11, 3, 22, 0, 1, tzinfo=SEOUL)


def test_probe_records_three_requests_per_symbol_without_basis_date(tmp_path, capsys):
    client = FakeClient()
    result = diagnostic.main(
        [
            "--trade-date", "2026-11-03",
            "--slot", "2200",
            "--log-dir", str(tmp_path),
        ],
        client_factory=lambda: client,
        service_checker=lambda: [],
        now=fixed_now,
    )

    assert result == 0
    assert len(client.calls) == 9
    for offset, symbol in enumerate(diagnostic.SYMBOLS):
        assert client.calls[offset * 3] == (
            "daily", symbol, date(2026, 11, 3), date(2026, 11, 3), False
        )
        assert client.calls[offset * 3 + 1][-1] is True
        assert client.calls[offset * 3 + 2] == ("current", symbol)

    path = tmp_path / "20261103.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    assert path.stat().st_mode & 0o777 == 0o600
    assert records[0]["current_quote"]["basis_trade_date"] is None
    assert records[0]["current_quote"]["stck_bsop_date"] is None
    assert records[0]["comparisons"] == {
        "pbr_price_minus_current": "0.0",
        "pbr_price_minus_raw_close": "0.0",
        "pbr_times_bps": "110.0",
        "per_price_minus_current": "0.0",
        "per_price_minus_raw_close": "0.0",
        "per_times_eps": "110.0",
        "raw_close_equals_current_price": True,
        "raw_close_equals_standard_price": False,
        "raw_volume_equals_current_volume": True,
    }
    output = json.loads(capsys.readouterr().out)
    assert output["record_count"] == 3


def test_active_service_blocks_before_client_or_log_creation(tmp_path, capsys):
    constructed = False

    def client_factory():
        nonlocal constructed
        constructed = True
        return FakeClient()

    result = diagnostic.main(
        [
            "--trade-date", "2026-11-03",
            "--slot", "2200",
            "--log-dir", str(tmp_path),
        ],
        client_factory=client_factory,
        service_checker=lambda: ["memos-market-refresh-evening.service"],
        now=fixed_now,
    )

    assert result == 2
    assert constructed is False
    assert not list(tmp_path.iterdir())
    output = json.loads(capsys.readouterr().err)
    assert output["status"] == "blocked_active_service"


def test_summary_uses_latest_record_per_slot_and_compares_stability(tmp_path, capsys):
    path = tmp_path / "20261103.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for slot, close, volume in (
        ("2200", "109", "6"),
        ("0200", "110", "7"),
        ("0800", "110", "7"),
    ):
        for symbol in diagnostic.SYMBOLS:
            records.append(
                {
                    "requested_trade_date": "2026-11-03",
                    "run_finished_at_kst": f"2026-11-04T{slot[:2]}:00:00+09:00",
                    "slot": slot,
                    "symbol": symbol,
                    "raw_daily": {"status": "ok", "close": close, "volume": volume},
                    "adjusted_daily": {"status": "ok", "close": close, "volume": volume},
                    "current_quote": {"status": "ok", "stck_prpr": close},
                    "comparisons": {},
                }
            )
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
    )

    result = diagnostic.main(
        [
            "--trade-date", "2026-11-03",
            "--summary",
            "--log-dir", str(tmp_path),
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    samsung = output["symbols"]["005930"]
    assert samsung["observed_slots"] == ["2200", "0200", "0800"]
    assert samsung["raw_close_stable"] is False
    assert samsung["raw_volume_stable"] is False
    assert samsung["raw_close_stable_since"] == "0200"
    assert samsung["raw_volume_stable_since"] == "0200"


def test_service_status_check_fails_closed_on_systemctl_error():
    class Result:
        returncode = 1

    def runner(*_args, **_kwargs):
        return Result()

    try:
        diagnostic.active_market_services(runner)
    except RuntimeError as exc:
        assert "안전하게 확인" in str(exc)
    else:
        raise AssertionError("systemctl 오류를 허용했습니다.")
