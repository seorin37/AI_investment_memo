"""홈 위젯 응답: HomeChecklistItem, PriceConditionRow (frontend/src/types/models.ts)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.board.repository import BoardRepository
from app.board.schemas import ChecklistCreate
from app.board.service import BoardService
from app.board.tracking import TrackingRepository

from .repository import HomeRepository

DEFAULT_CHECKLIST_TITLE = "체크리스트"


class StockNotOwnedError(LookupError):
    pass


class PriceConditionNotFoundError(LookupError):
    pass


class AiLinkOffError(ValueError):
    pass


def _price(value: Any) -> int | float | None:
    if value is None:
        return None
    number = Decimal(value)
    return int(number) if number == number.to_integral_value() else float(number)


class HomeService:
    def __init__(self, repo: HomeRepository, tracking: TrackingRepository | None = None,
                 board: BoardService | None = None) -> None:
        self.repo = repo
        self.tracking = tracking or TrackingRepository(repo.db)
        self._board = board

    @property
    def board(self) -> BoardService:
        if self._board is None:
            self._board = BoardService(BoardRepository(self.repo.db), tracking=self.tracking, llm_factory=lambda: None)
        return self._board

    # ─── 체크리스트
    @staticmethod
    def _checklist_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "checklist_id": str(row["checklist_id"]),
            "text": row["label"],
            "done": bool(row["is_done"]),
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"],
        }

    def list_checklist(self, user_id: int) -> list[dict[str, Any]]:
        return [self._checklist_item(row) for row in self.repo.checklist_items(user_id)]

    def add_checklist_item(self, user_id: int, stock_code: str, text: str) -> dict[str, Any]:
        """그 종목 보드의 체크리스트(고정된 것 → 앞쪽)에 항목을 붙인다. 체크리스트가 없으면 하나 만든다 (mock 과 같음)."""
        if not self.board.repository.owns_stock(user_id, stock_code):
            raise StockNotOwnedError(stock_code)
        checklist_id = self.repo.first_checklist(user_id, stock_code)
        if checklist_id is None:
            created = self.board.create_checklist(
                user_id, stock_code, ChecklistCreate(title=DEFAULT_CHECKLIST_TITLE, items=[])
            )
            checklist_id = int(created["id"])
        item_id = self.repo.append_checklist_item(int(checklist_id), text)
        return {
            "id": str(item_id),
            "checklist_id": str(checklist_id),
            "text": text,
            "done": False,
            "stock_code": stock_code,
            "stock_name": self.tracking.stock_name(stock_code),
        }

    # ─── 가격 조건
    def list_price_conditions(self, user_id: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for memo in self.repo.price_condition_memos(user_id):
            for condition in self.tracking.price_conditions(int(memo["id"])):
                out.append(
                    {
                        "memo_id": str(memo["id"]),
                        "memo_title": memo["title"] or "",
                        "stock_code": memo["stock_code"],
                        "stock_name": memo["stock_name"],
                        "condition": condition,
                        "current_price": _price(memo["current_price"]),
                    }
                )
        return out

    def set_price_tracking(self, user_id: int, memo_id: int, condition_id: int, tracking: bool) -> None:
        """조건 하나의 추적 켜기/끄기 = tracking_items active ↔ paused. AI 연결이 꺼진 메모는 켤 수 없다."""
        memo = self.repo.owned_note(user_id, memo_id)
        if memo is None:
            raise PriceConditionNotFoundError(memo_id)
        if str(condition_id) not in {c["id"] for c in self.tracking.price_conditions(memo_id)}:
            raise PriceConditionNotFoundError(condition_id)
        if tracking and not memo["ai_linked"]:
            raise AiLinkOffError(memo_id)
        if not self.repo.set_item_status(memo_id, condition_id, "active" if tracking else "paused"):
            raise PriceConditionNotFoundError(condition_id)
