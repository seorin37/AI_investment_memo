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


class StockCreateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9A-Z]{6}$")
    status: StockStatus


class StockUpdateRequest(BaseModel):
    status: StockStatus | None = None
    tags: list[str] | None = None
