from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from pipelines.market import kis


def daily_row(
    day: str = "20261027",
    *,
    open_: str = "100",
    high: str = "120",
    low: str = "90",
    close: str = "110",
    volume: str = "7",
    trade_value: str = "770",
) -> dict[str, str]:
    return {
        "stck_bsop_date": day,
        "stck_oprc": open_,
        "stck_hgpr": high,
        "stck_lwpr": low,
        "stck_clpr": close,
        "acml_vol": volume,
        "acml_tr_pbmn": trade_value,
    }


def test_normalize_distinguishes_raw_and_adjusted_ohlcv():
    raw = kis.normalize_daily_row("005930", daily_row(), adjusted=False)
    adjusted = kis.normalize_daily_row("005930", daily_row(), adjusted=True)

    assert raw == {
        "symbol": "005930",
        "trade_date": date(2026, 10, 27),
        "open": Decimal("100"),
        "high": Decimal("120"),
        "low": Decimal("90"),
        "close": Decimal("110"),
        "volume": 7,
        "source": "KIS",
        "collected_at": raw["collected_at"],
        "trade_value": Decimal("770"),
        "market_cap": None,
        "listed_shares": None,
        "market_metadata_source": None,
    }
    assert adjusted["volume"] == 7
    assert adjusted["source"] == "KIS"
    assert adjusted["adjustment_basis"] == "KIS_FID_ORG_ADJ_PRC_0_V1"
    assert "trade_value" not in adjusted


def test_kis_normalization_accepts_uppercase_alphanumeric_symbol():
    raw = kis.normalize_daily_row("00104K", daily_row(), adjusted=False)
    assert raw["symbol"] == "00104K"


@pytest.mark.parametrize("symbol", ["00104k", "00-04K", "12345", "1234567"])
def test_kis_normalization_rejects_invalid_symbol(symbol):
    with pytest.raises(ValueError, match="종목코드"):
        kis.normalize_daily_row(symbol, daily_row(), adjusted=False)


def test_samsung_2018_split_values_remain_distinct():
    adjusted = kis.normalize_daily_row(
        "005930",
        daily_row(
            "20180427", open_="53380", high="53640", low="52440",
            close="53000", volume="30310800",
        ),
        adjusted=True,
    )
    raw = kis.normalize_daily_row(
        "005930",
        daily_row(
            "20180427", open_="2669000", high="2682000", low="2622000",
            close="2650000", volume="606216",
        ),
        adjusted=False,
    )

    assert adjusted["close"] == Decimal("53000")
    assert raw["close"] == Decimal("2650000")
    assert adjusted["volume"] == 30_310_800
    assert raw["volume"] == 606_216


def test_zero_ohlc_is_skipped_and_invalid_order_is_rejected():
    assert kis.normalize_daily_row(
        "005930", daily_row(open_="0", high="0", low="0", close="0"), adjusted=True
    ) is None
    with pytest.raises(ValueError, match="고가"):
        kis.normalize_daily_row(
            "005930", daily_row(open_="100", high="105", low="90", close="110"), adjusted=False
        )


class PageClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def daily_page(self, symbol, start_date, end_date, *, adjusted):
        self.calls.append((symbol, start_date, end_date, adjusted))
        return self.pages.pop(0)


def test_daily_range_pages_backward_without_duplicates():
    newest = [daily_row(f"202610{day:02d}") for day in range(1, 29)]
    # Force the official 100-row continuation path with harmless duplicates.
    first = newest + [daily_row("20261001") for _ in range(72)]
    second = [daily_row("20260930")]
    client = PageClient([first, second])

    rows, zero_rows = kis.fetch_daily_range(
        client, "005930", date(2026, 9, 30), date(2026, 10, 28), adjusted=True
    )

    assert zero_rows == 0
    assert len(rows) == 29
    assert client.calls[0][3] is True
    assert client.calls[1][2] == date(2026, 9, 30)


def test_daily_range_paginates_from_2020_without_gaps_or_duplicates():
    start = date(2020, 1, 1)
    end = date(2026, 10, 28)
    expected_dates = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            expected_dates.append(cursor)
        cursor += timedelta(days=1)

    class HistoricalClient:
        def __init__(self):
            self.calls = []

        def daily_page(self, symbol, page_start, page_end, *, adjusted):
            self.calls.append((symbol, page_start, page_end, adjusted))
            dates = [
                day for day in expected_dates
                if page_start <= day <= page_end
            ]
            return [
                daily_row(day.strftime("%Y%m%d"))
                for day in sorted(dates, reverse=True)[:100]
            ]

    client = HistoricalClient()
    rows, zero_rows = kis.fetch_daily_range(
        client, "005930", start, end, adjusted=True
    )

    actual_dates = [row["trade_date"] for row in rows]
    assert actual_dates == expected_dates
    assert len(actual_dates) == len(set(actual_dates))
    assert zero_rows == 0
    assert len(client.calls) == (len(expected_dates) + 99) // 100
    assert all(
        later[2] < earlier[2]
        for earlier, later in zip(client.calls, client.calls[1:])
    )


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class Session:
    def __init__(self):
        self.post_calls = 0
        self.get_calls = []

    def post(self, *args, **kwargs):
        self.post_calls += 1
        return Response(
            200,
            {
                "access_token": "secret-token",
                "access_token_token_expired": "2099-01-01 00:00:00",
            },
        )

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return Response(200, {"rt_cd": "0", "output": {"stck_prpr": "100"}})


