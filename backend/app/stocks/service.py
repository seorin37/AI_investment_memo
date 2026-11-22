"""Business rules for authenticated stock management."""

from __future__ import annotations

from .repository import StockRepository

# 많이 찾는 종목 (온보딩 종목 고르기). 사람이 적을 때 몇 명이 담았는지 드러나지 않게 3명 이상만 인정
POPULAR_MIN_USERS = 3
POPULAR_DEFAULT = 12
POPULAR_MAX = 30


class StockNotFoundError(LookupError):
    pass


class UserStockNotFoundError(LookupError):
    pass


class UnsupportedStockTagsError(ValueError):
    pass


class InvalidStockOrderError(ValueError):
    pass


class StockService:
    def __init__(self, repository: StockRepository) -> None:
        self.repository = repository

    def search(self, query: str) -> list[dict]:
        cleaned = query.strip()
        if not cleaned:
            return []
        return self.repository.search_kospi(cleaned, limit=8)

    def popular(self, limit: int = POPULAR_DEFAULT) -> list[dict]:
        """많이 찾는 종목: 담은 사람 POPULAR_MIN_USERS 명 이상 → 모자라면 최신 시총 순으로 채움. [{code, name, market}]만."""
        limit = max(1, min(int(limit), POPULAR_MAX))
        out: list[dict] = []
        seen: set[str] = set()

        def put(rows: list[dict]) -> None:
            for row in rows:
                code = str(row["code"]).strip()
                if code in seen or len(out) >= limit:
                    continue
                seen.add(code)
                out.append({"code": code, "name": row["name"], "market": row["market"]})

        put(self.repository.popular_by_users(min_users=POPULAR_MIN_USERS, limit=limit))
        if len(out) < limit:
            put(self.repository.top_market_cap(limit=limit - len(out), exclude=sorted(seen)))
        return out

    def get_master(self, code: str) -> dict:
        stock = self.repository.get_kospi(code)
        if stock is None:
            raise StockNotFoundError(code)
        return stock

    def list_mine(self, user_id: int) -> list[dict]:
        return [self._response(row) for row in self.repository.list_user_stocks(user_id)]

    def add(self, user_id: int, code: str, status: str) -> dict:
        self.get_master(code)
        return self._placed(user_id, self._response(self.repository.upsert_user_stock(user_id, code, status)))

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
        return self._placed(user_id, self._response(current))

    def _placed(self, user_id: int, row: dict) -> dict:
        """종목 하나 응답에도 사이드바 자리(0021)를 넣는다."""
        order = self.repository.stock_order(user_id)
        code = str(row.get("code") or "").strip()
        return {**row, "position": order.index(code) if code in order else 0}

    def reorder(self, user_id: int, codes: list[str]) -> list[dict]:
        """사이드바 순서 저장 (0021). 빠진 종목은 지금 순서대로 뒤에. 내 종목이 아니거나(지운 것 포함) 중복이면 거절."""
        codes = [c.strip() for c in codes]
        if len(set(codes)) != len(codes):
            raise InvalidStockOrderError("같은 종목이 순서에 두 번 들어 있습니다.")
        current = self.repository.stock_order(user_id, lock=True)
        unknown = [c for c in codes if c not in set(current)]
        if unknown:
            raise InvalidStockOrderError(f"내 종목이 아닙니다: {', '.join(unknown)}")
        given = set(codes)
        self.repository.write_stock_order(user_id, codes + [c for c in current if c not in given])
        return self.list_mine(user_id)

    def remove(self, user_id: int, code: str) -> None:
        if not self.repository.soft_delete(user_id, code):
            raise UserStockNotFoundError(code)

    @staticmethod
    def _response(row: dict) -> dict:
        return {**row, "tags": []}
