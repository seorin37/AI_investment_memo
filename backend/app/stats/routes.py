"""설정 화면 숫자와 피드백 (2026-11-20). 프론트 mock(getAiStats·getDataStats·sendFeedback)과 같은 모양.

- GET /api/v1/ai/stats   {linked_memos, updates_this_month, linked_stocks}: AI 연결 메모 수, 이번 달(한국 시간) AI 소식 수, AI 연결 종목 수
- GET /api/v1/data/stats {memos, journals, stocks}: 내 메모·투자 기록·종목 수 (지운 것 제외)
- POST /api/v1/feedback  FeedbackPayload {kind, rating?, screen?, categories?, message} → feedbacks 테이블, 204
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db

router = APIRouter(prefix="/api/v1", tags=["stats"])
SEOUL = ZoneInfo("Asia/Seoul")


def _user_id(current: dict) -> int:
    try:
        return int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def ai_stats(db: Session, user_id: int, now: datetime | None = None) -> dict[str, int]:
    now = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    month_start = datetime(now.year, now.month, 1, tzinfo=SEOUL)
    row = db.execute(text("""
        SELECT (SELECT count(*) FROM memos WHERE user_id = :u AND deleted_at IS NULL AND ai_linked),
               (SELECT count(DISTINCT btrim(symbol)) FROM memos WHERE user_id = :u AND deleted_at IS NULL AND ai_linked),
               (SELECT count(*) FROM tracking_updates tu JOIN tracking_items ti ON ti.id = tu.tracking_item_id
                  JOIN memos m ON m.id = ti.memo_id
                 WHERE m.user_id = :u AND m.deleted_at IS NULL AND tu.created_at >= :since)"""),
                     {"u": user_id, "since": month_start}).one()
    return {"linked_memos": int(row[0]), "updates_this_month": int(row[2]), "linked_stocks": int(row[1])}


def data_stats(db: Session, user_id: int) -> dict[str, int]:
    row = db.execute(text("""
        SELECT (SELECT count(*) FROM memos WHERE user_id = :u AND deleted_at IS NULL AND kind = 'note'),
               (SELECT count(*) FROM journal_entries WHERE user_id = :u AND deleted_at IS NULL),
               (SELECT count(*) FROM user_stocks WHERE user_id = :u AND deleted_at IS NULL)"""), {"u": user_id}).one()
    return {"memos": int(row[0]), "journals": int(row[1]), "stocks": int(row[2])}


class FeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["general", "bug"]
    rating: int | None = Field(default=None, ge=1, le=5)
    screen: str | None = Field(default=None, max_length=200)
    categories: list[str] = Field(default_factory=list, max_length=20)
    message: str = Field(max_length=5000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("내용을 입력해 주세요.")
        return value.strip()


@router.get("/ai/stats")
def get_ai_stats(current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    return ai_stats(db, _user_id(current))


@router.get("/data/stats")
def get_data_stats(current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    return data_stats(db, _user_id(current))


@router.post("/feedback", status_code=204)
def post_feedback(payload: FeedbackPayload, current: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(text("""INSERT INTO feedbacks (user_id, kind, screen, types, body, rating, status)
        VALUES (:u, :k, :s, CAST(:t AS jsonb), :b, :r, 'new')"""),
               {"u": _user_id(current), "k": payload.kind, "s": payload.screen,
                "t": json.dumps(payload.categories, ensure_ascii=False), "b": payload.message, "r": payload.rating})
    db.commit()
    return Response(status_code=204)