class Clock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


def test_token_is_reused_and_requests_are_rate_limited(monkeypatch):
    monkeypatch.delenv("KIS_REQUEST_INTERVAL", raising=False)
    session = Session()
    clock = Clock()
    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=session,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    client.current_price("005930")
    client.current_price("000660")

    assert session.post_calls == 1
    assert len(session.get_calls) == 2
    assert sum(clock.sleeps) >= 2.10
    assert client.request_interval == 1.05
    assert all(call[1]["headers"]["authorization"] == "Bearer secret-token" for call in session.get_calls)


def test_rate_limit_covers_token_raw_adjusted_and_fundamentals():
    clock = Clock()
    request_times = []

    class TimedSession(Session):
        def post(self, *args, **kwargs):
            request_times.append(("token", clock.monotonic()))
            return super().post(*args, **kwargs)

        def get(self, *args, **kwargs):
            request_times.append(("quotation", clock.monotonic()))
            path = args[0]
            if path.endswith(kis.DAILY_PATH):
                return Response(200, {"rt_cd": "0", "output2": [daily_row()]})
            return super().get(*args, **kwargs)

    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=TimedSession(),
        request_interval=1.05,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    client.daily_page("005930", date(2026, 10, 27), date(2026, 10, 27), adjusted=False)
    client.daily_page("005930", date(2026, 10, 27), date(2026, 10, 27), adjusted=True)
    client.current_price("005930")

    assert [kind for kind, _ in request_times] == [
        "token", "quotation", "quotation", "quotation"
    ]
    assert all(
        later - earlier >= 1.05
        for (_, earlier), (_, later) in zip(request_times, request_times[1:])
    )
    assert client.request_metrics() == {
        "total": 4,
        "token": 1,
        "quotation": 3,
        "retries": 0,
        "rate_limit_errors": 0,
    }


@pytest.mark.parametrize("interval", [0.5, 0.2])
def test_configurable_request_interval_is_applied(interval):
    clock = Clock()
    request_times = []

    class TimedSession(Session):
        def post(self, *args, **kwargs):
            request_times.append(clock.monotonic())
            return super().post(*args, **kwargs)

        def get(self, *args, **kwargs):
            request_times.append(clock.monotonic())
            return super().get(*args, **kwargs)

    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=TimedSession(),
        request_interval=interval,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    client.current_price("005930")
    client.current_price("000660")

    assert client.request_interval == interval
    assert all(
        later - earlier >= interval
        for earlier, later in zip(request_times, request_times[1:])
    )


def test_request_interval_can_be_selected_from_environment(monkeypatch):
    monkeypatch.setenv("KIS_REQUEST_INTERVAL", "0.5")

    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=Session(),
    )

    assert client.request_interval == 0.5


def test_egw00201_uses_cooldown_and_bounded_retry():
    clock = Clock()

    class LimitedSession(Session):
        def get(self, *args, **kwargs):
            self.get_calls.append((args, kwargs))
            if len(self.get_calls) == 1:
                return Response(
                    200,
                    {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "rate limited"},
                )
            return Response(200, {"rt_cd": "0", "output": {"stck_prpr": "100"}})

    session = LimitedSession()
    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=session,
        request_interval=0.5,
        rate_limit_cooldown=7.0,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert client.current_price("005930")["stck_prpr"] == "100"
    assert len(session.get_calls) == 2
    assert 7.0 in clock.sleeps
    assert client.request_metrics()["rate_limit_errors"] == 1
    assert client.request_metrics()["retries"] == 1


def test_egw00201_exhaustion_raises_without_infinite_retry():
    clock = Clock()

    class AlwaysLimitedSession(Session):
        def get(self, *args, **kwargs):
            self.get_calls.append((args, kwargs))
            return Response(
                200,
                {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "rate limited"},
            )

    session = AlwaysLimitedSession()
    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=session,
        request_interval=0.5,
        rate_limit_cooldown=7.0,
        max_attempts=2,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    with pytest.raises(kis.KisApiError, match="EGW00201"):
        client.current_price("005930")

    assert len(session.get_calls) == 2
    assert client.request_metrics()["rate_limit_errors"] == 2
    assert client.request_metrics()["retries"] == 1


