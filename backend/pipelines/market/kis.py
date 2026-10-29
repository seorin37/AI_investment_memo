"""KIS Open API market-data collector for the DB-managed KOSPI universe.

Only quotation endpoints are used.  Access tokens can be reused from a
permission-restricted local cache, credentials are never rendered in errors,
and database writes happen only after a symbol's raw and adjusted responses
have both been normalized successfully.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import bindparam, text

from pipelines.common.db import get_engine, load_env
from pipelines.market.calendar import is_krx_trading_day
from pipelines.market.stock_master import load_kospi_symbols


BACKFILL_START = date(2020, 1, 1)
SOURCE = "KIS"
ADJUSTMENT_BASIS = "KIS_FID_ORG_ADJ_PRC_0_V1"
BASE_URL = "https://openapi.koreainvestment.com:9443"
TOKEN_PATH = "/oauth2/tokenP"
PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
PRICE_TR_ID = "FHKST01010100"
DAILY_TR_ID = "FHKST03010100"
STATE_ROOT = Path(__file__).resolve().parents[3] / "logs" / "market"
KOSPI_BACKFILL_STATE_ROOT = STATE_ROOT / "kospi_all_v1"
TOKEN_CACHE_PATH = STATE_ROOT / "kis_token_cache.json"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
SEOUL = ZoneInfo("Asia/Seoul")


class KisConfigError(RuntimeError):
    pass


class KisApiError(RuntimeError):
    pass


class KisSchemaError(RuntimeError):
    pass


def _safe_exception(exc: Exception) -> str:
    if isinstance(exc, (KisApiError, KisConfigError, KisSchemaError, ValueError)):
        return str(exc)[:300]
    return type(exc).__name__


@dataclass(frozen=True)
class KisCredentials:
    app_key: str
    app_secret: str

    @classmethod
    def from_environment(cls) -> "KisCredentials":
        load_env()
        app_key = os.getenv("KIS_APP_KEY", "").strip()
        app_secret = os.getenv("KIS_APP_SECRET", "").strip()
        missing = [
            name
            for name, value in (
                ("KIS_APP_KEY", app_key),
                ("KIS_APP_SECRET", app_secret),
            )
            if not value
        ]
        if missing:
            raise KisConfigError(
                f"필수 KIS 환경변수가 없거나 비어 있습니다: {', '.join(missing)}"
            )
        return cls(app_key=app_key, app_secret=app_secret)


def _safe_error(response: requests.Response, payload: object = None) -> str:
    if not isinstance(payload, dict):
        try:
            payload = response.json()
        except ValueError:
            payload = {}
    code = str(payload.get("msg_cd") or payload.get("error_code") or "-")
    message = str(
        payload.get("msg1")
        or payload.get("error_description")
        or "응답 본문 확인 불가"
    )
    return f"KIS HTTP {response.status_code}, code={code}, message={message[:200]}"


class KisClient:
    """KIS quotation client with secure cross-process token reuse."""

    def __init__(
        self,
        credentials: KisCredentials | None = None,
        *,
        session: requests.Session | None = None,
        request_interval: float = 1.05,
        timeout: float = 20.0,
        max_attempts: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        token_cache_path: Path | None = None,
    ) -> None:
        if request_interval < 1.05:
            raise ValueError("KIS 요청 간격은 최소 1.05초여야 합니다.")
        if timeout <= 0 or max_attempts < 1:
            raise ValueError("timeout과 max_attempts 설정이 올바르지 않습니다.")
        supplied_credentials = credentials is not None
        self.credentials = credentials or KisCredentials.from_environment()
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.request_interval = request_interval
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.monotonic = monotonic
        self.now = now
        self.token_cache_path = (
            token_cache_path
            if token_cache_path is not None
            else (None if supplied_credentials else TOKEN_CACHE_PATH)
        )
        self._last_request_at: float | None = None
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self.token_cache_hit = False
        self.token_issued = False
        self.total_request_count = 0
        self.token_request_count = 0
        self.quotation_request_count = 0
        self.retry_count = 0

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> "KisClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _wait_for_slot(self) -> None:
        if self._last_request_at is not None:
            elapsed = self.monotonic() - self._last_request_at
            if elapsed < self.request_interval:
                self.sleep(self.request_interval - elapsed)

    def _mark_request(self) -> None:
        self._last_request_at = self.monotonic()

    def _token_valid(self) -> bool:
        if not self._token or not self._token_expires_at:
            return False
        return self.now() < self._token_expires_at - timedelta(minutes=5)

    def _credential_fingerprint(self) -> str:
        value = f"{self.credentials.app_key}\0{self.credentials.app_secret}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @contextmanager
    def _cache_lock(self):
        if self.token_cache_path is None:
            yield
            return
        import fcntl

        lock_path = self.token_cache_path.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.chmod(lock_path, 0o600)
        with os.fdopen(descriptor, "r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_cached_token(self) -> bool:
        path = self.token_cache_path
        if path is None or not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("credential_fingerprint") != self._credential_fingerprint():
                return False
            expiry = datetime.fromisoformat(str(payload["expires_at"]))
            if expiry.tzinfo is None:
                return False
            token = str(payload["access_token"])
            if not token:
                return False
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
        self._token = token
        self._token_expires_at = expiry.astimezone(timezone.utc)
        if not self._token_valid():
            self._token = None
            self._token_expires_at = None
            return False
        self.token_cache_hit = True
        return True

    def _save_cached_token(self) -> None:
        path = self.token_cache_path
        if path is None or not self._token or not self._token_expires_at:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "credential_fingerprint": self._credential_fingerprint(),
                        "access_token": self._token,
                        "expires_at": self._token_expires_at.isoformat(),
                    },
                    handle,
                )
            os.chmod(temporary, 0o600)
            temporary.replace(path)
            os.chmod(path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)

    def _request_new_token(self) -> str:
        self._wait_for_slot()
        self.total_request_count += 1
        self.token_request_count += 1
        response = self.session.post(
            BASE_URL + TOKEN_PATH,
            json={
                "grant_type": "client_credentials",
                "appkey": self.credentials.app_key,
                "appsecret": self.credentials.app_secret,
            },
            headers={"content-type": "application/json"},
            timeout=self.timeout,
        )
        self._mark_request()
        try:
            payload = response.json()
        except ValueError as exc:
            raise KisApiError(_safe_error(response)) from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if response.status_code != 200 or not token:
            raise KisApiError(_safe_error(response, payload))
        expiry_text = str(payload.get("access_token_token_expired", ""))
        try:
            expiry = datetime.strptime(expiry_text, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone(timedelta(hours=9))
            ).astimezone(timezone.utc)
        except ValueError:
            expiry = self.now() + timedelta(hours=23)
        self._token = str(token)
        self._token_expires_at = expiry
        self.token_issued = True
        return self._token

    def _invalidate_token(self, rejected_token: str) -> None:
        """Discard only the rejected cached token, preserving a newer peer token."""

        self._token = None
        self._token_expires_at = None
        path = self.token_cache_path
        if path is None:
            return
        with self._cache_lock():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return
            if payload.get("access_token") == rejected_token:
                path.unlink(missing_ok=True)

    def request_metrics(self) -> dict[str, int]:
        return {
            "total": self.total_request_count,
            "token": self.token_request_count,
            "quotation": self.quotation_request_count,
            "retries": self.retry_count,
        }

    def _issue_token(self) -> str:
        if self._token_valid():
            assert self._token is not None
            return self._token
        with self._cache_lock():
            if self._load_cached_token():
                assert self._token is not None
                return self._token
            token = self._request_new_token()
            self._save_cached_token()
            return token

    def _get(self, path: str, tr_id: str, params: dict[str, str]) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            token = self._issue_token()
            self._wait_for_slot()
            self.total_request_count += 1
            self.quotation_request_count += 1
            try:
                response = self.session.get(
                    BASE_URL + path,
                    headers={
                        "content-type": "application/json; charset=utf-8",
                        "authorization": f"Bearer {token}",
                        "appkey": self.credentials.app_key,
                        "appsecret": self.credentials.app_secret,
                        "tr_id": tr_id,
                    },
                    params=params,
                    timeout=self.timeout,
                )
                self._mark_request()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise KisApiError(_safe_error(response)) from exc
                if response.status_code == 200 and payload.get("rt_cd") == "0":
                    return payload
                error = KisApiError(_safe_error(response, payload))
                if response.status_code == 401 and attempt < self.max_attempts:
                    self._invalidate_token(token)
                    last_error = error
                    self.retry_count += 1
                    continue
                if response.status_code not in RETRYABLE_STATUSES:
                    raise error
                last_error = error
            except (requests.Timeout, requests.ConnectionError) as exc:
                self._mark_request()
                last_error = KisApiError(f"KIS 네트워크 일시 오류: {type(exc).__name__}")
            if attempt < self.max_attempts:
                self.retry_count += 1
                delay = max(self.request_interval, 2 ** (attempt - 1))
                self.sleep(delay + random.uniform(0, 0.1))
        assert last_error is not None
        raise last_error

    def current_price(self, symbol: str) -> dict[str, str]:
        _validate_symbol(symbol)
        payload = self._get(
            PRICE_PATH,
            PRICE_TR_ID,
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        output = payload.get("output")
        if not isinstance(output, dict):
            raise KisApiError("KIS 현재가 응답 output이 객체가 아닙니다.")
        return {str(key): str(value) for key, value in output.items()}

    def daily_page(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        adjusted: bool,
    ) -> list[dict[str, str]]:
        _validate_symbol(symbol)
        payload = self._get(
            DAILY_PATH,
            DAILY_TR_ID,
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
            },
        )
        output = payload.get("output2")
        if not isinstance(output, list):
            raise KisApiError("KIS 기간시세 응답 output2가 배열이 아닙니다.")
        return [
            {str(key): str(value) for key, value in row.items()}
            for row in output
            if isinstance(row, dict)
        ]


def _validate_symbol(symbol: str) -> None:
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError("종목코드는 6자리 숫자여야 합니다.")


def _decimal(value: object, field: str, *, nullable: bool = False) -> Decimal | None:
    text_value = str(value or "").replace(",", "").strip()
    if text_value in {"", "-"} and nullable:
        return None
    try:
        parsed = Decimal(text_value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} 값이 숫자가 아닙니다.") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} 값이 유한수가 아닙니다.")
    return parsed


def _integer(value: object, field: str, *, nullable: bool = False) -> int | None:
    parsed = _decimal(value, field, nullable=nullable)
    if parsed is None:
        return None
    if parsed != parsed.to_integral_value():
        raise ValueError(f"{field} 값이 정수가 아닙니다.")
    return int(parsed)


def _api_date(value: object, field: str, *, nullable: bool = False) -> date | None:
    text_value = str(value or "").strip()
    if not text_value and nullable:
        return None
    try:
        return datetime.strptime(text_value, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} 날짜 형식이 올바르지 않습니다.") from exc


def normalize_daily_row(symbol: str, row: dict[str, str], *, adjusted: bool) -> dict | None:
    _validate_symbol(symbol)
    prices = {
        "open": _decimal(row.get("stck_oprc"), "시가"),
        "high": _decimal(row.get("stck_hgpr"), "고가"),
        "low": _decimal(row.get("stck_lwpr"), "저가"),
        "close": _decimal(row.get("stck_clpr"), "종가"),
    }
    assert all(value is not None for value in prices.values())
    if any(value == 0 for value in prices.values()):
        return None
    if any(value < 0 for value in prices.values()):
        raise ValueError("OHLC는 음수일 수 없습니다.")
    if prices["high"] < max(prices.values()):
        raise ValueError("고가가 다른 OHLC보다 작습니다.")
    if prices["low"] > min(prices.values()):
        raise ValueError("저가가 다른 OHLC보다 큽니다.")
    volume = _integer(row.get("acml_vol"), "거래량")
    trade_value = _decimal(row.get("acml_tr_pbmn"), "거래대금", nullable=True)
    if volume is None or volume < 0 or (trade_value is not None and trade_value < 0):
        raise ValueError("거래량·거래대금은 음수일 수 없습니다.")
    normalized = {
        "symbol": symbol,
        "trade_date": _api_date(row.get("stck_bsop_date"), "영업일"),
        **prices,
        "volume": volume,
        "source": SOURCE,
        "collected_at": datetime.now(timezone.utc),
    }
    if adjusted:
        normalized["adjustment_basis"] = ADJUSTMENT_BASIS
    else:
        normalized.update(
            trade_value=trade_value,
            market_cap=None,
            listed_shares=None,
            market_metadata_source=None,
        )
    return normalized


def fetch_daily_range(
    client: KisClient,
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    adjusted: bool,
) -> tuple[list[dict], int]:
    if start_date > end_date:
        raise ValueError("시작일이 종료일보다 늦습니다.")
    collected: dict[date, dict] = {}
    zero_rows = 0
    cursor_end = end_date
    for _ in range(100):
        page = client.daily_page(symbol, start_date, cursor_end, adjusted=adjusted)
        in_range = []
        for raw in page:
            row_date = _api_date(raw.get("stck_bsop_date"), "영업일")
            assert row_date is not None
            if start_date <= row_date <= end_date:
                in_range.append((row_date, raw))
        if not in_range:
            break
        for row_date, raw in in_range:
            normalized = normalize_daily_row(symbol, raw, adjusted=adjusted)
            if normalized is None:
                zero_rows += 1
            else:
                collected[row_date] = normalized
        oldest = min(row_date for row_date, _ in in_range)
        if oldest <= start_date or len(page) < 100:
            break
        next_end = oldest - timedelta(days=1)
        if next_end >= cursor_end:
            raise KisApiError("KIS 기간시세 페이지가 과거 방향으로 진행되지 않았습니다.")
        cursor_end = next_end
    else:
        raise KisApiError("KIS 기간시세가 안전한 페이지 상한을 초과했습니다.")
    return [collected[key] for key in sorted(collected)], zero_rows


def normalize_fundamentals(
    symbol: str,
    current: dict[str, str],
    final_daily: dict,
    *,
    collected_at: datetime | None = None,
) -> dict:
    basis_date = final_daily["trade_date"]
    collected_at = collected_at or datetime.now(timezone.utc)
    nullable_decimal = lambda key, label: _decimal(current.get(key), label, nullable=True)
    nullable_integer = lambda key, label: _integer(current.get(key), label, nullable=True)
    market_cap_units = nullable_decimal("hts_avls", "시가총액")
    market_cap = market_cap_units * Decimal("100000000") if market_cap_units is not None else None
    reference_price = nullable_decimal("stck_prpr", "KIS 기준가격")
    final_close = final_daily["close"]
    current_volume = nullable_integer("acml_vol", "당일 누적거래량")
    if reference_price is None:
        raise ValueError("KIS 기준가격이 제공되지 않았습니다.")
    if reference_price != final_close:
        raise ValueError("KIS 기준가격이 최신 확정 원시 종가와 일치하지 않습니다.")
    collection_seoul = collected_at.astimezone(SEOUL)
    collection_date = collection_seoul.date()
    # KIS keeps the previous session's cumulative volume overnight.  It is
    # therefore safe to pair an unchanged reference price with the latest
    # finalized daily close before the regular session starts.  Once 09:00
    # KST is reached, a non-zero volume is treated conservatively as an
    # ambiguous live-session response.
    regular_session_started = collection_seoul.time() >= datetime_time(9, 0)
    if (
        basis_date < collection_date
        and current_volume != 0
        and regular_session_started
    ):
        raise ValueError(
            "이전 거래일 종가 기준 수집 중 당일 거래가 시작되어 기준일을 확정할 수 없습니다."
        )
    result = {
        "symbol": symbol,
        "basis_trade_date": basis_date,
        "per": nullable_decimal("per", "PER"),
        "pbr": nullable_decimal("pbr", "PBR"),
        "eps": nullable_decimal("eps", "EPS"),
        "bps": nullable_decimal("bps", "BPS"),
        "w52_high": nullable_decimal("w52_hgpr", "52주 최고가"),
        "w52_high_date": _api_date(current.get("w52_hgpr_date"), "52주 최고일", nullable=True),
        "w52_low": nullable_decimal("w52_lwpr", "52주 최저가"),
        "w52_low_date": _api_date(current.get("w52_lwpr_date"), "52주 최저일", nullable=True),
        "market_cap": market_cap,
        "listed_shares": nullable_integer("lstn_stcn", "상장주식수"),
        "reference_price": reference_price,
        "final_close": final_close,
        "source": SOURCE,
        "collected_at": collected_at,
    }
    if result["per"] is not None and result["per"] < 0:
        raise ValueError("PER은 음수일 수 없습니다.")
    if result["pbr"] is not None and result["pbr"] < 0:
        raise ValueError("PBR은 음수일 수 없습니다.")
    if result["listed_shares"] is not None and result["listed_shares"] <= 0:
        raise ValueError("상장주식수는 양수여야 합니다.")
    return result


def assert_kis_schema() -> None:
    required = {
        "prices_daily": {"source", "market_metadata_source"},
        "adjusted_prices_daily": {"volume", "source", "adjustment_basis"},
        "stock_fundamentals_snapshot": {
            "basis_trade_date", "per", "pbr", "eps", "bps", "w52_high",
            "w52_high_date", "w52_low", "w52_low_date", "market_cap",
            "listed_shares", "reference_price", "final_close", "source",
        },
    }
    statement = text(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name IN (
            'prices_daily', 'adjusted_prices_daily', 'stock_fundamentals_snapshot'
          )
        """
    )
    engine = get_engine()
    with engine.connect() as connection:
        present: dict[str, set[str]] = {}
        for table_name, column_name in connection.execute(statement):
            present.setdefault(table_name, set()).add(column_name)
    missing = {
        table: sorted(columns - present.get(table, set()))
        for table, columns in required.items()
        if columns - present.get(table, set())
    }
    if missing:
        raise KisSchemaError(
            "KIS 스키마가 준비되지 않았습니다. 0011 migration 적용 후 활성화하세요: "
            + json.dumps(missing, ensure_ascii=False)
        )


