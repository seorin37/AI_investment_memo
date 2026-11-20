"""휴지통 규칙. 응답은 frontend TrashItem {id, kind, title, context, deleted_at}."""

from __future__ import annotations

import re
from typing import Any

from .repository import TrashRepository

_ID = re.compile(r"^(memo|journal)-(\d{1,18})$|^(stock)-([0-9A-Z]{6})$")

_KIND = {"note": "memo", "checklist": "checklist", "reference": "reference"}
_KIND_LABEL = {"memo": "메모", "checklist": "체크리스트", "reference": "참고자료"}


class TrashItemNotFoundError(LookupError):
    pass


class TrashPurgeBlockedError(RuntimeError):
    pass


def parse_id(trash_id: str) -> tuple[str, str]:
    match = _ID.match(trash_id)
    if not match:
        raise TrashItemNotFoundError(trash_id)
    if match.group(1):
        return match.group(1), match.group(2)
    return "stock", match.group(4)


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _memo_title(row: dict[str, Any], kind: str) -> str:
    title = (row.get("title") or "").strip()
    if title:
        return title
    first_line = next((line.strip() for line in (row.get("content") or "").splitlines() if line.strip()), "")
    return first_line[:40] or f"제목 없는 {_KIND_LABEL[kind]}"


class TrashService:
    def __init__(self, repo: TrashRepository) -> None:
        self.repo = repo

    def list(self, user_id: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in self.repo.deleted_memos(user_id):
            kind = _KIND.get(row["kind"])
            if kind is None:
                continue
            items.append(
                {
                    "id": f"memo-{row['id']}",
                    "kind": kind,
                    "title": _memo_title(row, kind),
                    "context": f"{row['stock_name']} / {_KIND_LABEL[kind]}",
                    "deleted_at": row["deleted_at"],
                }
            )
        for row in self.repo.deleted_stocks(user_id):
            items.append(
                {
                    "id": f"stock-{row['symbol']}",
                    "kind": "stock",
                    "title": row["stock_name"],
                    "context": "종목",
                    "deleted_at": row["deleted_at"],
                }
            )
        for row in self.repo.deleted_journals(user_id):          # mock deleteJournal 과 같은 제목·설명
            items.append(
                {
                    "id": f"journal-{row['id']}",
                    "kind": "journal",
                    "title": (row.get("title") or "").strip() or "제목 없는 기록",
                    "context": "투자 기록",
                    "deleted_at": row["deleted_at"],
                }
            )
        items.sort(key=lambda item: item["deleted_at"], reverse=True)
        return [{**item, "deleted_at": _iso(item["deleted_at"])} for item in items]

    def restore(self, user_id: int, trash_id: str) -> None:
        kind, key = parse_id(trash_id)
        if kind == "memo":
            ok = self.repo.restore_memo(user_id, int(key)) is not None
        elif kind == "journal":
            ok = self.repo.restore_journal(user_id, int(key))
        else:
            ok = self.repo.restore_stock(user_id, key)
        if not ok:
            raise TrashItemNotFoundError(trash_id)

    def purge(self, user_id: int, trash_id: str) -> None:
        kind, key = parse_id(trash_id)
        if kind == "stock":
            if not self.repo.purge_stock(user_id, key):
                raise TrashItemNotFoundError(trash_id)
            return
        if kind == "journal":
            if not self.repo.purge_journal(user_id, int(key)):
                raise TrashItemNotFoundError(trash_id)
            return
        memo_id = int(key)
        if not self.repo.deleted_memo_exists(user_id, memo_id):
            raise TrashItemNotFoundError(trash_id)
        if self.repo.memo_has_usage_events(memo_id):
            raise TrashPurgeBlockedError(trash_id)
        if not self.repo.purge_memo(user_id, memo_id):
            raise TrashItemNotFoundError(trash_id)
