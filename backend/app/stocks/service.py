"""Business rules for authenticated stock management."""

from __future__ import annotations

from .repository import StockRepository


class StockNotFoundError(LookupError):
    pass


class UserStockNotFoundError(LookupError):
    pass


class UnsupportedStockTagsError(ValueError):
    pass


class StockService:
    def __init__(self, repository: StockRepository) -> None:
        self.repository = repository

    def search(self, query: str) -> list[dict]:
        cleaned = query.strip()
        if not cleaned:
            return []
        return self.repository.search_kospi(cleaned, limit=8)

    def get_master(self, code: str) -> dict:
        stock = self.repository.get_kospi(code)
        if stock is None:
            raise StockNotFoundError(code)
        return stock

    def list_mine(self, user_id: int) -> list[dict]:
        return [self._response(row) for row in self.repository.list_user_stocks(user_id)]

    def add(self, user_id: int, code: str, status: str) -> dict:
        self.get_master(code)
        return self._response(self.repository.upsert_user_stock(user_id, code, status))

    def update(
        self,
        user_id: int,
        code: str,
        *,
        status: str | None,
        tags: list[str] | None,
    ) -> dict:
        if tags not in (None, []):
            raise UnsupportedStockTagsError(
                "현재 DB 스키마에는 종목 태그 저장 구조가 없습니다."
            )
        current = self.repository.get_user_stock(user_id, code)
        if current is None:
            raise UserStockNotFoundError(code)
        if status is not None:
            current = self.repository.update_status(user_id, code, status)
            if current is None:
                raise UserStockNotFoundError(code)
        return self._response(current)

    def remove(self, user_id: int, code: str) -> None:
        if not self.repository.soft_delete(user_id, code):
            raise UserStockNotFoundError(code)

    @staticmethod
    def _response(row: dict) -> dict:
        return {**row, "tags": []}