def test_expired_long_run_token_cache_is_replaced(tmp_path):
    cache_path = tmp_path / "token.json"
    session = Session()
    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=session,
        request_interval=1.05,
        sleep=lambda _seconds: None,
        token_cache_path=cache_path,
    )
    client.current_price("005930")
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    client._token_expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

    client.current_price("000660")

    assert session.post_calls == 2
    assert client.request_metrics()["token"] == 2
    refreshed = json.loads(cache_path.read_text(encoding="utf-8"))
    assert refreshed["expires_at"] != "2000-01-01T00:00:00+00:00"


def test_unauthorized_token_is_invalidated_and_reissued(tmp_path):
    class AuthSession(Session):
        def post(self, *args, **kwargs):
            self.post_calls += 1
            return Response(200, {
                "access_token": f"token-{self.post_calls}",
                "access_token_token_expired": "2099-01-01 00:00:00",
            })

        def get(self, *args, **kwargs):
            self.get_calls.append((args, kwargs))
            if len(self.get_calls) == 1:
                return Response(401, {"msg_cd": "EGW00123", "msg1": "expired"})
            return Response(200, {"rt_cd": "0", "output": {"stck_prpr": "100"}})

    session = AuthSession()
    client = kis.KisClient(
        kis.KisCredentials("app", "secret"),
        session=session,
        request_interval=1.05,
        sleep=lambda _seconds: None,
        token_cache_path=tmp_path / "token.json",
    )

    assert client.current_price("005930")["stck_prpr"] == "100"
    assert session.post_calls == 2
    assert len(session.get_calls) == 2
    assert session.get_calls[0][1]["headers"]["authorization"] == "Bearer token-1"
    assert session.get_calls[1][1]["headers"]["authorization"] == "Bearer token-2"
    assert client.request_metrics()["retries"] == 1


def test_token_cache_is_reused_across_clients_without_reissuing(tmp_path):
    cache_path = tmp_path / "kis_token_cache.json"
    credentials = kis.KisCredentials("client-public-value", "client-private-value")
    first_session = Session()
    first = kis.KisClient(
        credentials,
        session=first_session,
        request_interval=1.05,
        sleep=lambda _seconds: None,
        token_cache_path=cache_path,
    )
    first.current_price("005930")

    second_session = Session()
    second = kis.KisClient(
        credentials,
        session=second_session,
        request_interval=1.05,
        sleep=lambda _seconds: None,
        token_cache_path=cache_path,
    )
    second.current_price("000660")

    assert first_session.post_calls == 1
    assert first.token_issued is True
    assert second_session.post_calls == 0
    assert second.token_cache_hit is True
    assert second.token_issued is False
    assert cache_path.stat().st_mode & 0o777 == 0o600
    cached = cache_path.read_text(encoding="utf-8")
    assert "client-public-value" not in cached
    assert "client-private-value" not in cached


