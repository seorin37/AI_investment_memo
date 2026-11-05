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

    def list_board(self, user_id: int, symbol: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT m.*, (row_number() OVER (ORDER BY m.created_at, m.id) - 1)::integer AS position
                FROM memos m
                WHERE m.user_id = :user_id AND m.symbol = :symbol AND m.deleted_at IS NULL
                ORDER BY m.created_at, m.id
                """
            ),
            {"user_id": user_id, "symbol": symbol},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_owned(self, user_id: int, memo_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT m.*,
                       (SELECT count(*)::integer FROM memos before
                        WHERE before.user_id = m.user_id
                          AND before.symbol = m.symbol
                          AND before.deleted_at IS NULL
                          AND (before.created_at, before.id) < (m.created_at, m.id)) AS position
                FROM memos m
                WHERE m.id = :memo_id AND m.user_id = :user_id AND m.deleted_at IS NULL
                """
            ),
            {"user_id": user_id, "memo_id": memo_id},
        ).mappings().first()
        return dict(row) if row else None

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
        result = dict(row)
        result["position"] = self._last_position(user_id, symbol)
        return result

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

    def _last_position(self, user_id: int, symbol: str) -> int:
        return max(
            0,
            self.db.execute(
                text(
                    """
                    SELECT count(*) - 1 FROM memos
                    WHERE user_id = :user_id AND symbol = :symbol AND deleted_at IS NULL
                    """
                ),
                {"user_id": user_id, "symbol": symbol},
            ).scalar_one(),
        )
