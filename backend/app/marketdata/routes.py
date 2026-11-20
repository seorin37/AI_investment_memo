"""시세·뉴스 조회 API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_read_db

from .repository import MarketDataRepository
from .service import MarketDataService, PriceDataNotFoundError

router = APIRouter(prefix="/api/v1", tags=["marketdata"])

StockCode = Path(pattern=r"^[0-9A-Z]{6}$")


def get_marketdata_service(db: Session = Depends(get_read_db)) -> MarketDataService:
    return MarketDataService(MarketDataRepository(db))


def _no_prices() -> HTTPException:
    return HTTPException(404, detail="시세 데이터가 없습니다.")


@router.get("/stocks/{code}/quote")
def get_quote(
    code: str = StockCode,
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.quote(code)
    except PriceDataNotFoundError as exc:
        raise _no_prices() from exc


@router.get("/stocks/{code}/candles")
def get_candles(
    code: str = StockCode,
    range: Literal["1W", "1M", "3M", "1Y"] = Query(default="3M"),
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.candles(code, range)
    except PriceDataNotFoundError as exc:
        raise _no_prices() from exc


@router.get("/news/headlines")
def list_headlines(
    limit: int = Query(default=20, ge=1, le=50),
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    return service.headlines(limit)
