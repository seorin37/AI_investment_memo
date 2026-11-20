from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class BoardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def owns_stock(self, user_id: int, symbol: str) -> bool:
        return self.db.execute(
            text(
                """
                SELECT 1 FROM user_stocks
                WHERE user_id = :user_id AND symbol = :symbol AND deleted_at IS NULL
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).first() is not None

    # 보드 순서 (2026-11-20, 0019 memos.position): 보드 하나 = 사용자 × 종목. 화면 순서는 왼쪽→오른쪽, 위→아래.
    # 응답의 position은 보드 안 자리(0부터)라 저장값에 빈 번호나 NULL이 있어도 0, 1, 2…로 보인다.
    _BOARD_ORDER = "m.position NULLS LAST, m.created_at, m.id"

    def list_board(self, user_id: int, symbol: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                f"""
                SELECT m.*
                FROM memos m
                WHERE m.user_id = :user_id AND m.symbol = :symbol AND m.deleted_at IS NULL
                ORDER BY {self._BOARD_ORDER}
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).mappings().all()
        return [{**dict(row), "position": index} for index, row in enumerate(rows)]

    def get_owned(self, user_id: int, memo_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                f"""
                SELECT ranked.* FROM (
                  SELECT m.*, (row_number() OVER (ORDER BY {self._BOARD_ORDER}) - 1)::integer AS board_position
                  FROM memos m
                  JOIN memos target ON target.id = :memo_id AND target.user_id = :user_id
                  WHERE m.user_id = target.user_id AND m.symbol = target.symbol AND m.deleted_at IS NULL
                ) ranked
                WHERE ranked.id = :memo_id
                """
            ),
            {"user_id": user_id, "memo_id": memo_id},
        ).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["position"] = result.pop("board_position")
        return result

    def board_order(self, user_id: int, symbol: str, *, lock: bool = False) -> list[dict[str, Any]]:
        """보드 카드 순서 [{id, pinned}]. lock=True면 순서를 다시 쓰는 동안 같은 보드의 동시 변경을 막는다."""
        rows = self.db.execute(
            text(
                f"""
                SELECT m.id, m.is_pinned
                FROM memos m
                WHERE m.user_id = :user_id AND m.symbol = :symbol AND m.deleted_at IS NULL
                ORDER BY {self._BOARD_ORDER}
                {"FOR UPDATE" if lock else ""}
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).all()
        return [{"id": int(memo_id), "pinned": bool(pinned)} for memo_id, pinned in rows]

    def write_order(self, user_id: int, symbol: str, ids: list[int]) -> None:
        """보드 카드 순서를 0부터 다시 매긴다. ids는 그 보드의 살아 있는 카드 전체여야 한다."""
        if not ids:
            return
        self.db.execute(
            text(
                """
                UPDATE memos m SET position = o.pos - 1
                FROM unnest(CAST(:ids AS bigint[])) WITH ORDINALITY AS o(id, pos)
                WHERE m.id = o.id AND m.user_id = :user_id AND m.symbol = :symbol
                  AND m.deleted_at IS NULL AND m.position IS DISTINCT FROM o.pos - 1
                """
            ),
            {"ids": ids, "user_id": user_id, "symbol": symbol},
        )

    def create(
        self,
        *,
        user_id: int,
        symbol: str,
        kind: str,
        title: str,
        content: str,
        color: str | None = None,
        pinned: bool = False,
        ai_linked: bool = False,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                INSERT INTO memos
                  (user_id, symbol, kind, title, content, color, is_pinned,
                   ai_linked, ai_linked_at)
                VALUES
                  (:user_id, :symbol, CAST(:kind AS memo_kind), :title, :content,
                   :color, :pinned, :ai_linked,
                   CASE WHEN :ai_linked THEN now() ELSE NULL END)
                RETURNING *
                """
            ),
            {
                "user_id": user_id,
                "symbol": symbol,
                "kind": kind,
                "title": title,
                "content": content,
                "color": color,
                "pinned": pinned,
                "ai_linked": ai_linked,
            },
        ).mappings().one()
        return dict(row)                                        # 자리는 service가 place_new로 정한다

    def update_base(self, user_id: int, memo_id: int, values: dict[str, Any]) -> bool:
        columns = {
            "title": "title",
            "body": "content",
            "color": "color",
            "pinned": "is_pinned",
        }
        assignments = [f"{columns[key]} = :{key}" for key in values if key in columns]
        if not assignments:
            return self.get_owned(user_id, memo_id) is not None
        assignments.append("updated_at = now()")
        changed = self.db.execute(
            text(
                f"""
                UPDATE memos SET {', '.join(assignments)}
                WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"memo_id": memo_id, "user_id": user_id, **values},
        ).first()
        return changed is not None

    def set_ai_link(self, user_id: int, memo_id: int, enabled: bool) -> bool:
        changed = self.db.execute(
            text(
                """
                UPDATE memos
                SET ai_linked = :enabled,
                    ai_linked_at = CASE WHEN :enabled THEN COALESCE(ai_linked_at, now()) ELSE NULL END,
                    updated_at = now()
                WHERE id = :memo_id AND user_id = :user_id
                  AND kind = 'note' AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"memo_id": memo_id, "user_id": user_id, "enabled": enabled},
        ).first()
        return changed is not None

    def touch(self, user_id: int, memo_id: int) -> bool:
        changed = self.db.execute(
            text(
                """
                UPDATE memos SET updated_at = now()
                WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).first()
        return changed is not None

    def soft_delete(self, user_id: int, memo_id: int) -> bool:
        changed = self.db.execute(
            text(
                """
                UPDATE memos
                SET deleted_at = now(), ai_linked = false, ai_linked_at = NULL, updated_at = now()
                WHERE id = :memo_id AND user_id = :user_id AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"memo_id": memo_id, "user_id": user_id},
        ).first()
        if changed:
            self.db.execute(
                text("UPDATE tracking_items SET status = 'done', updated_at = now() WHERE memo_id = :memo_id"),
                {"memo_id": memo_id},
            )
        return changed is not None

    def tags(self, memo_id: int) -> list[str]:
        return list(
            self.db.execute(
                text(
                    """
                    SELECT t.name FROM memo_tags mt JOIN tags t ON t.id = mt.tag_id
                    WHERE mt.memo_id = :memo_id ORDER BY t.name
                    """
                ),
                {"memo_id": memo_id},
            ).scalars()
        )

    def replace_tags(self, user_id: int, memo_id: int, tags: list[str]) -> None:
        self.db.execute(text("DELETE FROM memo_tags WHERE memo_id = :memo_id"), {"memo_id": memo_id})
        for name in tags:
            tag_id = self.db.execute(
                text(
                    """
                    INSERT INTO tags (user_id, name) VALUES (:user_id, :name)
                    ON CONFLICT (user_id, name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """
                ),
                {"user_id": user_id, "name": name},
            ).scalar_one()
            self.db.execute(
                text("INSERT INTO memo_tags (memo_id, tag_id) VALUES (:memo_id, :tag_id)"),
                {"memo_id": memo_id, "tag_id": tag_id},
            )

    def checklist_items(self, memo_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT id::text AS id, label AS text, is_done AS done
                FROM checklist_items WHERE memo_id = :memo_id
                ORDER BY sort_order NULLS LAST, id
                """
            ),
            {"memo_id": memo_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def replace_checklist(self, memo_id: int, items: list[dict[str, Any]]) -> None:
        self.db.execute(text("DELETE FROM checklist_items WHERE memo_id = :memo_id"), {"memo_id": memo_id})
        for order, item in enumerate(items):
            self.db.execute(
                text(
                    """
                    INSERT INTO checklist_items (memo_id, label, is_done, sort_order)
                    VALUES (:memo_id, :label, :done, :sort_order)
                    """
                ),
                {"memo_id": memo_id, "label": item["text"], "done": item["done"], "sort_order": order},
            )

    def update_checklist_item(
        self, user_id: int, memo_id: int, item_id: int, values: dict[str, Any]
    ) -> bool:
        sets = []
        params = {"user_id": user_id, "memo_id": memo_id, "item_id": item_id}
        if "text" in values:
            sets.append("label = :text")
            params["text"] = values["text"]
        if "done" in values:
            sets.append("is_done = :done")
            params["done"] = values["done"]
        if not sets:
            return False
        changed = self.db.execute(
            text(
                f"""
                UPDATE checklist_items ci SET {', '.join(sets)}
                FROM memos m
                WHERE ci.id = :item_id AND ci.memo_id = :memo_id
                  AND m.id = ci.memo_id AND m.user_id = :user_id
                  AND m.kind = 'checklist' AND m.deleted_at IS NULL
                RETURNING ci.id
                """
            ),
            params,
        ).first()
        if changed:
            self.db.execute(text("UPDATE memos SET updated_at = now() WHERE id = :memo_id"), {"memo_id": memo_id})
        return changed is not None

    def links(self, memo_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT id::text AS id, COALESCE(title, url) AS title, url,
                       CASE WHEN link_type = 'other' OR link_type IS NULL THEN 'etc' ELSE link_type END AS ref_type,
                       CASE WHEN is_file THEN 'file' ELSE 'link' END AS source
                FROM memo_links WHERE memo_id = :memo_id
                ORDER BY sort_order NULLS LAST, id
                """
            ),
            {"memo_id": memo_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def replace_links(self, memo_id: int, links: list[dict[str, Any]]) -> None:
        self.db.execute(text("DELETE FROM memo_links WHERE memo_id = :memo_id"), {"memo_id": memo_id})
        for order, link in enumerate(links):
            self.db.execute(
                text(
                    """
                    INSERT INTO memo_links
                      (memo_id, url, title, sort_order, link_type, is_file)
                    VALUES
                      (:memo_id, :url, :title, :sort_order, :link_type, :is_file)
                    """
                ),
                {
                    "memo_id": memo_id,
                    "url": str(link["url"]),
                    "title": link["title"],
                    "sort_order": order,
                    "link_type": "other" if link["ref_type"] == "etc" else link["ref_type"],
                    "is_file": link["source"] == "file",
                },
            )

    def revision_count(self, memo_id: int) -> int:
        return self.db.execute(
            text("SELECT count(*) FROM memo_revisions WHERE memo_id = :memo_id"),
            {"memo_id": memo_id},
        ).scalar_one()
