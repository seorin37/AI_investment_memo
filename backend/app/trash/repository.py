"""휴지통 SQL. 메모는 memos.deleted_at, 종목은 user_stocks.deleted_at 으로 소프트 삭제돼 있다."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class TrashRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def deleted_memos(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT m.id, m.kind::text AS kind, m.title, left(m.content, 200) AS content,
                       btrim(m.symbol) AS symbol, s.name AS stock_name, m.deleted_at
                FROM memos m
                JOIN stocks s ON s.symbol = m.symbol
                WHERE m.user_id = :user_id AND m.deleted_at IS NOT NULL
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def deleted_stocks(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT btrim(us.symbol) AS symbol, s.name AS stock_name, us.deleted_at
                FROM user_stocks us
                JOIN stocks s ON s.symbol = us.symbol
                WHERE us.user_id = :user_id AND us.deleted_at IS NOT NULL
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def restore_memo(self, user_id: int, memo_id: int) -> str | None:
        """복원한 메모의 종목 코드. 종목이 빠져 있으면 보드에 보이도록 종목도 되살린다."""
        row = self.db.execute(
            text(
                """
                UPDATE memos SET deleted_at = NULL, updated_at = now()
                WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NOT NULL
                RETURNING symbol
                """
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).first()
        if not row:
            return None
        self.db.execute(
            text(
                """
                INSERT INTO user_stocks (user_id, symbol) VALUES (:user_id, :symbol)
                ON CONFLICT (user_id, symbol) DO UPDATE SET deleted_at = NULL
                WHERE user_stocks.deleted_at IS NOT NULL
                """
            ),
            {"user_id": user_id, "symbol": row[0]},
        )
        return str(row[0]).strip()

    def restore_stock(self, user_id: int, symbol: str) -> bool:
        return self.db.execute(
            text(
                """
                UPDATE user_stocks SET deleted_at = NULL
                WHERE user_id = :user_id AND symbol = :symbol AND deleted_at IS NOT NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).first() is not None

    def deleted_memo_exists(self, user_id: int, memo_id: int) -> bool:
        return self.db.execute(
            text(
                "SELECT 1 FROM memos WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NOT NULL"
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).first() is not None

    def memo_has_usage_events(self, memo_id: int) -> bool:
        # tracking_usage_events → tracking_items 는 ON DELETE NO ACTION 이라 사용 기록이 있으면 지울 수 없다.
        return self.db.execute(
            text(
                """
                SELECT 1 FROM tracking_usage_events e
                JOIN tracking_items t ON t.id = e.tracking_item_id
                WHERE t.memo_id = :memo_id
                LIMIT 1
                """
            ),
            {"memo_id": memo_id},
        ).first() is not None

    def purge_memo(self, user_id: int, memo_id: int) -> bool:
        # 태그·체크리스트·링크·버전·추적 항목은 FK ON DELETE CASCADE 로 함께 지워진다.
        return self.db.execute(
            text(
                """
                DELETE FROM memos
                WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NOT NULL
                RETURNING id
                """
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).first() is not None

    def purge_stock(self, user_id: int, symbol: str) -> bool:
        return self.db.execute(
            text(
                """
                DELETE FROM user_stocks
                WHERE user_id = :user_id AND symbol = :symbol AND deleted_at IS NOT NULL
                RETURNING symbol
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).first() is not None
