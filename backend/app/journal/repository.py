"""journal_entries · journal_entry_stocks SQL.

- 종목: journal_entry_stocks 의 첫 번째(종목 코드 순) 하나. 저장할 때는 그 하나로 바꿔 쓴다.
- kind·status·folder_id·parent_id 는 기본값(NULL·'draft'·NULL·NULL), source_memo_id 는 비워 둔다 (메모 결론과 별개).
- blocks(0020)가 원본, body 는 blocks 로 만든 Markdown.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_SELECT = """
SELECT e.id, e.title, e.body, e.blocks, e.is_pinned, e.created_at, e.updated_at,
       st.symbol AS stock_code, s.name AS stock_name
FROM journal_entries e
LEFT JOIN LATERAL (
  SELECT btrim(js.symbol) AS symbol FROM journal_entry_stocks js
  WHERE js.entry_id = e.id ORDER BY js.symbol LIMIT 1
) st ON true
LEFT JOIN stocks s ON s.symbol = st.symbol
"""


class JournalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, user_id: int, limit: int = 500) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(_SELECT + " WHERE e.user_id = :user_id AND e.deleted_at IS NULL"
                           " ORDER BY e.created_at DESC, e.id DESC LIMIT :limit"),
            {"user_id": user_id, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def get(self, user_id: int, entry_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(_SELECT + " WHERE e.id = :id AND e.user_id = :user_id AND e.deleted_at IS NULL"),
            {"id": entry_id, "user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None

    def stock_exists(self, symbol: str) -> bool:
        return self.db.execute(text("SELECT 1 FROM stocks WHERE symbol = :s"), {"s": symbol}).first() is not None

    def create(self, user_id: int, *, title: str, body: str, blocks: list[dict[str, Any]], pinned: bool = False) -> int:
        return int(self.db.execute(
            text(
                """
                INSERT INTO journal_entries (user_id, title, body, blocks, is_pinned)
                VALUES (:user_id, :title, :body, CAST(:blocks AS jsonb), :pinned)
                RETURNING id
                """
            ),
            {"user_id": user_id, "title": title, "body": body,
             "blocks": json.dumps(blocks, ensure_ascii=False), "pinned": pinned},
        ).scalar_one())

    def update(self, user_id: int, entry_id: int, values: dict[str, Any], *, touch: bool = True) -> bool:
        """values: title·body·blocks·is_pinned 중 바꿀 것.
        touch=True 면 비어 있어도 updated_at 을 새로 찍는다 (종목만 바뀐 경우). 고정만 바꿀 때는 touch=False."""
        sets, params = (["updated_at = now()"] if touch else ["id = id"]), {"id": entry_id, "user_id": user_id}
        if "is_pinned" in values:
            sets.append("is_pinned = :is_pinned")
            params["is_pinned"] = bool(values["is_pinned"])
        if "title" in values:
            sets.append("title = :title")
            params["title"] = values["title"]
        if "body" in values:
            sets.append("body = :body")
            params["body"] = values["body"]
        if "blocks" in values:
            sets.append("blocks = CAST(:blocks AS jsonb)")
            params["blocks"] = json.dumps(values["blocks"], ensure_ascii=False)
        return self.db.execute(
            text(f"UPDATE journal_entries SET {', '.join(sets)} "
                 "WHERE id = :id AND user_id = :user_id AND deleted_at IS NULL RETURNING id"),
            params,
        ).first() is not None

    def set_stock(self, entry_id: int, symbol: str | None) -> None:
        self.db.execute(text("DELETE FROM journal_entry_stocks WHERE entry_id = :id"), {"id": entry_id})
        if symbol:
            self.db.execute(
                text("INSERT INTO journal_entry_stocks (entry_id, symbol) VALUES (:id, :symbol)"),
                {"id": entry_id, "symbol": symbol},
            )

    def soft_delete(self, user_id: int, entry_id: int) -> bool:
        return self.db.execute(
            text(
                """
                UPDATE journal_entries SET deleted_at = now()
                WHERE id = :id AND user_id = :user_id AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"id": entry_id, "user_id": user_id},
        ).first() is not None
