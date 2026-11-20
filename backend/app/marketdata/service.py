"""DB 행 → 프론트 Quote / Candle / NewsHeadline / StockProfile / Financials / MarketOverview 모양."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .repository import MarketDataRepository

KST = ZoneInfo("Asia/Seoul")
MARKET_CLOSE = time(15, 30)

# mock/index.ts getCandles 와 같은 개수
RANGE_SIZES = {"1W": 5, "1M": 22, "3M": 64, "1Y": 250}
SPARK_SIZE = 24
YEAR_DAYS = 250
ANNUAL_YEARS = 7

# 시장 개요 지수 그래프. 장중 데이터가 없어 1D 는 전일·최근 종가 두 점이다.
INDEX_SERIES_SIZES = {"1D": 2, "1W": 5, "1M": 22, "1Y": 250}

# (key, label, flag, 읽을 곳, 코드)
INDICES = [
    ("KOSPI", "코스피", "kr", "index", "KOSPI"),
    ("KOSDAQ", "코스닥", "kr", "index", "KOSDAQ"),
    ("USDKRW", "원/달러", "us", "observation", "USD_KRW"),
]
# (key, label, unit, 읽을 곳, 코드)
MACROS = [
    ("BASE_RATE", "기준금리", "%", "observation", "KR_POLICY_RATE"),
    ("KR3Y", "국고채 3년", "%", "observation", "KR_GOV_3Y"),
    ("US10Y", "미 국채 10년", "%", "observation", "US_TREASURY_10Y"),
    ("GOLD", "금", "원/g", "commodity", "04020000"),           # KRX 금 99.99K, 1g 원화 가격
    ("WTI", "WTI 유가", "$", "observation", "WTI_SPOT"),
]

DEFAULT_OVERVIEW_TEXT = "기업 개요를 준비 중이에요."


class PriceDataNotFoundError(LookupError):
    pass


class StockNotFoundError(LookupError):
    pass


class FinancialsNotFoundError(LookupError):
    pass


def num(value: Any) -> int | float | None:
    """numeric 은 정수면 int, 아니면 float 로."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _round(value: Any, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _ratio(part: Any, whole: Any) -> float | None:
    if part is None or not whole:
        return None
    return round(float(Decimal(part) / Decimal(whole) * 100), 1)


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _close_time(day: date) -> str:
    return datetime.combine(day, MARKET_CLOSE, tzinfo=KST).isoformat()


def candle(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": row["trade_date"].isoformat(),
        "open": num(row["open"]),
        "high": num(row["high"]),
        "low": num(row["low"]),
        "close": num(row["close"]),
        "volume": int(row["volume"]),
    }