def save_kis_prices(raw_rows: list[dict], adjusted_rows: list[dict]) -> int:
    if not raw_rows and not adjusted_rows:
        return 0
    raw_statement = text(
        """
        INSERT INTO prices_daily (
          symbol, trade_date, open, high, low, close, volume, trade_value,
          market_cap, listed_shares, source, market_metadata_source
        ) VALUES (
          :symbol, :trade_date, :open, :high, :low, :close, :volume, :trade_value,
          :market_cap, :listed_shares, :source, :market_metadata_source
        )
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
          open = EXCLUDED.open,
          high = EXCLUDED.high,
          low = EXCLUDED.low,
          close = EXCLUDED.close,
          volume = EXCLUDED.volume,
          trade_value = EXCLUDED.trade_value,
          source = EXCLUDED.source,
          market_cap = COALESCE(EXCLUDED.market_cap, prices_daily.market_cap),
          listed_shares = COALESCE(EXCLUDED.listed_shares, prices_daily.listed_shares),
          market_metadata_source = COALESCE(
            EXCLUDED.market_metadata_source, prices_daily.market_metadata_source
          )
        """
    )
    adjusted_statement = text(
        """
        INSERT INTO adjusted_prices_daily (
          symbol, trade_date, open, high, low, close, volume,
          source, adjustment_basis, collected_at
        ) VALUES (
          :symbol, :trade_date, :open, :high, :low, :close, :volume,
          :source, :adjustment_basis, :collected_at
        )
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
          open = EXCLUDED.open,
          high = EXCLUDED.high,
          low = EXCLUDED.low,
          close = EXCLUDED.close,
          volume = EXCLUDED.volume,
          source = EXCLUDED.source,
          adjustment_basis = EXCLUDED.adjustment_basis,
          collected_at = EXCLUDED.collected_at
        """
    )
    engine = get_engine()
    with engine.begin() as connection:
        if raw_rows:
            connection.execute(raw_statement, raw_rows)
        if adjusted_rows:
            connection.execute(adjusted_statement, adjusted_rows)
    return len(raw_rows) + len(adjusted_rows)


