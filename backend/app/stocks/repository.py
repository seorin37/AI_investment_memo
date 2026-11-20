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
                ORDER BY us.position NULLS LAST, us.created_at, s.symbol
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [{**dict(row), "position": index} for index, row in enumerate(rows)]   # 사이드바 자리 (0021, 0부터)

    def stock_order(self, user_id: int, *, lock: bool = False) -> list[str]:
        """내 종목 순서 (지우지 않은 것). lock=True면 순서를 다시 쓰는 동안 동시 변경을 막는다."""
        rows = self.db.execute(
            text(
                f"""
                SELECT btrim(symbol) FROM user_stocks
                WHERE user_id = :user_id AND deleted_at IS NULL
                ORDER BY position NULLS LAST, created_at, symbol
                {"FOR UPDATE" if lock else ""}
                """
            ),
            {"user_id": user_id},
        ).scalars().all()
        return list(rows)

    def write_stock_order(self, user_id: int, codes: list[str]) -> None:
        """내 종목 순서를 0부터 다시 매긴다. codes는 지우지 않은 내 종목 전체."""
        if not codes:
            return
        self.db.execute(
            text(
                """
                UPDATE user_stocks us SET position = o.pos - 1
                FROM unnest(CAST(:codes AS text[])) WITH ORDINALITY AS o(code, pos)
                WHERE us.user_id = :user_id AND btrim(us.symbol) = o.code AND us.deleted_at IS NULL
                  AND us.position IS DISTINCT FROM o.pos - 1
                """
            ),
            {"user_id": user_id, "codes": codes},
        )

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
                INSERT INTO user_stocks (user_id, symbol, status, position)
                VALUES (:user_id, :code, CAST(:status AS stock_status),
                        (SELECT COALESCE(max(position) + 1, 0) FROM user_stocks
                         WHERE user_id = :user_id AND deleted_at IS NULL))
                ON CONFLICT (user_id, symbol) DO UPDATE
                SET status = EXCLUDED.status,
                    position = CASE WHEN user_stocks.deleted_at IS NULL THEN user_stocks.position
                                    ELSE EXCLUDED.position END,     -- 새로·다시 추가하면 맨 뒤 (0021)
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
