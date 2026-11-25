"""크레딧 사용량 API (2026-11-20). 화면: MY·스튜디오의 'AI 사용량 %'·'11.30 갱신', 메모 상세의 AI 멈춤(ai_paused)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db

from . import ai_off, ledger

router = APIRouter(prefix="/api/v1", tags=["credits"])


@router.get("/me/usage")
def get_my_usage(current: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """이번 기간 사용량. 이번 달 기본량을 아직 안 받았으면 여기서 지급한다(쓰기 세션)."""
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    out = ledger.usage(db, user_id).to_dict()
    out["ai_memo_count"] = ai_off.active_ai_count(db, user_id)    # 2026-11-24 선택 창 'AI 연결 메모 N개가 모두 꺼져요'
    out["auto_off_count"] = ai_off.auto_off_count(db, user_id)    # 갱신일에 자동으로 꺼진 메모 수 (안내 한 번)
    return out


@router.post("/me/ai-off")
def turn_off_my_ai(current: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """크레딧을 다 쓴 뒤 선택 창의 'AI 연결 모두 끄기' (2026-11-24). 메모는 남고 AI 연결만 꺼진다. 다시 켤 때는 메모마다."""
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    n = ai_off.turn_off_all(db, user_id)
    db.commit()
    return {"turned_off": n}


@router.post("/me/ai-off/notice-seen")
def seen_ai_off_notice(current: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """'지난 기간 AI 사용량을 다 써서 N개가 꺼졌어요' 안내 확인 (2026-11-24). 메모는 꺼진 채, 표시만 지운다."""
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    n = ai_off.clear_notice(db, user_id)
    db.commit()
    return {"cleared": n}
