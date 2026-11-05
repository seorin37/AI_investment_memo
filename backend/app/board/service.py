"""Business rules for authenticated memo-board management."""

from __future__ import annotations

from typing import Any

from .repository import BoardRepository
from .schemas import ChecklistCreate, MemoCreate, ReferenceCreate


class BoardItemNotFoundError(LookupError):
    pass


class StockBoardNotFoundError(LookupError):
    pass


class InvalidBoardPatchError(ValueError):
    pass


class BoardService:
    _COLORS = {"yellow", "blue", "pink", "green", "purple"}

    def __init__(self, repository: BoardRepository) -> None:
        self.repository = repository

    def list_board(self, user_id: int, symbol: str) -> list[dict[str, Any]]:
        self._require_stock(user_id, symbol)
        return [self._response(row) for row in self.repository.list_board(user_id, symbol)]

    def get(self, user_id: int, memo_id: int) -> dict[str, Any]:
        return self._response(self._require_item(user_id, memo_id))

    def create_memo(self, user_id: int, symbol: str, payload: MemoCreate) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="note",
            title=payload.title,
            content=payload.body,
            color=payload.color,
            pinned=payload.pinned,
            ai_linked=payload.ai_linked,
        )
        self.repository.replace_tags(user_id, int(row["id"]), payload.tags)
        return self._response(row)

    def create_checklist(
        self, user_id: int, symbol: str, payload: ChecklistCreate
    ) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="checklist",
            title=payload.title,
            content="",
        )
        self.repository.replace_checklist(
            int(row["id"]), [item.model_dump(exclude={"id"}) for item in payload.items]
        )
        return self._response(row)

    def create_reference(
        self, user_id: int, symbol: str, payload: ReferenceCreate
    ) -> dict[str, Any]:
        self._require_stock(user_id, symbol)
        row = self.repository.create(
            user_id=user_id,
            symbol=symbol,
            kind="reference",
            title=payload.title,
            content="",
        )
        self.repository.replace_links(
            int(row["id"]), [link.model_dump(exclude={"id"}) for link in payload.links]
        )
        return self._response(row)

    def update(self, user_id: int, memo_id: int, values: dict[str, Any]) -> dict[str, Any]:
        row = self._require_item(user_id, memo_id)
        if "position" in values:
            raise InvalidBoardPatchError(
                "현재 DB 스키마에는 메모 순서 저장 컬럼이 없어 position 변경을 지원하지 않습니다."
            )
        kind = str(row["kind"])
        allowed = {
            "note": {"title", "body", "tags", "color", "pinned"},
            "checklist": {"title", "items"},
            "reference": {"title", "links"},
        }[kind]
        unsupported = set(values) - allowed
        if unsupported:
            raise InvalidBoardPatchError(
                f"{kind} 유형에서 수정할 수 없는 필드입니다: {', '.join(sorted(unsupported))}"
            )

        base = {key: value for key, value in values.items() if key in {"title", "body", "color", "pinned"}}
        if base and not self.repository.update_base(user_id, memo_id, base):
            raise BoardItemNotFoundError(memo_id)
        children_changed = False
        if "tags" in values:
            self.repository.replace_tags(user_id, memo_id, values["tags"])
            children_changed = True
        if "items" in values:
            self.repository.replace_checklist(memo_id, values["items"])
            children_changed = True
        if "links" in values:
            self.repository.replace_links(memo_id, values["links"])
            children_changed = True
        if children_changed:
            self.repository.touch(user_id, memo_id)
        return self.get(user_id, memo_id)

    def update_checklist_item(
        self, user_id: int, memo_id: int, item_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        if not values:
            raise InvalidBoardPatchError("수정할 체크리스트 필드가 없습니다.")
        row = self._require_item(user_id, memo_id)
        if str(row["kind"]) != "checklist":
            raise InvalidBoardPatchError("체크리스트 항목은 체크리스트 메모에서만 수정할 수 있습니다.")
        if not self.repository.update_checklist_item(user_id, memo_id, item_id, values):
            raise BoardItemNotFoundError(item_id)
        return self.get(user_id, memo_id)

    def set_ai_link(self, user_id: int, memo_id: int, enabled: bool) -> dict[str, Any]:
        row = self._require_item(user_id, memo_id)
        if str(row["kind"]) != "note":
            raise InvalidBoardPatchError("일반 메모만 AI 추적 대상으로 설정할 수 있습니다.")
        if not self.repository.set_ai_link(user_id, memo_id, enabled):
            raise BoardItemNotFoundError(memo_id)
        return self.get(user_id, memo_id)

    def delete(self, user_id: int, memo_id: int) -> None:
        self._require_item(user_id, memo_id)
        if not self.repository.soft_delete(user_id, memo_id):
            raise BoardItemNotFoundError(memo_id)

    def _require_stock(self, user_id: int, symbol: str) -> None:
        if not self.repository.owns_stock(user_id, symbol):
            raise StockBoardNotFoundError(symbol)

    def _require_item(self, user_id: int, memo_id: int) -> dict[str, Any]:
        row = self.repository.get_owned(user_id, memo_id)
        if row is None or not self.repository.owns_stock(user_id, str(row["symbol"]).strip()):
            raise BoardItemNotFoundError(memo_id)
        return row

    def _response(self, row: dict[str, Any]) -> dict[str, Any]:
        memo_id = int(row["id"])
        common = {
            "id": str(memo_id),
            "stock_code": str(row["symbol"]).strip(),
            "title": row["title"] or "",
            "position": int(row.get("position") or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        kind = str(row["kind"])
        if kind == "note":
            color = row.get("color")
            return {
                **common,
                "kind": "memo",
                "body": row["content"],
                "tags": self.repository.tags(memo_id),
                "color": color if color in self._COLORS else "yellow",
                "pinned": bool(row.get("is_pinned")),
                "ai_linked": bool(row.get("ai_linked")),
                "ai_linked_at": row.get("ai_linked_at"),
                "price_conditions": [],
                "unread_updates": 0,
            }
        if kind == "checklist":
            return {**common, "kind": "checklist", "items": self.repository.checklist_items(memo_id)}
        if kind == "reference":
            return {**common, "kind": "reference", "links": self.repository.links(memo_id)}
        raise InvalidBoardPatchError(f"지원하지 않는 메모 유형입니다: {kind}")
