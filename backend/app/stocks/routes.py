"""FastAPI routes for KOSPI master search and user-owned stocks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import StockRepository
from .schemas import (
    MyStockResponse,
    StockCreateRequest,
    StockMasterResponse,
    StockOrderRequest,
    StockUpdateRequest,
)
from .service import (
    InvalidStockOrderError,
    StockNotFoundError,
    StockService,
    UnsupportedStockTagsError,
    UserStockNotFoundError,
)


router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])


def get_query_service(db: Session = Depends(get_read_db)) -> StockService:
    return StockService(StockRepository(db))


def get_command_service(db: Session = Depends(get_db)) -> StockService:
    return StockService(StockRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _stock_not_found() -> HTTPException:
    return HTTPException(404, detail="종목을 찾을 수 없습니다.")


@router.get("/search", response_model=list[StockMasterResponse])
def search_stocks(
    q: str = Query(min_length=1, max_length=80),
    _current: dict = Depends(get_current_user),
    service: StockService = Depends(get_query_service),
):
    return service.search(q)


@router.get("", response_model=list[MyStockResponse])
def list_my_stocks(
    current: dict = Depends(get_current_user),
    service: StockService = Depends(get_query_service),
):
    return service.list_mine(_user_id(current))


@router.put("/order", response_model=list[MyStockResponse])
def put_stock_order(
    payload: StockOrderRequest,
    current: dict = Depends(get_current_user),
    service: StockService = Depends(get_command_service),
):
    """사이드바에서 끌어 옮긴 뒤 내 종목 전체 순서를 저장하고, 새 순서의 목록을 돌려준다 (0021)."""
    try:
        return service.reorder(_user_id(current), payload.codes)
    except InvalidStockOrderError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.post("", response_model=MyStockResponse)
def add_stock(
    payload: StockCreateRequest,
    current: dict = Depends(get_current_user),
    service: StockService = Depends(get_command_service),
):
    try:
        return service.add(_user_id(current), payload.code, payload.status)
    except StockNotFoundError as exc:
        raise _stock_not_found() from exc


@router.get("/{code}", response_model=StockMasterResponse)
def get_stock(
    code: str,
    _current: dict = Depends(get_current_user),
    service: StockService = Depends(get_query_service),
):
    try:
        return service.get_master(code)
    except StockNotFoundError as exc:
        raise _stock_not_found() from exc


@router.patch("/{code}", response_model=MyStockResponse)
def update_stock(
    code: str,
    payload: StockUpdateRequest,
    current: dict = Depends(get_current_user),
    service: StockService = Depends(get_command_service),
):
    try:
        return service.update(
            _user_id(current),
            code,
            status=payload.status,
            tags=payload.tags,
        )
    except UserStockNotFoundError as exc:
        raise _stock_not_found() from exc
    except UnsupportedStockTagsError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.delete("/{code}", status_code=204)
def delete_stock(
    code: str,
    current: dict = Depends(get_current_user),
    service: StockService = Depends(get_command_service),
):
    try:
        service.remove(_user_id(current), code)
    except UserStockNotFoundError as exc:
        raise _stock_not_found() from exc
    return Response(status_code=204)
