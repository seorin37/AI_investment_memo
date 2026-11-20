"""크레딧 사용량 API (2026-11-20). 화면: MY·스튜디오의 'AI 사용량 %'·'11.30 갱신', 메모 상세의 AI 멈춤(ai_paused)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db

from . import ledger

router = APIRouter(prefix="/api/v1", tags=["credits"])


@router.get("/me/usage")
def get_my_usage(current: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """이번 기간 사용량. 이번 달 기본량을 아직 안 받았으면 여기서 지급한다(쓰기 세션)."""
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    return ledger.usage(db, user_id).to_dict()