def save_fundamentals(rows: list[dict]) -> int:
    if not rows:
        return 0
    statement = text(
        """
        INSERT INTO stock_fundamentals_snapshot (
          symbol, basis_trade_date, per, pbr, eps, bps,
          w52_high, w52_high_date, w52_low, w52_low_date,
          market_cap, listed_shares, reference_price, final_close,
          source, collected_at
        ) VALUES (
          :symbol, :basis_trade_date, :per, :pbr, :eps, :bps,
          :w52_high, :w52_high_date, :w52_low, :w52_low_date,
          :market_cap, :listed_shares, :reference_price, :final_close,
          :source, :collected_at
        )
        ON CONFLICT (symbol, basis_trade_date) DO UPDATE SET
          per = EXCLUDED.per,
          pbr = EXCLUDED.pbr,
          eps = EXCLUDED.eps,
          bps = EXCLUDED.bps,
          w52_high = EXCLUDED.w52_high,
          w52_high_date = EXCLUDED.w52_high_date,
          w52_low = EXCLUDED.w52_low,
          w52_low_date = EXCLUDED.w52_low_date,
          market_cap = EXCLUDED.market_cap,
          listed_shares = EXCLUDED.listed_shares,
          reference_price = EXCLUDED.reference_price,
          final_close = EXCLUDED.final_close,
          source = EXCLUDED.source,
          collected_at = EXCLUDED.collected_at
        """
    )
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(statement, rows)
    return len(rows)


