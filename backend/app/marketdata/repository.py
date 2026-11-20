"""prices_daily / news_articles / 재무 / 시장 지표 조회 (읽기 전용)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class MarketDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _rows(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(text(sql), params).mappings().all()]

    def _row(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        row = self.db.execute(text(sql), params).mappings().first()
        return dict(row) if row else None

    # ─── 시세 (A)
    def recent_prices(self, code: str, limit: int) -> list[dict[str, Any]]:
        """최근 거래일부터 limit개. 반환은 날짜 오름차순."""
        rows = self._rows(
            """
            SELECT trade_date, open, high, low, close, volume,
                   trade_value, market_cap, listed_shares
            FROM prices_daily
            WHERE symbol = :code
            ORDER BY trade_date DESC
            LIMIT :limit
            """,
            {"code": code, "limit": limit},
        )
        return list(reversed(rows))

    def recent_candles(self, code: str, limit: int, *, adjusted: bool) -> list[dict[str, Any]]:
        """차트용 일봉. adjusted=True 면 수정주가(adjusted_prices_daily) OHLC, 그 날 수정값이 없으면 원시값.
        거래량은 수정 테이블에 없어 항상 prices_daily 값. 반환은 날짜 오름차순."""
        if not adjusted:
            return self.recent_prices(code, limit)
        rows = self._rows(
            """
            SELECT p.trade_date,
                   COALESCE(a.open, p.open) AS open, COALESCE(a.high, p.high) AS high,
                   COALESCE(a.low, p.low) AS low, COALESCE(a.close, p.close) AS close,
                   p.volume
            FROM prices_daily p
            LEFT JOIN adjusted_prices_daily a ON a.symbol = p.symbol AND a.trade_date = p.trade_date
            WHERE p.symbol = :code
            ORDER BY p.trade_date DESC
            LIMIT :limit
            """,
            {"code": code, "limit": limit},
        )
        return list(reversed(rows))

    def latest_news(self, limit: int) -> list[dict[str, Any]]:
        # 원문(news_article_bodies)·청크(news_chunks)는 쓰지 않는다.
        return self._rows(
            """
            SELECT a.id, a.title, a.summary, a.url, a.published_at, s.name AS source
            FROM news_articles a
            JOIN news_sources s ON s.id = a.source_id
            ORDER BY a.published_at DESC, a.id DESC
            LIMIT :limit
            """,
            {"limit": limit},
        )

    # ─── 기업 정보 (B)
    def stock(self, code: str) -> dict[str, Any] | None:
        return self._row(
            """
            SELECT btrim(symbol) AS code, name, market::text AS market,
                   description, shares_outstanding
            FROM stocks WHERE symbol = :code
            """,
            {"code": code},
        )

    def latest_snapshot(self, code: str) -> dict[str, Any] | None:
        return self._row(
            """
            SELECT basis_trade_date, per, pbr, eps, bps, w52_high, w52_low,
                   market_cap, listed_shares
            FROM stock_fundamentals_snapshot
            WHERE symbol = :code
            ORDER BY basis_trade_date DESC
            LIMIT 1
            """,
            {"code": code},
        )

    def annual_financials(self, code: str, limit: int) -> list[dict[str, Any]]:
        """연간 재무. 같은 기간에 연결·별도가 함께 있으면 연결을 쓴다. 날짜 오름차순."""
        rows = self._rows(
            """
            SELECT * FROM (
              SELECT DISTINCT ON (f.period_end)
                     f.period_end, f.fs_div, f.revenue, f.operating_income,
                     f.net_income, f.total_equity, m.roe AS metric_roe
              FROM financials f
              LEFT JOIN financial_metrics m
                ON m.symbol = f.symbol AND m.period_end = f.period_end
              WHERE f.symbol = :code AND f.period_type = 'annual'
              ORDER BY f.period_end DESC, (f.fs_div = 'consolidated') DESC
            ) t
            ORDER BY period_end DESC
            LIMIT :limit
            """,
            {"code": code, "limit": limit},
        )
        return list(reversed(rows))

    def latest_metrics(self, code: str) -> dict[str, Any] | None:
        return self._row(
            """
            SELECT period_end, fs_div, debt_ratio, current_ratio, quick_ratio,
                   interest_coverage, reserve_ratio
            FROM financial_metrics
            WHERE symbol = :code
            ORDER BY period_end DESC
            LIMIT 1
            """,
            {"code": code},
        )

    # ─── 시장 개요 (B). 반환은 날짜 오름차순 [{day, value}]
    def index_closes(self, index_code: str, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT trade_date AS day, close AS value FROM market_indices
            WHERE code = :code ORDER BY trade_date DESC LIMIT :limit
            """,
            {"code": index_code, "limit": limit},
        )
        return list(reversed(rows))

    def observations(self, indicator_code: str, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT observation_date AS day, value FROM economic_observations
            WHERE indicator_code = :code AND value IS NOT NULL
            ORDER BY observation_date DESC LIMIT :limit
            """,
            {"code": indicator_code, "limit": limit},
        )
        return list(reversed(rows))

    def commodity_closes(self, product_code: str, limit: int) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT trade_date AS day, close AS value FROM commodity_prices_daily
            WHERE product_code = :code ORDER BY trade_date DESC LIMIT :limit
            """,
            {"code": product_code, "limit": limit},
        )
        return list(reversed(rows))
