"""시세·뉴스·기업 정보·시장 개요 조회 API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_read_db

from .repository import MarketDataRepository
from .service import (
    FinancialsNotFoundError,
    MarketDataService,
    PriceDataNotFoundError,
    StockNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["marketdata"])

StockCode = Path(pattern=r"^[0-9A-Z]{6}$")


def get_marketdata_service(db: Session = Depends(get_read_db)) -> MarketDataService:
    return MarketDataService(MarketDataRepository(db))


def _not_found(exc: LookupError) -> HTTPException:
    detail = {
        PriceDataNotFoundError: "시세 데이터가 없습니다.",
        StockNotFoundError: "종목을 찾을 수 없습니다.",
        FinancialsNotFoundError: "재무 데이터가 없습니다.",
    }.get(type(exc), "데이터가 없습니다.")
    return HTTPException(404, detail=detail)


_LOOKUP_ERRORS = (PriceDataNotFoundError, StockNotFoundError, FinancialsNotFoundError)


@router.get("/stocks/{code}/quote")
def get_quote(
    code: str = StockCode,
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.quote(code)
    except _LOOKUP_ERRORS as exc:
        raise _not_found(exc) from exc


@router.get("/stocks/{code}/candles")
def get_candles(
    code: str = StockCode,
    range: Literal["1W", "1M", "3M", "1Y"] = Query(default="3M"),
    adjusted: bool = Query(default=True, description="true: 수정주가(기본), false: 원시 주가"),
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.candles(code, range, adjusted)
    except _LOOKUP_ERRORS as exc:
        raise _not_found(exc) from exc


@router.get("/stocks/{code}/profile")
def get_profile(
    code: str = StockCode,
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.profile(code)
    except _LOOKUP_ERRORS as exc:
        raise _not_found(exc) from exc


@router.get("/stocks/{code}/financials")
def get_financials(
    code: str = StockCode,
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    try:
        return service.financials(code)
    except _LOOKUP_ERRORS as exc:
        raise _not_found(exc) from exc


@router.get("/news/headlines")
def list_headlines(
    limit: int = Query(default=20, ge=1, le=50),
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    return service.headlines(limit)


@router.get("/news/home")
def get_home_news(
    limit: int = Query(default=9, ge=1, le=50),
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    """홈 뉴스 위젯: 최신 기사(웹 9개·앱 5개 사용) + 가장 새 기사 날짜의 기사 수."""
    return service.home_news(limit)


@router.get("/market/overview")
def get_market_overview(
    _current: dict = Depends(get_current_user),
    service: MarketDataService = Depends(get_marketdata_service),
):
    return service.overview()
