"""AI 업데이트 카드 조회·읽음 처리 API (2026-11-11, frontend/docs/API_CONTRACT.md 3·6절)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

from .repository import UpdatesRepository
from .service import MemoNotFoundError, UpdateNotFoundError, UpdatesService

router = APIRouter(prefix="/api/v1", tags=["ai-updates"])


def get_query_service(db: Session = Depends(get_read_db)) -> UpdatesService:
    return UpdatesService(UpdatesRepository(db))


def get_command_service(db: Session = Depends(get_db)) -> UpdatesService:
    return UpdatesService(UpdatesRepository(db))


def _user_id(current: dict) -> int:
    try:
        return int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


@router.get("/stocks/{code}/ai-updates")
def list_stock_ai_updates(code: str, limit: int = Query(100, ge=1, le=500), current: dict = Depends(get_current_user),
                          service: UpdatesService = Depends(get_query_service)):
    """보드 우측 패널: 이 종목의 AI 연결 ON 메모에 연결된 카드, 최신순."""
    return service.stock_ai_updates(_user_id(current), code, limit)


@router.get("/memos/{memo_id}/timeline")
def get_memo_timeline(memo_id: int, current: dict = Depends(get_current_user),
                      service: UpdatesService = Depends(get_query_service)):
    try:
        return service.memo_timeline(_user_id(current), memo_id)
    except MemoNotFoundError as exc:
        raise HTTPException(404, detail="메모를 찾을 수 없습니다.") from exc


@router.get("/ai-updates/summary")
def get_ai_updates_summary(current: dict = Depends(get_current_user),
                           service: UpdatesService = Depends(get_query_service)):
    return service.summary(_user_id(current))


@router.post("/ai-updates/{update_id}/read", status_code=204)
def mark_ai_update_read(update_id: int, current: dict = Depends(get_current_user),
                        service: UpdatesService = Depends(get_command_service)):
    try:
        service.mark_read(_user_id(current), update_id)
    except UpdateNotFoundError as exc:
        raise HTTPException(404, detail="업데이트를 찾을 수 없습니다.") from exc
    return Response(status_code=204)
