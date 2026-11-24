"""투자 기록 API: GET·POST /journal, PATCH·DELETE /journal/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import JournalRepository
from .schemas import JournalCreate, JournalPatch
from .service import JournalNotFoundError, JournalService, JournalStockNotFoundError

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


def get_journal_query_service(db: Session = Depends(get_read_db)) -> JournalService:
    return JournalService(JournalRepository(db))


def get_journal_command_service(db: Session = Depends(get_db)) -> JournalService:
    return JournalService(JournalRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _not_ready(exc: ProgrammingError) -> HTTPException:
    """0020(journal_entries.blocks) 적용 전 DB 면 500 대신 알아볼 수 있는 503."""
    if "blocks" in str(exc.orig if hasattr(exc, "orig") else exc):
        return HTTPException(503, detail="투자 기록 저장소가 준비되지 않았어요 (DB 마이그레이션 0020 적용 필요).")
    raise exc


@router.get("")
def list_journal(
    current: dict = Depends(get_current_user),
    service: JournalService = Depends(get_journal_query_service),
):
    try:
        return service.list(_user_id(current))
    except ProgrammingError as exc:
        raise _not_ready(exc) from exc


@router.post("", status_code=201)
def create_journal(
    payload: JournalCreate,
    current: dict = Depends(get_current_user),
    service: JournalService = Depends(get_journal_command_service),
):
    try:
        return service.create(_user_id(current), payload)
    except JournalStockNotFoundError as exc:
        raise HTTPException(422, detail="종목을 찾을 수 없습니다.") from exc
    except ProgrammingError as exc:
        raise _not_ready(exc) from exc


@router.patch("/{entry_id}")
def update_journal(
    entry_id: int,
    payload: JournalPatch,
    current: dict = Depends(get_current_user),
    service: JournalService = Depends(get_journal_command_service),
):
    try:
        return service.update(_user_id(current), entry_id, payload)
    except JournalNotFoundError as exc:
        raise HTTPException(404, detail="투자 기록을 찾을 수 없습니다.") from exc
    except JournalStockNotFoundError as exc:
        raise HTTPException(422, detail="종목을 찾을 수 없습니다.") from exc
    except ProgrammingError as exc:
        raise _not_ready(exc) from exc


@router.delete("/{entry_id}", status_code=204)
def delete_journal(
    entry_id: int,
    current: dict = Depends(get_current_user),
    service: JournalService = Depends(get_journal_command_service),
):
    """휴지통으로 보낸다 (deleted_at). 복원·영구 삭제는 /trash."""
    try:
        service.delete(_user_id(current), entry_id)
    except JournalNotFoundError as exc:
        raise HTTPException(404, detail="투자 기록을 찾을 수 없습니다.") from exc
    return Response(status_code=204)
