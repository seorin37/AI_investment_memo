"""메모 질문 답 목록 (2026-11-20, 0019 ask → answer).

GET /api/v1/memos/{memo_id}/answers
- 메모 분석이 찾은 질문(tracking_items.type='ask')마다 답 상태와 답 카드를 돌려준다. 질문을 만든 순서.
- status: pending(아직 답 전, 다음 매일 실행에서 답함) · answered · no_answer(자료에서 확인되지 않음)
- 같은 메모의 질문 여러 개를 한 카드로 합쳐 답한 경우(details.merged_items), 합쳐진 질문도 그 카드를 답으로 본다.
- AI 업데이트 API(/ai-updates, /timeline)는 프론트 타입 호환을 위해 answer 카드를 news·disclosure로 바꿔 보낸다.
  이 API는 질문 답 전용이라 원래 모양(질문 ↔ 답)으로 보낸다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_read_db

router = APIRouter(prefix="/api/v1", tags=["memo-answers"])

MEMO_SQL = "SELECT id FROM memos WHERE id = :m AND user_id = :u AND deleted_at IS NULL"
ASKS_SQL = """SELECT ti.id, ti.status::text, COALESCE(r.description, ti.description) AS question, ti.created_at
FROM tracking_items ti
LEFT JOIN LATERAL (SELECT description FROM tracking_item_revisions WHERE tracking_item_id = ti.id
                   ORDER BY revision_no DESC LIMIT 1) r ON true
WHERE ti.memo_id = :m AND ti.type = 'ask' ORDER BY ti.id"""
CARDS_SQL = """SELECT tu.id, tu.tracking_item_id, tu.type::text, tu.title, tu.summary, tu.details, tu.is_read, tu.created_at
FROM tracking_updates tu JOIN tracking_items ti ON ti.id = tu.tracking_item_id
WHERE ti.memo_id = :m ORDER BY tu.id"""
SOURCES_SQL = """SELECT us.update_id, us.news_id, us.disclosure_rcept_no, us.quote,
       na.title AS news_title, na.url AS news_url, na.published_at, ns.name AS news_source,
       d.title AS disclosure_title, d.rcept_dt, d.source_url
FROM update_sources us
LEFT JOIN news_articles na ON na.id = us.news_id
LEFT JOIN news_sources ns ON ns.id = na.source_id
LEFT JOIN disclosures d ON d.rcept_no = us.disclosure_rcept_no
WHERE us.update_id = ANY(:ids) ORDER BY us.id"""


def _source(row) -> dict[str, Any]:
    if row["news_id"] is not None:
        return {"kind": "news", "title": row["news_title"] or "", "source": row["news_source"] or "뉴스",
                "date": row["published_at"].date().isoformat() if row["published_at"] else None, "url": row["news_url"]}
    return {"kind": "disclosure", "title": row["disclosure_title"] or "", "source": "DART",
            "date": row["rcept_dt"].isoformat() if row["rcept_dt"] else None, "url": row["source_url"]}


def memo_answers(db: Session, user_id: int, memo_id: int) -> list[dict[str, Any]] | None:
    if db.execute(text(MEMO_SQL), {"m": memo_id, "u": user_id}).first() is None:
        return None
    asks = db.execute(text(ASKS_SQL), {"m": memo_id}).mappings().all()
    cards = [dict(r) for r in db.execute(text(CARDS_SQL), {"m": memo_id}).mappings().all()]
    by_item: dict[int, dict] = {}
    for c in cards:                                              # 자기 카드 먼저, 없으면 합쳐 답한 카드
        if c["type"] == "answer" or (c["details"] or {}).get("answer_status"):
            by_item.setdefault(int(c["tracking_item_id"]), c)
    for c in cards:
        for m in (c["details"] or {}).get("merged_items") or []:
            by_item.setdefault(int(m.get("item_id")), c)
    used = {int(c["id"]) for c in by_item.values()}
    sources: dict[int, list] = {}
    if used:
        for r in db.execute(text(SOURCES_SQL), {"ids": sorted(used)}).mappings().all():
            sources.setdefault(int(r["update_id"]), []).append(_source(r))
    out = []
    for a in asks:
        card = by_item.get(int(a["id"]))
        status = "pending"
        answer = None
        if card is not None:
            d = card["details"] or {}
            status = "no_answer" if d.get("answer_status") == "no_answer" else "answered"
            answer = {"id": str(card["id"]), "headline": card["title"], "summary": card["summary"],
                      "text": d.get("explanation") or card["summary"], "calculations": d.get("calculations") or [],
                      "sources": d.get("source_list") or sources.get(int(card["id"]), []),
                      "answered_at": card["created_at"], "read": bool(card["is_read"])}
        elif a["status"] != "active":                            # 답 카드 없이 닫힌 질문 (메모 수정으로 사라진 질문 등)
            continue
        out.append({"id": str(a["id"]), "question": a["question"], "asked_at": a["created_at"], "status": status,
                    "answer": answer})
    return out


@router.get("/memos/{memo_id}/answers")
def get_memo_answers(memo_id: int, current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    try:
        user_id = int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc
    out = memo_answers(db, user_id, memo_id)
    if out is None:
        raise HTTPException(404, detail="메모를 찾을 수 없습니다.")
    return out