def load_latest_raw_prices(
    symbols: Iterable[str],
    start_date: date,
    end_date: date,
) -> dict[str, dict]:
    """Load the latest persisted KIS raw close for each target in one query."""

    requested = tuple(symbols)
    if not requested:
        return {}
    statement = text(
        """
        SELECT DISTINCT ON (symbol) symbol, trade_date, close
        FROM prices_daily
        WHERE source = 'KIS'
          AND trade_date BETWEEN :start_date AND :end_date
          AND symbol IN :symbols
        ORDER BY symbol, trade_date DESC
        """
    ).bindparams(bindparam("symbols", expanding=True))
    engine = get_engine()
    with engine.connect() as connection:
        return {
            str(row.symbol).strip(): {
                "symbol": str(row.symbol).strip(),
                "trade_date": row.trade_date,
                "close": row.close,
            }
            for row in connection.execute(
                statement,
                {
                    "symbols": requested,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
        }


def _trading_dates(start_date: date, end_date: date) -> tuple[date, ...]:
    cursor = start_date
    result = []
    while cursor <= end_date:
        if is_krx_trading_day(cursor):
            result.append(cursor)
        cursor += timedelta(days=1)
    return tuple(result)


def _checkpoint_symbols(path: Path) -> set[str]:
    state = _load_json(path)
    return {str(key).split(":", 1)[0] for key in state}


def freeze_daily_symbols(
    target_date: date,
    symbols: Iterable[str],
    *,
    state_root: Path = STATE_ROOT,
) -> tuple[str, ...]:
    """Persist and reuse the exact universe first seen for one trading date."""

    current = tuple(symbols)
    path = state_root / "daily" / target_date.isoformat() / "target_symbols.json"
    if path.exists():
        payload = _load_json(path)
        frozen = tuple(str(symbol) for symbol in payload.get("symbols", []))
        if frozen and len(frozen) == len(set(frozen)):
            return frozen
        if path.exists():
            raise ValueError(f"{target_date} KIS 대상 체크포인트가 올바르지 않습니다.")
    _atomic_json(
        path,
        {
            "trade_date": target_date.isoformat(),
            "target_count": len(current),
            "symbols": list(current),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return current


def find_incomplete_kis_dates(
    scheduled_date: date,
    symbols: Iterable[str],
    *,
    lookback_days: int = 10,
    state_root: Path = STATE_ROOT,
    engine=None,
) -> tuple[date, ...]:
    """Find recent missing or interrupted sessions without triggering an API.

    A completely empty database is treated as a first run and schedules only
    ``scheduled_date``; historical loading remains an explicit manual job.
    Once data exists, gaps after the older of raw/adjusted maxima are recovered.
    Existing per-date checkpoints also identify partial or interrupted runs.
    """

    targets = tuple(symbols)
    if not targets or lookback_days < 1:
        raise ValueError("복구 대상 종목과 조회 기간이 올바르지 않습니다.")
    window_start = scheduled_date - timedelta(days=lookback_days - 1)
    candidates = _trading_dates(window_start, scheduled_date)
    if not candidates:
        raise ValueError("최근 범위에 KRX 거래일이 없습니다.")

    target_engine = engine or get_engine()
    statement = text(
        """
        SELECT
          (SELECT max(trade_date) FROM prices_daily
           WHERE source='KIS' AND trade_date <= :scheduled_date),
          (SELECT max(trade_date) FROM adjusted_prices_daily
           WHERE source='KIS' AND trade_date <= :scheduled_date)
        """
    )
    with target_engine.connect() as connection:
        max_raw, max_adjusted = connection.execute(
            statement, {"scheduled_date": scheduled_date}
        ).one()

    needed: set[date] = {scheduled_date}
    maxima = [value for value in (max_raw, max_adjusted) if value is not None]
    if maxima:
        baseline = min(maxima) if len(maxima) == 2 else window_start - timedelta(days=1)
        needed.update(day for day in candidates if day > baseline)

    for day in candidates:
        root = state_root / "daily" / day.isoformat()
        completed_path = root / "kis_prices_completed.json"
        failed_path = root / "kis_prices_failed.json"
        if not completed_path.exists() and not failed_path.exists():
            continue
        manifest_path = root / "target_symbols.json"
        requested = (
            set(freeze_daily_symbols(day, targets, state_root=state_root))
            if manifest_path.exists()
            else set(targets)
        )
        completed = _checkpoint_symbols(completed_path)
        failures = _checkpoint_symbols(failed_path)
        if failures or not requested.issubset(completed):
            needed.add(day)
    return tuple(sorted(day for day in needed if day in candidates))


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
    temporary.replace(path)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError):
        value = None
    if not isinstance(value, dict):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        corrupt_path = path.with_name(f"{path.name}.corrupt-{stamp}")
        path.replace(corrupt_path)
        return {}
    return value


def _year_chunks(start_date: date, end_date: date) -> Iterable[tuple[date, date]]:
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(date(cursor.year, 12, 31), end_date)
        yield cursor, chunk_end
        cursor = date(cursor.year + 1, 1, 1)


def _chunk_key(
    symbol: str,
    start_date: date,
    end_date: date,
    include_raw: bool,
    include_adjusted: bool,
) -> str:
    return (
        f"{symbol}:{start_date.isoformat()}:{end_date.isoformat()}:"
        f"raw={include_raw}:adjusted={include_adjusted}"
    )


def backfill_kis_prices(
    start_date: date = BACKFILL_START,
    end_date: date | None = None,
    symbols: Iterable[str] | None = None,
    *,
    client: KisClient | None = None,
    include_raw: bool = True,
    include_adjusted: bool = True,
    resume: bool = True,
    state_root: Path = STATE_ROOT,
    saver: Callable[[list[dict], list[dict]], int] = save_kis_prices,
    capture_latest_raw: dict[str, dict] | None = None,
) -> dict:
    end_date = end_date or date.today()
    if start_date > end_date or not (include_raw or include_adjusted):
        raise ValueError("수집 날짜 또는 원시/수정 선택이 올바르지 않습니다.")
    requested = (
        load_kospi_symbols()
        if symbols is None
        else tuple(str(symbol).strip() for symbol in symbols)
    )
    if not requested:
        raise ValueError("KIS 수집 대상이 0종목입니다.")
    if len(set(requested)) != len(requested):
        raise ValueError("KIS 수집 대상에 중복 종목이 있습니다.")
    for symbol in requested:
        _validate_symbol(symbol)
    own_client = client is None
    api = client or KisClient()
    completed_path = state_root / "kis_prices_completed.json"
    failed_path = state_root / "kis_prices_failed.json"
    completed = _load_json(completed_path)
    failures = _load_json(failed_path)
    result = {
        "completed_symbols": [],
        "skipped_symbols": [],
        "failed_symbols": [],
        "completed_chunks": [],
        "skipped_chunks": [],
        "failed_chunks": [],
        "raw_rows": 0,
        "adjusted_rows": 0,
        "zero_ohlc_rows": 0,
    }
    chunks = [
        (symbol, chunk_start, chunk_end)
        for symbol in requested
        for chunk_start, chunk_end in _year_chunks(start_date, end_date)
    ]
    skipped_by_symbol = {symbol: 0 for symbol in requested}
    chunk_count_by_symbol = {
        symbol: sum(1 for item in chunks if item[0] == symbol)
        for symbol in requested
    }
    try:
        for symbol, chunk_start, chunk_end in chunks:
            key = _chunk_key(
                symbol,
                chunk_start,
                chunk_end,
                include_raw,
                include_adjusted,
            )
            if resume and key in completed and key not in failures:
                result["skipped_chunks"].append(key)
                skipped_by_symbol[symbol] += 1
                continue
            failures[key] = {
                "status": "in_progress",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(failed_path, failures)
            try:
                raw_rows: list[dict] = []
                adjusted_rows: list[dict] = []
                zero_rows = 0
                if include_raw:
                    raw_rows, zeros = fetch_daily_range(
                        api, symbol, chunk_start, chunk_end, adjusted=False
                    )
                    zero_rows += zeros
                if include_adjusted:
                    adjusted_rows, zeros = fetch_daily_range(
                        api, symbol, chunk_start, chunk_end, adjusted=True
                    )
                    zero_rows += zeros
                if include_raw and not raw_rows:
                    raise KisApiError("KIS 원시 기간시세에 저장 가능한 행이 없습니다.")
                if include_adjusted and not adjusted_rows:
                    raise KisApiError("KIS 수정 기간시세에 저장 가능한 행이 없습니다.")
                saver(raw_rows, adjusted_rows)
                if capture_latest_raw is not None and raw_rows:
                    capture_latest_raw[symbol] = raw_rows[-1]
                completed[key] = {
                    "raw_rows": len(raw_rows),
                    "adjusted_rows": len(adjusted_rows),
                    "zero_ohlc_rows": zero_rows,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
                # Completion is durable before removing the write-ahead failure
                # marker.  A crash between these writes causes a safe UPSERT
                # replay instead of silently skipping an uncertain chunk.
                _atomic_json(completed_path, completed)
                failures.pop(key, None)
                _atomic_json(failed_path, failures)
                result["completed_chunks"].append(key)
                result["raw_rows"] += len(raw_rows)
                result["adjusted_rows"] += len(adjusted_rows)
                result["zero_ohlc_rows"] += zero_rows
            except BaseException as exc:
                completed.pop(key, None)
                failures[key] = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": (
                        _safe_exception(exc)
                        if isinstance(exc, Exception)
                        else type(exc).__name__
                    ),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                }
                _atomic_json(completed_path, completed)
                _atomic_json(failed_path, failures)
                result["failed_chunks"].append(key)
                if symbol not in result["failed_symbols"]:
                    result["failed_symbols"].append(symbol)
                if not isinstance(exc, Exception):
                    raise
    finally:
        if own_client:
            api.close()
    for symbol in requested:
        symbol_keys = [
            _chunk_key(
                item_symbol,
                chunk_start,
                chunk_end,
                include_raw,
                include_adjusted,
            )
            for item_symbol, chunk_start, chunk_end in chunks
            if item_symbol == symbol
        ]
        if all(key in completed and key not in failures for key in symbol_keys):
            result["completed_symbols"].append(symbol)
        if skipped_by_symbol[symbol] == chunk_count_by_symbol[symbol]:
            result["skipped_symbols"].append(symbol)
    result["remaining_failures"] = len(failures)
    result["target_count"] = len(requested)
    result["completed_count"] = len(result["completed_symbols"])
    result["skipped_count"] = len(result["skipped_symbols"])
    result["failed_count"] = len(result["failed_symbols"])
    return result


def collect_fundamentals(
    client: KisClient,
    symbols: Iterable[str],
    final_rows: dict[str, dict],
    *,
    saver: Callable[[list[dict]], int] = save_fundamentals,
) -> dict:
    result = {"saved_rows": 0, "failed_symbols": [], "errors": {}}
    for symbol in symbols:
        try:
            final_daily = final_rows.get(symbol)
            if final_daily is None:
                raise ValueError("최신 확정 KIS 일봉이 없습니다.")
            row = normalize_fundamentals(
                symbol, client.current_price(symbol), final_daily
            )
            result["saved_rows"] += saver([row])
        except Exception as exc:
            result["failed_symbols"].append(symbol)
            result["errors"][symbol] = {
                "error_type": type(exc).__name__,
                "error": _safe_exception(exc),
            }
    return result


def refresh_kis_market_data(
    start_date: date,
    end_date: date,
    *,
    symbols: Iterable[str] | None = None,
    symbol_limit: int | None = None,
    full_resync_symbol: str | None = None,
    full_resync_start: date = BACKFILL_START,
) -> dict:
    """Run one frozen KOSPI universe through prices and fundamentals."""
    targets = load_kospi_symbols(symbols=symbols, limit=symbol_limit)
    assert_kis_schema()  # Fail before any external request if 0011 is absent.
    if full_resync_symbol is not None and full_resync_symbol not in targets:
        raise ValueError("전체 재동기화 종목이 이번 실행 대상에 없습니다.")
    scheduled_targets = freeze_daily_symbols(end_date, targets)
    recovery_dates = find_incomplete_kis_dates(
        end_date, targets, state_root=STATE_ROOT
    )
    with KisClient() as client:
        metrics_before = client.request_metrics()
        date_results: dict[str, dict] = {}
        recent = {
            "target_count": len(targets),
            "completed_symbols": [],
            "skipped_symbols": [],
            "failed_symbols": [],
            "completed_chunks": [],
            "skipped_chunks": [],
            "failed_chunks": [],
            "raw_rows": 0,
            "adjusted_rows": 0,
            "zero_ohlc_rows": 0,
            "remaining_failures": 0,
        }
        for target_date in recovery_dates:
            date_targets = freeze_daily_symbols(target_date, targets)
            one = backfill_kis_prices(
                target_date,
                target_date,
                date_targets,
                client=client,
                resume=True,
                state_root=STATE_ROOT / "daily" / target_date.isoformat(),
            )
            date_results[target_date.isoformat()] = one
            for key in (
                "completed_chunks", "skipped_chunks", "failed_chunks"
            ):
                recent[key].extend(one[key])
            for key in ("raw_rows", "adjusted_rows", "zero_ohlc_rows"):
                recent[key] += one[key]
            recent["remaining_failures"] += one["remaining_failures"]
        for key in ("completed_symbols", "skipped_symbols", "failed_symbols"):
            recent[key] = sorted(
                {
                    symbol
                    for result in date_results.values()
                    for symbol in result[key]
                }
            )

        # Completed checkpoints may skip API calls on a rerun.  Reload durable
        # rows so fundamentals use the same frozen current universe.
        final_rows = load_latest_raw_prices(
            scheduled_targets, min(recovery_dates), end_date
        )
        fundamentals = collect_fundamentals(
            client, scheduled_targets, final_rows
        )
        full_resync = None
        if full_resync_symbol:
            full_resync = backfill_kis_prices(
                full_resync_start,
                end_date,
                (full_resync_symbol,),
                client=client,
                include_raw=False,
                include_adjusted=True,
                resume=False,
            )
        metrics_after = client.request_metrics()
    request_metrics = {
        key: metrics_after[key] - metrics_before[key]
        for key in metrics_after
    }
    incomplete_dates = sorted(
        day for day, result in date_results.items() if result["failed_symbols"]
    )
    processed_symbol_dates = sum(
        result["target_count"] for result in date_results.values()
    )
    successful_symbol_dates = sum(
        result["completed_count"] for result in date_results.values()
    )
    skipped_symbol_dates = sum(
        result["skipped_count"] for result in date_results.values()
    )
    failed_symbol_dates = sum(
        result["failed_count"] for result in date_results.values()
    )
    summary = {
        "target_count": len(scheduled_targets),
        "processed_date_count": len(recovery_dates),
        "processed_dates": [day.isoformat() for day in recovery_dates],
        "incomplete_dates": incomplete_dates,
        "processed_symbol_dates": processed_symbol_dates,
        "successful_symbol_dates": successful_symbol_dates,
        "skipped_symbol_dates": skipped_symbol_dates,
        "failed_symbol_dates": failed_symbol_dates,
        "request_metrics": request_metrics,
        "prices": recent,
        "date_results": date_results,
        "fundamentals": fundamentals,
        "full_resync": full_resync,
    }
    _atomic_json(
        STATE_ROOT / "daily" / end_date.isoformat() / "kis_run_summary.json",
        summary,
    )
    return summary
