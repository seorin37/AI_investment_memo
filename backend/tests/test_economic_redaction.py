from __future__ import annotations

import json
from datetime import date

import pytest
import requests
from urllib3.exceptions import MaxRetryError

from pipelines.economic import ecos, fred, pipeline
from pipelines.economic.redaction import redact_secrets, redact_value


ECOS_KEY = "FAKEECOSKEY0123456789"
FRED_KEY = "fakefredkey0123456789abcdef"


@pytest.fixture(autouse=True)
def _fake_keys(monkeypatch):
    monkeypatch.setenv("ECOS_API_KEY", ECOS_KEY)
    monkeypatch.setenv("FRED_API_KEY", FRED_KEY)


def _http_error_response(url: str, status: int = 403) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.reason = "Forbidden"
    response.url = url
    return response


def _fake_ecos_get(url, timeout):
    return _http_error_response(url)


def _fake_fred_get(url, params, timeout):
    prepared = requests.Request("GET", url, params=params).prepare()
    return _http_error_response(prepared.url)


# 1. 문자열 가리기 -----------------------------------------------------------


@pytest.mark.parametrize(
    "text, secret",
    [
        (
            "403 Client Error: Forbidden for url: https://ecos.bok.or.kr/api/"
            "StatisticSearch/SOMEKEY123/json/kr/1/1000/731Y003/D/20260101/20260102/0000003",
            "SOMEKEY123",
        ),
        (
            "HTTPSConnectionPool(host='ecos.bok.or.kr', port=443): Max retries exceeded "
            "with url: /api/StatisticSearch/SOMEKEY123/json/kr/1/1000/x (Caused by ...)",
            "SOMEKEY123",
        ),
        (
            "403 Client Error: for url: https://api.stlouisfed.org/fred/series/observations"
            "?series_id=DGS2&api_key=somefredkey999&file_type=json",
            "somefredkey999",
        ),
        ("...observations?API_KEY=somefredkey999", "somefredkey999"),
        ("...observations?series_id=DGS2&amp;api_key=somefredkey999", "somefredkey999"),
    ],
)
def test_redact_secrets_masks_url_formats_without_env(monkeypatch, text, secret):
    monkeypatch.delenv("ECOS_API_KEY")
    monkeypatch.delenv("FRED_API_KEY")
    redacted = redact_secrets(text)
    assert secret not in redacted
    assert "***" in redacted


def test_redact_secrets_masks_literal_env_values_anywhere():
    text = f"params={{'api_key': '{FRED_KEY}'}} ecos={ECOS_KEY}"
    redacted = redact_secrets(text)
    assert FRED_KEY not in redacted
    assert ECOS_KEY not in redacted


def test_redact_value_handles_nested_state():
    state = {"A:2026-01-01:2026-01-02": {"error": f"url /api/StatisticSearch/{ECOS_KEY}/json", "n": 3}}
    redacted = redact_value(state)
    assert ECOS_KEY not in json.dumps(redacted)
    assert redacted["A:2026-01-01:2026-01-02"]["n"] == 3


# 2. 다시 던지는 예외 ----------------------------------------------------------


def test_ecos_http_error_message_has_no_key(monkeypatch):
    monkeypatch.setattr(ecos.requests, "get", _fake_ecos_get)

    with pytest.raises(requests.HTTPError) as excinfo:
        ecos.fetch_ecos_series("731Y003/0000003", date(2026, 1, 1), date(2026, 1, 2))

    assert ECOS_KEY not in str(excinfo.value)
    assert "***" in str(excinfo.value)
    # 예외 타입과 응답 상태는 그대로 유지
    assert excinfo.value.response.status_code == 403


def test_fred_http_error_message_has_no_key(monkeypatch):
    monkeypatch.setattr(fred.requests, "get", _fake_fred_get)

    with pytest.raises(requests.HTTPError) as excinfo:
        fred.fetch_fred_series("DGS2", date(2026, 1, 1), date(2026, 1, 2))

    assert FRED_KEY not in str(excinfo.value)
    assert "api_key=***" in str(excinfo.value)


def test_connection_error_chain_has_no_key(monkeypatch):
    def fake_get(url, timeout):
        path = url.split("ecos.bok.or.kr", 1)[1]
        try:
            raise MaxRetryError(None, path, reason="boom")
        except MaxRetryError as inner:
            raise requests.ConnectionError(inner)

    monkeypatch.setattr(ecos.requests, "get", fake_get)

    with pytest.raises(requests.ConnectionError) as excinfo:
        ecos.fetch_ecos_series(
            "731Y003/0000003", date(2026, 1, 1), date(2026, 1, 2), max_attempts=1
        )

    assert ECOS_KEY not in str(excinfo.value)
    assert ECOS_KEY not in str(excinfo.value.__context__)


# 3. 상태 JSON·출력 ------------------------------------------------------------


def test_ecos_failed_state_json_and_print_have_no_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pipeline, "ECOS_STATE_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "ECOS_SERIES", {"USD_KRW": "731Y003/0000003"})
    monkeypatch.setattr(ecos.requests, "get", _fake_ecos_get)

    result = pipeline.backfill_ecos(
        date(2026, 1, 1), date(2026, 1, 2), request_interval=0, resume=False
    )

    assert result["failed"] == ["USD_KRW:2026-01-01:2026-01-02"]
    saved = (tmp_path / "ecos_failed.json").read_text(encoding="utf-8")
    assert ECOS_KEY not in saved
    state = json.loads(saved)
    entry = state["USD_KRW:2026-01-01:2026-01-02"]
    assert entry["error_type"] == "HTTPError"
    assert "/api/StatisticSearch/***/" in entry["error"]
    assert ECOS_KEY not in capsys.readouterr().out


def test_fred_failed_state_json_and_print_have_no_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pipeline, "FRED_STATE_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "FRED_SERIES", {"US_TREASURY_2Y": "DGS2"})
    monkeypatch.setattr(fred.requests, "get", _fake_fred_get)

    result = pipeline.backfill_fred(
        date(2026, 1, 1), date(2026, 1, 2), request_interval=0, resume=False
    )

    assert result["failed"] == ["US_TREASURY_2Y:2026-01-01:2026-01-02"]
    saved = (tmp_path / "fred_failed.json").read_text(encoding="utf-8")
    assert FRED_KEY not in saved
    assert "api_key=***" in json.loads(saved)["US_TREASURY_2Y:2026-01-01:2026-01-02"]["error"]
    assert FRED_KEY not in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["ecos", "fred"])
def test_state_save_masks_even_unredacted_input(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(pipeline, f"{kind.upper()}_STATE_DIR", tmp_path)
    save = getattr(pipeline, f"save_{kind}_state")
    save("failed", {"k": {"error": f"leak {ECOS_KEY} {FRED_KEY} ?api_key=abcdefgh1234"}})

    saved = (tmp_path / f"{kind}_failed.json").read_text(encoding="utf-8")
    assert ECOS_KEY not in saved
    assert FRED_KEY not in saved
    assert "abcdefgh1234" not in saved