def test_expired_token_cache_is_not_reused(tmp_path):
    cache_path = tmp_path / "kis_token_cache.json"
    credentials = kis.KisCredentials("app", "secret")
    expired = kis.KisClient(
        credentials,
        session=Session(),
        token_cache_path=cache_path,
        now=lambda: datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    expired._token = "expired-token"
    expired._token_expires_at = datetime(2026, 10, 28, tzinfo=timezone.utc)
    expired._save_cached_token()

    session = Session()
    client = kis.KisClient(
        credentials,
        session=session,
        request_interval=1.05,
        sleep=lambda _seconds: None,
        token_cache_path=cache_path,
        now=lambda: datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    client.current_price("005930")

    assert session.post_calls == 1
    assert client.token_cache_hit is False
    assert client.token_issued is True


def test_current_and_daily_use_only_quotation_parameters():
    class CaptureClient(kis.KisClient):
        def __init__(self):
            self.calls = []

        def _get(self, path, tr_id, params):
            self.calls.append((path, tr_id, params))
            if path == kis.PRICE_PATH:
                return {"output": {"stck_prpr": "100"}}
            return {"output2": [daily_row()]}

    client = CaptureClient()
    client.current_price("005930")
    client.daily_page(
        "005930", date(2026, 10, 1), date(2026, 10, 28), adjusted=True
    )
    client.daily_page(
        "005930", date(2026, 10, 1), date(2026, 10, 28), adjusted=False
    )

    assert client.calls[0][0:2] == (kis.PRICE_PATH, kis.PRICE_TR_ID)
    assert client.calls[1][2]["FID_COND_MRKT_DIV_CODE"] == "J"
    assert client.calls[1][2]["FID_ORG_ADJ_PRC"] == "0"
    assert client.calls[2][2]["FID_ORG_ADJ_PRC"] == "1"
    assert all("order" not in path for path, _, _ in client.calls)


def test_fundamentals_preserve_zero_negative_and_final_close():
    current = {
        "per": "0.00",
        "pbr": "1.25",
        "eps": "-100.50",
        "bps": "1000",
        "w52_hgpr": "200",
        "w52_hgpr_date": "20260601",
        "w52_lwpr": "80",
        "w52_lwpr_date": "20251101",
        "hts_avls": "1234",
        "lstn_stcn": "1000000",
        "stck_prpr": "105",
        "acml_vol": "0",
    }
    result = kis.normalize_fundamentals(
        "005930",
        current,
        {"trade_date": date(2026, 10, 27), "close": Decimal("105")},
        collected_at=datetime(2026, 10, 27, 8, tzinfo=timezone.utc),
    )

    assert result["per"] == Decimal("0.00")
    assert result["eps"] == Decimal("-100.50")
    assert result["market_cap"] == Decimal("123400000000")
    assert result["reference_price"] == Decimal("105")
    assert result["final_close"] == Decimal("105")


def test_fundamentals_reject_price_mismatch_and_intraday_ambiguity():
    current = {
        "per": "1", "pbr": "1", "eps": "100", "bps": "100",
        "w52_hgpr": "120", "w52_hgpr_date": "20261001",
        "w52_lwpr": "80", "w52_lwpr_date": "20251101",
        "hts_avls": "1", "lstn_stcn": "1000",
        "stck_prpr": "101", "acml_vol": "0",
    }
    final = {"trade_date": date(2026, 10, 28), "close": Decimal("100")}
    collected = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="일치하지 않습니다"):
        kis.normalize_fundamentals(
            "005930", current, final, collected_at=collected
        )

    current["stck_prpr"] = "100"
    with pytest.raises(ValueError, match="장 마감 후"):
        kis.normalize_fundamentals(
            "005930",
            current,
            final,
            collected_at=datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc),
        )


def test_fundamentals_reject_previous_session_even_before_market_open():
    current = {
        "per": "1", "pbr": "1", "eps": "100", "bps": "100",
        "w52_hgpr": "120", "w52_hgpr_date": "20261001",
        "w52_lwpr": "80", "w52_lwpr_date": "20251101",
        "hts_avls": "1", "lstn_stcn": "1000",
        "stck_prpr": "100", "acml_vol": "12345",
    }
    with pytest.raises(ValueError, match="기준일"):
        kis.normalize_fundamentals(
            "005930",
            current,
            {"trade_date": date(2026, 10, 28), "close": Decimal("100")},
            collected_at=datetime(2026, 10, 28, 15, 15, tzinfo=timezone.utc),
        )


def test_collect_fundamentals_skips_holiday_or_unfinalized_date_without_api():
    class Client:
        def current_price(self, _symbol):
            raise AssertionError("투자지표 API를 호출하면 안 됩니다.")

    result = kis.collect_fundamentals(
        Client(),
        ("005930", "000660"),
        {
            "005930": {
                "trade_date": date(2026, 10, 29),
                "close": Decimal("100"),
            }
        },
        collected_at=datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc),
    )

    assert result["saved_rows"] == 0
    assert result["failed_symbols"] == []
    assert result["skipped_symbols"] == ["005930", "000660"]


def test_collect_fundamentals_saves_same_day_post_close_snapshot():
    calls = []

    class Client:
        def current_price(self, symbol):
            calls.append(symbol)
            return {
                "per": "10", "pbr": "1", "eps": "10", "bps": "100",
                "w52_hgpr": "120", "w52_hgpr_date": "20261001",
                "w52_lwpr": "80", "w52_lwpr_date": "20251101",
                "hts_avls": "1", "lstn_stcn": "1000",
                "stck_prpr": "100", "acml_vol": "12345",
            }

    saved = []
    result = kis.collect_fundamentals(
        Client(),
        ("005930",),
        {
            "005930": {
                "trade_date": date(2026, 10, 30),
                "close": Decimal("100"),
                "volume": 12345,
            }
        },
        saver=lambda rows: saved.extend(rows) or len(rows),
        collected_at=datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc),
    )

    assert calls == ["005930"]
    assert result["saved_rows"] == 1
    assert result["failed_symbols"] == []
    assert result["skipped_symbols"] == []
    assert saved[0]["basis_trade_date"] == date(2026, 10, 30)


