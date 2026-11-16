"""PostgreSQL access for stock master and user-owned stock rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_kospi(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT btrim(symbol) AS code, name, market::text AS market
                FROM stocks
                WHERE market = 'KOSPI'
                  AND (name ILIKE :pattern OR btrim(symbol) ILIKE :pattern)
                ORDER BY
                  CASE
                    WHEN btrim(symbol) = :query THEN 0
                    WHEN name = :query THEN 1
                    WHEN btrim(symbol) ILIKE :prefix THEN 2
                    WHEN name ILIKE :prefix THEN 3
                    ELSE 4
                  END,
                  name, symbol
                LIMIT :limit
                """
            ),
            {
                "query": query,
                "pattern": f"%{query}%",
                "prefix": f"{query}%",
                "limit": limit,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_kospi(self, code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT btrim(symbol) AS code, name, market::text AS market
                FROM stocks
                WHERE symbol = :code AND market = 'KOSPI'
                """
            ),
            {"code": code},
        ).mappings().first()
        return dict(row) if row else None

    def list_user_stocks(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT btrim(s.symbol) AS code,
                       s.name,
                       s.market::text AS market,
                       us.status::text AS status,
                       us.created_at AS added_at,
                       COALESCE((
                         SELECT count(DISTINCT tu.id)
                         FROM memos m
                         JOIN tracking_items ti ON ti.memo_id = m.id
                         JOIN tracking_updates tu ON tu.tracking_item_id = ti.id
                         WHERE m.user_id = us.user_id
                           AND m.symbol = us.symbol
                           AND m.deleted_at IS NULL
                           AND tu.created_at > COALESCE(
                             us.last_checked_at,
                             CAST('-infinity' AS timestamptz)
                           )
                       ), 0)::integer AS unread_updates
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol
                WHERE us.user_id = :user_id
                  AND us.deleted_at IS NULL
                ORDER BY us.created_at, s.symbol
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_user_stock(self, user_id: int, code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT btrim(s.symbol) AS code,
                       s.name,
                       s.market::text AS market,
                       us.status::text AS status,
                       us.created_at AS added_at,
                       COALESCE((
                         SELECT count(DISTINCT tu.id)
                         FROM memos m
                         JOIN tracking_items ti ON ti.memo_id = m.id
                         JOIN tracking_updates tu ON tu.tracking_item_id = ti.id
                         WHERE m.user_id = us.user_id
                           AND m.symbol = us.symbol
                           AND m.deleted_at IS NULL
                           AND tu.created_at > COALESCE(
                             us.last_checked_at,
                             CAST('-infinity' AS timestamptz)
                           )
                       ), 0)::integer AS unread_updates
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol
                WHERE us.user_id = :user_id
                  AND us.symbol = :code
                  AND us.deleted_at IS NULL
                """
            ),
            {"user_id": user_id, "code": code},
        ).mappings().first()
        return dict(row) if row else None

    def upsert_user_stock(
        self, user_id: int, code: str, status: str
    ) -> dict[str, Any]:
        self.db.execute(
            text(
                """
                INSERT INTO user_stocks (user_id, symbol, status)
                VALUES (:user_id, :code, CAST(:status AS stock_status))
                ON CONFLICT (user_id, symbol) DO UPDATE
                SET status = EXCLUDED.status,
                    deleted_at = NULL
                """
            ),
            {"user_id": user_id, "code": code, "status": status},
        )
        return self.get_user_stock(user_id, code)  # type: ignore[return-value]

    def update_status(
        self, user_id: int, code: str, status: str
    ) -> dict[str, Any] | None:
        changed = self.db.execute(
            text(
                """
                UPDATE user_stocks
                SET status = CAST(:status AS stock_status)
                WHERE user_id = :user_id
                  AND symbol = :code
                  AND deleted_at IS NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "code": code, "status": status},
        ).first()
        return self.get_user_stock(user_id, code) if changed else None

    def soft_delete(self, user_id: int, code: str) -> bool:
        changed = self.db.execute(
            text(
                """
                UPDATE user_stocks
                SET deleted_at = now()
                WHERE user_id = :user_id
                  AND symbol = :code
                  AND deleted_at IS NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "code": code},
        ).first()
        return changed is not None
