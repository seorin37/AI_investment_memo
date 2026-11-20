"""Pydantic contracts matching the existing frontend stock API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


StockStatus = Literal["holding", "watching"]


class StockMasterResponse(BaseModel):
    code: str
    name: str
    market: Literal["KOSPI", "KOSDAQ", "KONEX"]


class MyStockResponse(StockMasterResponse):
    status: StockStatus
    tags: list[str] = Field(default_factory=list)
    unread_updates: int = 0
    added_at: datetime
    position: int = 0          # 사이드바 자리 (0021, 0부터). 목록 응답에서만 정확하다


class StockCreateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9A-Z]{6}$")
    status: StockStatus


class StockUpdateRequest(BaseModel):
    status: StockStatus | None = None
    tags: list[str] | None = None


class StockOrderRequest(BaseModel):
    """사이드바 내 종목 전체 순서. 빠진 종목은 서버가 지금 순서대로 맨 뒤에 붙인다."""
    codes: list[str] = Field(max_length=500)
