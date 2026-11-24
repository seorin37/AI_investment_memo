"""오늘의 퀴즈 (2026-11-22). 문제는 quiz_questions(0023)에서 읽는다.

- GET /api/v1/quiz/today → 오늘 문제 1개. 문제가 하나도 없으면 404 (프론트는 내장 문제로 대신 보여 준다)
- 오늘 문제 = 켜 둔 문제(is_active)를 demo_order(없으면 id) 순으로 세우고, 한국 시간 오전 10시마다 다음 문제.
  프론트 quizBank.ts quizIndex 와 같은 계산이라 DB 와 내장 문제 순서가 같으면 같은 문제가 나온다.
- 답 제출 · 연속 참여 기록은 아직 없음 (quiz_answers 는 제출 API 를 만들 때)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_read_db

router = APIRouter(prefix="/api/v1", tags=["quiz"])

OPEN_HOUR = 10  # 새 문제가 열리는 시각 (한국 시간)
_SHIFT_SECONDS = (9 - OPEN_HOUR) * 3600  # UTC → 한국 시간(+9) → 오전 10시를 하루의 시작으로


def quiz_index(now: datetime, total: int) -> int:
    """오늘(한국 시간 오전 10시 기준) 문제 번호 — 날마다 하나씩, total 개를 다 돌면 처음으로."""
    if total <= 0:
        raise ValueError("total must be positive")
    day = int((now.timestamp() + _SHIFT_SECONDS) // 86400)
    return day % total


def today_quiz(db: Session, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(timezone.utc)
    total = db.execute(text("SELECT count(*) FROM quiz_questions WHERE is_active")).scalar() or 0
    if not total:
        return None
    row = db.execute(text("""
        SELECT slug, category, quiz_type, label, question, options, answer_index, explanation, concept, source
          FROM quiz_questions WHERE is_active
         ORDER BY demo_order NULLS LAST, id
         OFFSET :i LIMIT 1"""), {"i": quiz_index(now, int(total))}).mappings().one_or_none()
    if row is None:
        return None
    return {**dict(row), "options": list(row["options"]), "index": quiz_index(now, int(total)), "total": int(total)}


@router.get("/quiz/today")
def get_today_quiz(current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    quiz = today_quiz(db)
    if quiz is None:
        raise HTTPException(404, detail="퀴즈 문제가 아직 없어요.")
    return quiz
