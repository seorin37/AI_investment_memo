"""홈 위젯 API: /checklist-items, /price-conditions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import HomeRepository
from .service import AiLinkOffError, HomeService, PriceConditionNotFoundError, StockNotOwnedError

router = APIRouter(prefix="/api/v1", tags=["home"])


class ChecklistItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_code: str = Field(pattern=r"^[0-9A-Z]{6}$")
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("체크리스트 내용은 비어 있을 수 없습니다.")
        return cleaned


class PriceTrackingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracking: bool


def get_home_query_service(db: Session = Depends(get_read_db)) -> HomeService:
    return HomeService(HomeRepository(db))


def get_home_command_service(db: Session = Depends(get_db)) -> HomeService:
    return HomeService(HomeRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


@router.get("/checklist-items")
def list_checklist_items(
    current: dict = Depends(get_current_user),
    service: HomeService = Depends(get_home_query_service),
):
    return service.list_checklist(_user_id(current))


@router.post("/checklist-items", status_code=201)
def add_checklist_item(
    payload: ChecklistItemCreate,
    current: dict = Depends(get_current_user),
    service: HomeService = Depends(get_home_command_service),
):
    try:
        return service.add_checklist_item(_user_id(current), payload.stock_code, payload.text)
    except StockNotOwnedError as exc:
        raise HTTPException(404, detail="내 종목에서 찾을 수 없습니다.") from exc


@router.get("/price-conditions")
def list_price_conditions(
    current: dict = Depends(get_current_user),
    service: HomeService = Depends(get_home_query_service),
):
    return service.list_price_conditions(_user_id(current))


@router.patch("/memos/{memo_id}/price-conditions/{condition_id}", status_code=204)
def set_price_condition_tracking(
    memo_id: int,
    condition_id: int,
    payload: PriceTrackingPatch,
    current: dict = Depends(get_current_user),
    service: HomeService = Depends(get_home_command_service),
):
    try:
        service.set_price_tracking(_user_id(current), memo_id, condition_id, payload.tracking)
    except PriceConditionNotFoundError as exc:
        raise HTTPException(404, detail="가격 조건을 찾을 수 없습니다.") from exc
    except AiLinkOffError as exc:
        raise HTTPException(409, detail="AI 연결이 꺼진 메모예요. 메모에서 AI 연결을 먼저 켜 주세요.") from exc
    return Response(status_code=204)