def test_backfill_isolates_symbol_failure_and_preserves_success(tmp_path):
    class Client:
        def daily_page(self, symbol, *_args, adjusted):
            if symbol == "000660":
                raise kis.KisApiError("provider unavailable")
            return [daily_row()]

    saved = []
    result = kis.backfill_kis_prices(
        date(2026, 10, 27),
        date(2026, 10, 27),
        ("005930", "000660"),
        client=Client(),
        resume=False,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or len(raw) + len(adjusted),
    )

    assert result["completed_symbols"] == ["005930"]
    assert result["failed_symbols"] == ["000660"]
    assert len(saved) == 1
    assert len(saved[0][0]) == len(saved[0][1]) == 1


def test_backfill_isolates_provider_rejection_of_alphanumeric_symbol(tmp_path):
    class Client:
        def daily_page(self, symbol, *_args, adjusted):
            if symbol == "00104K":
                raise kis.KisApiError("provider rejected symbol")
            return [daily_row()]

    saved = []
    result = kis.backfill_kis_prices(
        date(2026, 10, 27),
        date(2026, 10, 27),
        ("00104K", "005930"),
        client=Client(),
        resume=False,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )

    assert result["failed_symbols"] == ["00104K"]
    assert result["completed_symbols"] == ["005930"]
    assert len(saved) == 1
    assert saved[0][0][0]["symbol"] == saved[0][1][0]["symbol"] == "005930"


def test_901_symbol_mock_run_has_no_missing_duplicates_or_order_drift(tmp_path):
    symbols = tuple(f"{number:06d}" for number in range(1, 902))

    class BulkClient:
        def __init__(self):
            self.calls = []

        def daily_page(self, symbol, _start, _end, *, adjusted):
            self.calls.append((symbol, adjusted))
            return [daily_row("20261028")]

        def current_price(self, symbol):
            self.calls.append((symbol, "fundamentals"))
            return {
                "per": "1", "pbr": "1", "eps": "100", "bps": "100",
                "w52_hgpr": "120", "w52_hgpr_date": "20261001",
                "w52_lwpr": "80", "w52_lwpr_date": "20251101",
                "hts_avls": "1", "lstn_stcn": "1000",
                "stck_prpr": "110", "acml_vol": "0",
            }

    client = BulkClient()
    stored = {}

    def saver(raw, adjusted):
        for kind, rows in (("raw", raw), ("adjusted", adjusted)):
            for row in rows:
                stored[(kind, row["symbol"], row["trade_date"])] = row
        return len(raw) + len(adjusted)

    result = kis.backfill_kis_prices(
        date(2026, 10, 28),
        date(2026, 10, 28),
        symbols,
        client=client,
        resume=True,
        state_root=tmp_path,
        saver=saver,
    )
    final_rows = {
        symbol: {"trade_date": date(2026, 10, 28), "close": Decimal("110")}
        for symbol in symbols
    }
    fundamentals = kis.collect_fundamentals(
        client,
        symbols,
        final_rows,
        saver=lambda rows: len(rows),
        collected_at=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc),
    )

    assert result["completed_symbols"] == list(symbols)
    assert result["failed_symbols"] == []
    assert len(stored) == 901 * 2
    assert len(client.calls) == 901 * 3
    assert client.calls[:6] == [
        (symbols[0], False), (symbols[0], True),
        (symbols[1], False), (symbols[1], True),
        (symbols[2], False), (symbols[2], True),
    ]
    assert client.calls[1802:] == [
        (symbol, "fundamentals") for symbol in symbols
    ]
    assert fundamentals == {
        "saved_rows": 901,
        "failed_symbols": [],
        "errors": {},
        "skipped_symbols": [],
        "skip_reasons": {},
    }


def test_incomplete_date_detection_recovers_gap_and_partial_checkpoint(tmp_path):
    class Row:
        def __init__(self, values):
            self.values = values

        def one(self):
            return self.values

    class Connection:
        def __init__(self, values):
            self.values = values

        def execute(self, *_args, **_kwargs):
            return Row(self.values)

    class Connect:
        def __init__(self, values):
            self.values = values

        def __enter__(self):
            return Connection(self.values)

        def __exit__(self, *_args):
            return False

    class Engine:
        def __init__(self, values):
            self.values = values

        def connect(self):
            return Connect(self.values)

    state = tmp_path / "daily" / "2026-10-27"
    state.mkdir(parents=True)
    (state / "kis_prices_completed.json").write_text(
        json.dumps({
            "005930:2026-10-27:2026-10-27:raw=True:adjusted=True": {}
        }),
        encoding="utf-8",
    )
    dates = kis.find_incomplete_kis_dates(
        date(2026, 10, 28),
        ("005930", "000660"),
        state_root=tmp_path,
        engine=Engine((date(2026, 10, 26), date(2026, 10, 26))),
    )
    assert dates == (date(2026, 10, 27), date(2026, 10, 28))


