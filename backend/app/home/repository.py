"""홈 위젯 SQL. 대상은 지금 보유·관심 중인 종목(user_stocks.deleted_at IS NULL)의 살아 있는 메모."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_ACTIVE_STOCK_JOIN = """
JOIN user_stocks us ON us.user_id = m.user_id AND us.symbol = m.symbol AND us.deleted_at IS NULL
JOIN stocks s ON s.symbol = m.symbol
"""


class HomeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── 체크리스트
    def checklist_items(self, user_id: int) -> list[dict[str, Any]]:
        """고정(테이프) 체크리스트 먼저, 그다음 종목 추가 순 → 보드 순서 → 항목 순서."""
        rows = self.db.execute(
            text(
                f"""
                SELECT ci.id, ci.label, ci.is_done, m.id AS checklist_id, m.is_pinned,
                       btrim(m.symbol) AS stock_code, s.name AS stock_name
                FROM checklist_items ci
                JOIN memos m ON m.id = ci.memo_id
                {_ACTIVE_STOCK_JOIN}
                WHERE m.user_id = :user_id AND m.kind = 'checklist' AND m.deleted_at IS NULL
                ORDER BY m.is_pinned DESC, us.created_at, m.symbol,
                         m.position NULLS LAST, m.created_at, m.id, ci.sort_order NULLS LAST, ci.id
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def first_checklist(self, user_id: int, symbol: str) -> int | None:
        """이 종목 보드에서 새 항목을 붙일 체크리스트 (고정된 것 → 보드 앞쪽)."""
        return self.db.execute(
            text(
                """
                SELECT m.id FROM memos m
                WHERE m.user_id = :user_id AND m.symbol = :symbol
                  AND m.kind = 'checklist' AND m.deleted_at IS NULL
                ORDER BY m.is_pinned DESC, m.position NULLS LAST, m.created_at, m.id
                LIMIT 1
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).scalar()

    def append_checklist_item(self, checklist_id: int, label: str) -> int:
        item_id = self.db.execute(
            text(
                """
                INSERT INTO checklist_items (memo_id, label, is_done, sort_order)
                VALUES (:memo_id, :label, false,
                        (SELECT COALESCE(max(sort_order) + 1, 0) FROM checklist_items WHERE memo_id = :memo_id))
                RETURNING id
                """
            ),
            {"memo_id": checklist_id, "label": label},
        ).scalar_one()
        self.db.execute(text("UPDATE memos SET updated_at = now() WHERE id = :memo_id"), {"memo_id": checklist_id})
        return int(item_id)

    # ─── 가격 조건
    def price_condition_memos(self, user_id: int) -> list[dict[str, Any]]:
        """추적 중(active·paused) 항목이 있는 일반 메모 + 최근 종가. 가격 항목인지는 service 가 TrackingRepository 로 거른다."""
        rows = self.db.execute(
            text(
                f"""
                SELECT m.id, m.title, m.ai_linked, btrim(m.symbol) AS stock_code, s.name AS stock_name,
                       (SELECT p.close FROM prices_daily p WHERE p.symbol = m.symbol
                        ORDER BY p.trade_date DESC LIMIT 1) AS current_price
                FROM memos m
                {_ACTIVE_STOCK_JOIN}
                WHERE m.user_id = :user_id AND m.kind = 'note' AND m.deleted_at IS NULL
                  AND EXISTS (SELECT 1 FROM tracking_items ti
                              WHERE ti.memo_id = m.id AND ti.status::text IN ('active', 'paused'))
                ORDER BY us.created_at, m.symbol, m.position NULLS LAST, m.created_at, m.id
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def owned_note(self, user_id: int, memo_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT id, ai_linked FROM memos
                WHERE id = :memo_id AND user_id = :user_id AND kind = 'note' AND deleted_at IS NULL
                """
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None

    def set_item_status(self, memo_id: int, item_id: int, status: str) -> bool:
        return self.db.execute(
            text(
                """
                UPDATE tracking_items SET status = CAST(:status AS tracking_status), updated_at = now()
                WHERE id = :item_id AND memo_id = :memo_id AND status::text IN ('active', 'paused')
                RETURNING id
                """
            ),
            {"item_id": item_id, "memo_id": memo_id, "status": status},
        ).first() is not None
