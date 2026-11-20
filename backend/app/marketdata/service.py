"""DB 행 → 프론트 Quote / Candle / NewsHeadline 모양."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .repository import MarketDataRepository

KST = ZoneInfo("Asia/Seoul")
MARKET_CLOSE = time(15, 30)

# mock/index.ts getCandles 와 같은 개수
RANGE_SIZES = {"1W": 5, "1M": 22, "3M": 64, "1Y": 250}
SPARK_SIZE = 24


class PriceDataNotFoundError(LookupError):
    pass


def num(value: Any) -> int | float | None:
    """numeric 은 정수면 int, 아니면 float 로."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


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

    def quote(self, code: str) -> dict[str, Any]:
        rows = self.repo.recent_prices(code, SPARK_SIZE)
        if not rows:
            raise PriceDataNotFoundError(code)
        last = rows[-1]
        price = Decimal(last["close"])
        prev = Decimal(rows[-2]["close"]) if len(rows) >= 2 else price
        change = price - prev
        change_pct = float(round(change / prev * 100, 2)) if prev else 0.0
        as_of = datetime.combine(last["trade_date"], MARKET_CLOSE, tzinfo=KST)
        return {
            "code": code,
            "price": num(price),
            "change": num(change),
            "change_pct": change_pct,
            "as_of": as_of.isoformat(),
            "spark": [num(row["close"]) for row in rows],
        }

    def candles(self, code: str, range_: str) -> list[dict[str, Any]]:
        rows = self.repo.recent_prices(code, RANGE_SIZES[range_])
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
