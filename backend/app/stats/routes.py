"""설정 화면 숫자와 피드백 (2026-11-20). 프론트 mock(getAiStats·getDataStats·sendFeedback)과 같은 모양.

- GET /api/v1/ai/stats   {linked_memos, updates_this_month, linked_stocks}: AI 연결 메모 수, 이번 달(한국 시간) AI 소식 수, AI 연결 종목 수
- GET /api/v1/data/stats {memos, journals, stocks}: 내 메모·투자 기록·종목 수 (지운 것 제외)
- GET /api/v1/ai/tracking [{stock_code, name, memos:[{memo_id, title, chips}]}]: 설정 사용량 탭 "종목별 추적 현황" (2026-11-23)
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


# 지금 추적 중인 항목 (한 번 답하는 질문 ask는 추적이 아니라 뺀다)
TRACKING_SQL = """
SELECT btrim(us.symbol) AS code, s.name, m.id AS memo_id, m.title, m.content, ti.type::text AS type, ti.description
FROM user_stocks us
JOIN stocks s ON s.symbol = us.symbol
LEFT JOIN memos m ON m.user_id = us.user_id AND m.symbol = us.symbol AND m.deleted_at IS NULL AND m.ai_linked
LEFT JOIN tracking_items ti ON ti.memo_id = m.id AND ti.status = 'active' AND ti.type::text <> 'ask'
WHERE us.user_id = :u AND us.deleted_at IS NULL
ORDER BY us.created_at, us.symbol, m.id, ti.id"""

CHIP_KIND = {"topic": "공시·뉴스", "price_below": "가격 조건", "price_above": "가격 조건", "compare": "비교"}


def _memo_title(title: str | None, content: str | None) -> str:
    if title and title.strip():
        return title.strip()
    first = next((line.strip() for line in (content or "").splitlines() if line.strip()), "")
    return first[:40] or "제목 없는 메모"


def tracking_status(db: Session, user_id: int) -> list[dict]:
    """내 종목마다 추적 항목이 있는 AI 연결 메모와 그 항목(칩). 항목이 없는 메모는 넣지 않는다 (종목은 남긴다)."""
    out: dict[str, dict] = {}
    memos: dict[int, dict] = {}
    for r in db.execute(text(TRACKING_SQL), {"u": user_id}).mappings().all():
        stock = out.setdefault(r["code"], {"stock_code": r["code"], "name": r["name"], "memos": []})
        if r["memo_id"] is None or r["type"] is None:
            continue
        memo = memos.get(r["memo_id"])
        if memo is None:
            memo = memos[r["memo_id"]] = {"memo_id": str(r["memo_id"]), "title": _memo_title(r["title"], r["content"]), "chips": []}
            stock["memos"].append(memo)
        memo["chips"].append(f"{CHIP_KIND.get(r['type'], '추적')} · {r['description']}")
    return list(out.values())


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


@router.get("/ai/tracking")
def get_ai_tracking(current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    return tracking_status(db, _user_id(current))


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