def test_daily_symbol_snapshot_is_stable_when_market_membership_changes(tmp_path):
    trade_date = date(2026, 10, 28)
    original = ("000001", "000002")

    assert kis.freeze_daily_symbols(
        trade_date, original, state_root=tmp_path
    ) == original
    assert kis.freeze_daily_symbols(
        trade_date,
        ("000002", "000003"),
        state_root=tmp_path,
    ) == original

    manifest = json.loads(
        (tmp_path / "daily" / "2026-10-28" / "target_symbols.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["target_count"] == 2
    assert manifest["symbols"] == list(original)


def test_empty_database_schedules_only_current_session():
    class Result:
        def one(self):
            return None, None

    class Connection:
        def execute(self, *_args, **_kwargs):
            return Result()

    class Connect:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            return Connect()

    assert kis.find_incomplete_kis_dates(
        date(2026, 10, 28), ("005930",), engine=Engine()
    ) == (date(2026, 10, 28),)


def test_backfill_records_failed_year_and_resumes_only_that_chunk(monkeypatch, tmp_path):
    calls = []
    fail_2021_adjusted = True

    def fake_fetch(_client, symbol, start_date, end_date, *, adjusted):
        calls.append((symbol, start_date, end_date, adjusted))
        if adjusted and start_date.year == 2021 and fail_2021_adjusted:
            raise kis.KisApiError("provider unavailable")
        return [
            kis.normalize_daily_row(
                symbol,
                daily_row(start_date.strftime("%Y%m%d")),
                adjusted=adjusted,
            )
        ], 0

    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    saved = []
    first = kis.backfill_kis_prices(
        date(2020, 1, 1),
        date(2022, 12, 31),
        ("005930",),
        client=object(),
        resume=True,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )

    failed_key = "005930:2021-01-01:2021-12-31:raw=True:adjusted=True"
    failures = json.loads(
        (tmp_path / "kis_prices_failed.json").read_text(encoding="utf-8")
    )
    assert first["failed_chunks"] == [failed_key]
    assert failures[failed_key]["status"] == "failed"
    assert len(saved) == 2

    calls.clear()
    fail_2021_adjusted = False
    second = kis.backfill_kis_prices(
        date(2020, 1, 1),
        date(2022, 12, 31),
        ("005930",),
        client=object(),
        resume=True,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )

    assert {(start.year, adjusted) for _, start, _, adjusted in calls} == {
        (2021, False),
        (2021, True),
    }
    assert len(second["skipped_chunks"]) == 2
    assert second["completed_symbols"] == ["005930"]
    assert second["remaining_failures"] == 0
    assert len(saved) == 3


@pytest.mark.parametrize("failed_adjusted", [False, True])
def test_backfill_does_not_save_when_only_one_price_side_fails(
    monkeypatch, tmp_path, failed_adjusted
):
    calls = []

    def fake_fetch(_client, symbol, start_date, _end_date, *, adjusted):
        calls.append(adjusted)
        if adjusted is failed_adjusted:
            raise kis.KisApiError("one side failed")
        return [
            kis.normalize_daily_row(
                symbol,
                daily_row(start_date.strftime("%Y%m%d")),
                adjusted=adjusted,
            )
        ], 0

    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    saved = []
    result = kis.backfill_kis_prices(
        date(2026, 1, 1),
        date(2026, 1, 2),
        ("005930",),
        client=object(),
        resume=False,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )

    assert saved == []
    assert result["failed_symbols"] == ["005930"]
    assert result["remaining_failures"] == 1
    assert calls == ([False] if failed_adjusted is False else [False, True])


@pytest.mark.parametrize("empty_adjusted", [False, True])
def test_backfill_does_not_save_when_only_one_price_side_is_empty(
    monkeypatch, tmp_path, empty_adjusted
):
    def fake_fetch(_client, symbol, start_date, _end_date, *, adjusted):
        if adjusted is empty_adjusted:
            return [], 0
        return [
            kis.normalize_daily_row(
                symbol,
                daily_row(start_date.strftime("%Y%m%d")),
                adjusted=adjusted,
            )
        ], 0

    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    saved = []
    result = kis.backfill_kis_prices(
        date(2026, 1, 1),
        date(2026, 1, 2),
        ("005930",),
        client=object(),
        resume=False,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )

    assert saved == []
    assert result["failed_symbols"] == ["005930"]
    assert result["remaining_failures"] == 1


def test_backfill_replays_idempotently_after_save_before_checkpoint(
    monkeypatch, tmp_path
):
    def fake_fetch(_client, symbol, start_date, _end_date, *, adjusted):
        return [
            kis.normalize_daily_row(
                symbol,
                daily_row(start_date.strftime("%Y%m%d")),
                adjusted=adjusted,
            )
        ], 0

    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    stored = {}
    save_calls = 0

    def upsert_saver(raw, adjusted):
        nonlocal save_calls
        save_calls += 1
        for kind, rows in (("raw", raw), ("adjusted", adjusted)):
            for row in rows:
                stored[(kind, row["symbol"], row["trade_date"])] = row
        return len(raw) + len(adjusted)

    original_atomic_json = kis._atomic_json
    writes = 0

    def interrupt_after_save(path, value):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise KeyboardInterrupt
        original_atomic_json(path, value)

    monkeypatch.setattr(kis, "_atomic_json", interrupt_after_save)
    with pytest.raises(KeyboardInterrupt):
        kis.backfill_kis_prices(
            date(2026, 1, 1),
            date(2026, 1, 2),
            ("005930",),
            client=object(),
            resume=True,
            state_root=tmp_path,
            saver=upsert_saver,
        )

    assert save_calls == 1
    assert len(stored) == 2
    failures = json.loads(
        (tmp_path / "kis_prices_failed.json").read_text(encoding="utf-8")
    )
    assert next(iter(failures.values()))["error_type"] == "KeyboardInterrupt"

    monkeypatch.setattr(kis, "_atomic_json", original_atomic_json)
    result = kis.backfill_kis_prices(
        date(2026, 1, 1),
        date(2026, 1, 2),
        ("005930",),
        client=object(),
        resume=True,
        state_root=tmp_path,
        saver=upsert_saver,
    )

    assert save_calls == 2
    assert len(stored) == 2
    assert result["completed_symbols"] == ["005930"]
    assert result["remaining_failures"] == 0


def test_backfill_records_page_interrupt_and_resumes(monkeypatch, tmp_path):
    interrupted = True

    def fake_fetch(_client, symbol, start_date, _end_date, *, adjusted):
        nonlocal interrupted
        if adjusted and interrupted:
            interrupted = False
            raise KeyboardInterrupt
        return [
            kis.normalize_daily_row(
                symbol,
                daily_row(start_date.strftime("%Y%m%d")),
                adjusted=adjusted,
            )
        ], 0

    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    saved = []
    with pytest.raises(KeyboardInterrupt):
        kis.backfill_kis_prices(
            date(2026, 1, 1),
            date(2026, 1, 2),
            ("005930",),
            client=object(),
            resume=True,
            state_root=tmp_path,
            saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
        )

    failures = json.loads(
        (tmp_path / "kis_prices_failed.json").read_text(encoding="utf-8")
    )
    assert next(iter(failures.values()))["error_type"] == "KeyboardInterrupt"
    assert saved == []

    result = kis.backfill_kis_prices(
        date(2026, 1, 1),
        date(2026, 1, 2),
        ("005930",),
        client=object(),
        resume=True,
        state_root=tmp_path,
        saver=lambda raw, adjusted: saved.append((raw, adjusted)) or 2,
    )
    assert len(saved) == 1
    assert result["completed_symbols"] == ["005930"]
    assert result["remaining_failures"] == 0


def test_refresh_stops_before_api_when_schema_is_missing(monkeypatch):
    api_constructed = False

    def missing_schema():
        raise kis.KisSchemaError("0011 required")

    class ForbiddenClient:
        def __init__(self):
            nonlocal api_constructed
            api_constructed = True

    monkeypatch.setattr(kis, "assert_kis_schema", missing_schema)
    monkeypatch.setattr(kis, "load_kospi_symbols", lambda **_kwargs: ("005930",))
    monkeypatch.setattr(kis, "KisClient", ForbiddenClient)

    with pytest.raises(kis.KisSchemaError, match="0011"):
        kis.refresh_kis_market_data(date(2026, 10, 1), date(2026, 10, 27))
    assert api_constructed is False


def test_refresh_freezes_one_target_snapshot_for_prices_and_fundamentals(
    monkeypatch, tmp_path
):
    target_calls = []
    price_calls = []
    fundamental_calls = []
    targets = ("000660", "005930")

    def load_targets(**kwargs):
        target_calls.append(kwargs)
        return targets

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request_metrics(self):
            return {
                "total": 0,
                "token": 0,
                "quotation": 0,
                "retries": 0,
                "rate_limit_errors": 0,
            }

        request_interval = 1.05
        rate_limit_cooldown = 61.0

    def backfill(start_date, end_date, symbols, **kwargs):
        symbol_count = len(tuple(symbols))
        price_calls.append((start_date, end_date, tuple(symbols), kwargs))
        return {
            "completed_symbols": list(symbols),
            "skipped_symbols": [],
            "failed_symbols": [],
            "completed_chunks": [],
            "skipped_chunks": [],
            "failed_chunks": [],
            "raw_rows": symbol_count,
            "adjusted_rows": symbol_count,
            "zero_ohlc_rows": 0,
            "remaining_failures": 0,
            "target_count": symbol_count,
            "completed_count": symbol_count,
            "skipped_count": 0,
            "failed_count": 0,
        }

    def fundamentals(_client, symbols, final_rows):
        fundamental_calls.append((tuple(symbols), final_rows))
        return {"saved_rows": len(tuple(symbols)), "failed_symbols": []}

    monkeypatch.setattr(kis, "load_kospi_symbols", load_targets)
    monkeypatch.setattr(kis, "assert_kis_schema", lambda: None)
    monkeypatch.setattr(kis, "KisClient", Client)
    monkeypatch.setattr(kis, "backfill_kis_prices", backfill)
    monkeypatch.setattr(
        kis,
        "find_incomplete_kis_dates",
        lambda *_args, **_kwargs: (date(2026, 10, 28),),
    )
    monkeypatch.setattr(
        kis,
        "load_latest_raw_prices",
        lambda symbols, _start, _end: {
            symbol: {"trade_date": date(2026, 10, 28), "close": Decimal("100")}
            for symbol in symbols
        },
    )
    monkeypatch.setattr(kis, "collect_fundamentals", fundamentals)
    monkeypatch.setattr(kis, "STATE_ROOT", tmp_path)

    result = kis.refresh_kis_market_data(
        date(2026, 10, 28),
        date(2026, 10, 28),
        symbols=("005930", "000660"),
        symbol_limit=2,
    )

    assert target_calls == [{"symbols": ("005930", "000660"), "limit": 2}]
    assert price_calls[0][2] == targets
    assert price_calls[0][3]["resume"] is True
    assert price_calls[0][3]["state_root"] == tmp_path / "daily" / "2026-10-28"
    assert fundamental_calls[0][0] == targets
    assert set(fundamental_calls[0][1]) == set(targets)
    assert result["target_count"] == 2
    assert result["processed_dates"] == ["2026-10-28"]
    assert result["incomplete_dates"] == []
    assert result["processed_symbol_dates"] == 2
    assert result["successful_symbol_dates"] == 2
    assert result["skipped_symbol_dates"] == 0
    assert result["failed_symbol_dates"] == 0
    assert result["request_metrics"] == {
        "total": 0,
        "token": 0,
        "quotation": 0,
        "retries": 0,
        "rate_limit_errors": 0,
        "request_interval_seconds": 1.05,
        "rate_limit_cooldown_seconds": 61.0,
    }
    persisted = json.loads(
        (tmp_path / "daily" / "2026-10-28" / "kis_run_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["target_count"] == 2
    assert persisted["prices"]["raw_rows"] == 2


def test_refresh_empty_target_fails_before_api(monkeypatch):
    api_constructed = False

    def no_targets(**_kwargs):
        raise ValueError("stocks에 KOSPI 수집 대상이 없습니다")

    class ForbiddenClient:
        def __init__(self):
            nonlocal api_constructed
            api_constructed = True

    monkeypatch.setattr(kis, "load_kospi_symbols", no_targets)
    monkeypatch.setattr(kis, "KisClient", ForbiddenClient)

    with pytest.raises(ValueError, match="수집 대상"):
        kis.refresh_kis_market_data(date(2026, 10, 28), date(2026, 10, 28))
    assert api_constructed is False


def test_save_queries_are_upserts_and_keep_legacy_market_metadata(monkeypatch):
    sql = []

    class Connection:
        def execute(self, statement, rows):
            sql.append((str(statement), rows))

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_):
            return False

    class Engine:
        def begin(self):
            return Begin()

    monkeypatch.setattr(kis, "get_engine", lambda: Engine())
    assert kis.save_kis_prices([{"symbol": "005930"}], [{"symbol": "005930"}]) == 2

    assert all("ON CONFLICT (symbol, trade_date) DO UPDATE" in item[0] for item in sql)
    assert "COALESCE(EXCLUDED.market_cap, prices_daily.market_cap)" in sql[0][0]
    assert "volume = EXCLUDED.volume" in sql[1][0]


def test_migration_preserves_legacy_sources_and_adds_new_schema():
    migration = Path("alembic/versions/0011_kis_market_data.py").read_text(encoding="utf-8")

    assert 'down_revision: Union[str, Sequence[str], None] = "0010_adjusted_prices_daily"' in migration
    assert "SET source = 'KRX_OPEN_API'" in migration
    assert "source IN ('PYKRX_NAVER', 'KIS')" in migration
    assert "CREATE TABLE stock_fundamentals_snapshot" in migration
    assert "ADD COLUMN volume bigint" in migration
