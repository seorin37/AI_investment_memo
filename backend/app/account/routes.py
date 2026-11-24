"""홈 배치 · 설정 · 내 프로필 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.repository import AuthRepository
from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import AccountRepository
from .schemas import HomeLayout, ProfilePatch, SettingsPatch, TermsAgree
from .service import AccountService, TermsError, UserNotFoundError

router = APIRouter(prefix="/api/v1", tags=["account"])


def get_account_query_service(db: Session = Depends(get_read_db)) -> AccountService:
    return AccountService(AccountRepository(db), AuthRepository(db))


def get_account_command_service(db: Session = Depends(get_db)) -> AccountService:
    return AccountService(AccountRepository(db), AuthRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


@router.get("/home/layout")
def get_home_layout(
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_query_service),
):
    return service.get_home_layout(_user_id(current))


@router.put("/home/layout")
def save_home_layout(
    payload: HomeLayout,
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_command_service),
):
    return service.save_home_layout(_user_id(current), payload)


@router.get("/settings")
def get_settings(
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_query_service),
):
    return service.get_settings(_user_id(current))


@router.patch("/settings")
def update_settings(
    payload: SettingsPatch,
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_command_service),
):
    return service.update_settings(_user_id(current), payload)


@router.get("/me")
def get_me(
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_query_service),
):
    try:
        return service.get_me(_user_id(current))
    except UserNotFoundError as exc:
        raise HTTPException(404, detail="사용자를 찾을 수 없습니다.") from exc


@router.patch("/me")
def update_me(
    payload: ProfilePatch,
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_command_service),
):
    try:
        return service.update_me(_user_id(current), payload)
    except UserNotFoundError as exc:
        raise HTTPException(404, detail="사용자를 찾을 수 없습니다.") from exc


# ─── 약관 동의 (0022 user_terms_consents · 현재 버전 = defaults.TERMS_VERSION)
@router.get("/me/terms")
def get_my_terms(
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_query_service),
):
    return service.get_terms(_user_id(current))


@router.post("/me/terms")
def agree_my_terms(
    payload: TermsAgree,
    current: dict = Depends(get_current_user),
    service: AccountService = Depends(get_account_command_service),
):
    try:
        return service.agree_terms(_user_id(current), payload)
    except TermsError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