class MarketDataService:
    def __init__(self, repo: MarketDataRepository) -> None:
        self.repo = repo

    # ─── 시세 (A)
    def quote(self, code: str) -> dict[str, Any]:
        rows = self.repo.recent_prices(code, SPARK_SIZE)
        if not rows:
            raise PriceDataNotFoundError(code)
        last = rows[-1]
        price = Decimal(last["close"])
        prev = Decimal(rows[-2]["close"]) if len(rows) >= 2 else price
        change = price - prev
        change_pct = float(round(change / prev * 100, 2)) if prev else 0.0
        return {
            "code": code,
            "price": num(price),
            "change": num(change),
            "change_pct": change_pct,
            "as_of": _close_time(last["trade_date"]),
            "spark": [num(row["close"]) for row in rows],
        }

    def candles(self, code: str, range_: str, adjusted: bool = True) -> list[dict[str, Any]]:
        """차트는 기본이 수정주가(분할·병합으로 끊기지 않게). 현재가·전일비(quote·profile)는 원시 주가."""
        rows = self.repo.recent_candles(code, RANGE_SIZES[range_], adjusted=adjusted)
        if not rows:
            raise PriceDataNotFoundError(code)
        return [candle(row) for row in rows]

    def headlines(self, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                # 프론트 NewsHeadline 에는 없는 추가 필드(화면은 무시해도 됨)
                "summary": row["summary"],
                "source": row["source"],
                "url": row["url"],
                "published_at": _iso(row["published_at"]),
            }
            for row in self.repo.latest_news(limit)
        ]

    # ─── 기업 정보 (B)
    def profile(self, code: str) -> dict[str, Any]:
        stock = self.repo.stock(code)
        if not stock:
            raise StockNotFoundError(code)
        prices = self.repo.recent_prices(code, YEAR_DAYS)
        if not prices:
            raise PriceDataNotFoundError(code)
        snap = self.repo.latest_snapshot(code) or {}
        last = prices[-1]
        prev = prices[-2] if len(prices) >= 2 else last
        close = Decimal(last["close"])
        shares = snap.get("listed_shares") or last.get("listed_shares") or stock.get("shares_outstanding")
        market_cap = (
            snap.get("market_cap")
            or last.get("market_cap")
            or (close * shares if shares else None)
        )
        trading_value = last.get("trade_value") or close * int(last["volume"])
        week52_low = snap.get("w52_low") or min(Decimal(p["low"]) for p in prices)
        week52_high = snap.get("w52_high") or max(Decimal(p["high"]) for p in prices)
        return {
            "code": stock["code"],
            "name": stock["name"],
            "market": stock["market"],
            "overview": (stock.get("description") or "").strip() or DEFAULT_OVERVIEW_TEXT,
            "prev_close": num(prev["close"]),
            "open": num(last["open"]),
            "high": num(last["high"]),
            "low": num(last["low"]),
            "volume": int(last["volume"]),
            "trading_value": num(Decimal(trading_value).quantize(Decimal(1))),
            "per": _round(snap.get("per"), 2),
            "pbr": _round(snap.get("pbr"), 2),
            "eps": num(snap.get("eps")),
            "bps": num(snap.get("bps")),
            "market_cap": num(Decimal(market_cap).quantize(Decimal(1))) if market_cap is not None else None,
            "shares_outstanding": int(shares) if shares else None,
            "week52_low": num(week52_low),
            "week52_high": num(week52_high),
        }

    def financials(self, code: str) -> dict[str, Any]:
        if not self.repo.stock(code):
            raise StockNotFoundError(code)
        annual_rows = self.repo.annual_financials(code, ANNUAL_YEARS)
        metrics = self.repo.latest_metrics(code)
        if not annual_rows and not metrics:
            raise FinancialsNotFoundError(code)
        annual = [
            {
                "period": row["period_end"].strftime("%Y-%m"),
                "revenue": num(row["revenue"]),
                "operating_income": num(row["operating_income"]),
                "net_income": num(row["net_income"]),
                # financial_metrics 의 이익률은 분기 단독 값이라 연간 표는 연간 합계로 다시 계산한다.
                "operating_margin": _ratio(row["operating_income"], row["revenue"]),
                "net_margin": _ratio(row["net_income"], row["revenue"]),
                # ROE 는 metrics(연말 TTM = 연간) 값을 쓰고, 없으면 순이익/자본총계
                "roe": _round(row["metric_roe"], 1)
                if row.get("metric_roe") is not None
                else _ratio(row["net_income"], row["total_equity"]),
            }
            for row in annual_rows
        ]
        basis_row = metrics or annual_rows[-1]
        basis_end: date = basis_row["period_end"]
        fs_label = "별도재무제표" if basis_row.get("fs_div") == "separate" else "연결재무제표"
        stability = {
            "as_of": basis_end.strftime("%Y-%m"),
            "debt_ratio": _round((metrics or {}).get("debt_ratio"), 1),
            "current_ratio": _round((metrics or {}).get("current_ratio"), 1),
            "quick_ratio": _round((metrics or {}).get("quick_ratio"), 1),
            "interest_coverage": _round((metrics or {}).get("interest_coverage"), 1),
            "reserve_ratio": _round((metrics or {}).get("reserve_ratio"), 1),
        }
        return {
            "code": code,
            "basis": f"{basis_end.year}년 {basis_end.month:02d}월 기준 · {fs_label}",
            "annual": annual,
            "stability": stability,
        }

    # ─── 시장 개요 (B)
    def _series(self, source: str, code: str, limit: int) -> list[dict[str, Any]]:
        if source == "index":
            return self.repo.index_closes(code, limit)
        if source == "commodity":
            return self.repo.commodity_closes(code, limit)
        return self.repo.observations(code, limit)

    def overview(self) -> dict[str, Any]:
        longest = max(INDEX_SERIES_SIZES.values())
        latest_days: list[date] = []
        indices = []
        for key, label, flag, source, code in INDICES:
            rows = self._series(source, code, longest)
            if not rows:
                continue
            values = [Decimal(r["value"]) for r in rows]
            last = values[-1]
            prev = values[-2] if len(values) >= 2 else last
            change = last - prev
            latest_days.append(rows[-1]["day"])
            indices.append(
                {
                    "key": key,
                    "label": label,
                    "flag": flag,
                    "value": float(round(last, 2)),
                    "change": float(round(change, 2)),
                    "change_pct": float(round(change / prev * 100, 2)) if prev else 0.0,
                    "series": {
                        name: [float(round(v, 2)) for v in values[-size:]]
                        for name, size in INDEX_SERIES_SIZES.items()
                    },
                }
            )
        macro = []
        for key, label, unit, source, code in MACROS:
            rows = self._series(source, code, 2)
            if not rows:
                continue
            last = Decimal(rows[-1]["value"])
            prev = Decimal(rows[-2]["value"]) if len(rows) >= 2 else last
            # 화면(MarketWidgets)과 mock 의 약속: 단위가 % 인 지표는 %p 차이, 그 밖(원/g·$)은 등락률(%)
            if unit == "%":
                change = float(round(last - prev, 2))
            else:
                change = float(round((last - prev) / prev * 100, 2)) if prev else 0.0
            macro.append(
                {
                    "key": key,
                    "label": label,
                    "value": float(round(last, 2)),
                    "unit": unit,
                    "change": change,
                }
            )
        as_of = _close_time(max(latest_days)) if latest_days else datetime.now(KST).isoformat()
        return {"indices": indices, "macro": macro, "as_of": as_of}
