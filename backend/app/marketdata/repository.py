"""prices_daily / news_articles 조회."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class MarketDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recent_prices(self, code: str, limit: int) -> list[dict[str, Any]]:
        """최근 거래일부터 limit개. 반환은 날짜 오름차순."""
        rows = self.db.execute(
            text(
                """
                SELECT trade_date, open, high, low, close, volume
                FROM prices_daily
                WHERE symbol = :code
                ORDER BY trade_date DESC
                LIMIT :limit
                """
            ),
            {"code": code, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def latest_news(self, limit: int) -> list[dict[str, Any]]:
        # 원문(news_article_bodies)·청크(news_chunks)는 쓰지 않는다.
        rows = self.db.execute(
            text(
                """
                SELECT a.id, a.title, a.summary, a.url, a.published_at, s.name AS source
                FROM news_articles a
                JOIN news_sources s ON s.id = a.source_id
                ORDER BY a.published_at DESC, a.id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]
