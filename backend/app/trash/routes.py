"""휴지통 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import TrashRepository
from .service import TrashItemNotFoundError, TrashPurgeBlockedError, TrashService

router = APIRouter(prefix="/api/v1/trash", tags=["trash"])


def get_trash_query_service(db: Session = Depends(get_read_db)) -> TrashService:
    return TrashService(TrashRepository(db))


def get_trash_command_service(db: Session = Depends(get_db)) -> TrashService:
    return TrashService(TrashRepository(db))


def _user_id(current_user: dict) -> int:
    try:
        return int(current_user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _not_found() -> HTTPException:
    return HTTPException(404, detail="휴지통 항목을 찾을 수 없습니다.")


@router.get("")
def list_trash(
    current: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_query_service),
):
    return service.list(_user_id(current))


@router.post("/{trash_id}/restore", status_code=204)
def restore_trash(
    trash_id: str,
    current: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_command_service),
):
    try:
        service.restore(_user_id(current), trash_id)
    except TrashItemNotFoundError as exc:
        raise _not_found() from exc
    return Response(status_code=204)


@router.delete("/{trash_id}", status_code=204)
def purge_trash(
    trash_id: str,
    current: dict = Depends(get_current_user),
    service: TrashService = Depends(get_trash_command_service),
):
    try:
        service.purge(_user_id(current), trash_id)
    except TrashItemNotFoundError as exc:
        raise _not_found() from exc
    except TrashPurgeBlockedError as exc:
        raise HTTPException(
            409, detail="AI 추적 사용 기록이 남아 있는 메모라 영구 삭제할 수 없어요. 휴지통에 그대로 둘게요."
        ) from exc
    return Response(status_code=204)
