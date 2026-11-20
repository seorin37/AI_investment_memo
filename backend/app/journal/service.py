"""투자 기록 → 프론트 JournalEntry {id, title, stock_code, stock_name, blocks, created_at, updated_at}.

frontend/src/api/mock/index.ts 의 listJournal·createJournal·updateJournal·deleteJournal 과 같은 동작:
- 목록은 만든 순 최신부터, 삭제는 휴지통으로 (journal_entries.deleted_at, /trash 의 kind='journal').
"""

from __future__ import annotations

from typing import Any

from .markdown import blocks_to_markdown
from .repository import JournalRepository
from .schemas import JournalCreate, JournalPatch


class JournalNotFoundError(LookupError):
    pass


class JournalStockNotFoundError(LookupError):
    pass


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _blocks(row: dict[str, Any]) -> list[dict[str, Any]]:
    """blocks 가 원본. 0020 이전에 body 만 있던 행은 문단 하나로 보여 준다."""
    if isinstance(row.get("blocks"), list):
        return row["blocks"]
    body = row.get("body") or ""
    return [{"id": f"b{row['id']}", "type": "paragraph", "text": body}] if body else []


def entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": row.get("title") or "",
        "stock_code": row.get("stock_code"),
        "stock_name": row.get("stock_name") if row.get("stock_code") else None,
        "blocks": _blocks(row),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _dump_blocks(blocks) -> list[dict[str, Any]]:
    return [b.model_dump(exclude_none=True) for b in blocks]


class JournalService:
    def __init__(self, repo: JournalRepository) -> None:
        self.repo = repo

    def list(self, user_id: int) -> list[dict[str, Any]]:
        return [entry(r) for r in self.repo.list(user_id)]

    def _check_stock(self, symbol: str | None) -> None:
        if symbol and not self.repo.stock_exists(symbol):
            raise JournalStockNotFoundError(symbol)

    def create(self, user_id: int, payload: JournalCreate) -> dict[str, Any]:
        self._check_stock(payload.stock_code)
        blocks = _dump_blocks(payload.blocks)
        entry_id = self.repo.create(user_id, title=payload.title.strip(), body=blocks_to_markdown(blocks), blocks=blocks)
        self.repo.set_stock(entry_id, payload.stock_code)
        return self._get(user_id, entry_id)

    def update(self, user_id: int, entry_id: int, patch: JournalPatch) -> dict[str, Any]:
        if self.repo.get(user_id, entry_id) is None:
            raise JournalNotFoundError(entry_id)
        fields = patch.model_fields_set
        values: dict[str, Any] = {}
        if "title" in fields and patch.title is not None:
            values["title"] = patch.title.strip()
        if "blocks" in fields and patch.blocks is not None:
            blocks = _dump_blocks(patch.blocks)
            values["blocks"] = blocks
            values["body"] = blocks_to_markdown(blocks)
        if "stock_code" in fields:                              # null 이면 종목 연결 해제
            self._check_stock(patch.stock_code)
        if not self.repo.update(user_id, entry_id, values):
            raise JournalNotFoundError(entry_id)
        if "stock_code" in fields:
            self.repo.set_stock(entry_id, patch.stock_code)
        return self._get(user_id, entry_id)

    def delete(self, user_id: int, entry_id: int) -> None:
        if not self.repo.soft_delete(user_id, entry_id):
            raise JournalNotFoundError(entry_id)

    def _get(self, user_id: int, entry_id: int) -> dict[str, Any]:
        row = self.repo.get(user_id, entry_id)
        if row is None:
            raise JournalNotFoundError(entry_id)
        return entry(row)
