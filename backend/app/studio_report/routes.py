"""POST /api/v1/studio/reports — 주간보고서 만들기 (2026-11-23, docs/weekly-report-plan.md 6장).

- 기간: 주가는 그 주 월~금 거래일, 소식(뉴스·공시)은 월요일 0시 ~ 일요일 밤 12시(주말 기사 포함, build.news_window).
- 같은 주·같은 종목 조합·같은 증시 칸 보고서가 이미 있으면 그것을 돌려준다(크레딧 안 씀).
  단, 주말(아직 일요일이 안 끝난 주)에 만든 것은 같은 날 것만 다시 쓴다 — 다음 날에는 새 주말 기사가 있을 수 있다.
- 새로 만들면 studio_items에 status=generating으로 넣고, 응답 뒤 백그라운드로 만든다. 앱은 GET /studio/items로 상태를 본다.
- 크레딧(report)은 만들기에 성공했을 때만 뺀다. 실패하면 status=failed, error.
- 오래 멈춘 generating(서버 재시작 등, 15분 넘음)은 같은 조합 찾기에서 빼서 다시 만들 수 있게 한다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.credits import ledger
from app.db import get_read_db, get_read_session, get_session

from .build import SEOUL, build_report, last_week, news_window, week_label

log = logging.getLogger("studio_report")
router = APIRouter(prefix="/api/v1/studio", tags=["studio-report"])

MY_CODES_SQL = """SELECT btrim(symbol) AS code FROM user_stocks WHERE user_id = :u AND deleted_at IS NULL"""
SAME_SQL = """SELECT id, status FROM studio_items
WHERE user_id = :u AND kind = 'report' AND period_start = :mon AND expires_at > now() AND deleted_at IS NULL
  AND (status = 'ready' OR (status IN ('queued', 'generating') AND created_at > now() - interval '15 minutes'))
  AND (SELECT array_agg(btrim(x) ORDER BY btrim(x)) FROM unnest(symbols) x) = CAST(:codes AS text[])
  AND coalesce((content->>'market_on')::boolean, false) = :market
  AND (NOT :partial OR (created_at AT TIME ZONE 'Asia/Seoul')::date = :today)
ORDER BY created_at DESC LIMIT 1"""
INSERT_SQL = """INSERT INTO studio_items (user_id, kind, trigger, status, title, period_start, period_end, symbols, content)
VALUES (:u, 'report', 'request', 'generating', :title, :mon, :fri, CAST(:codes AS char(6)[]), CAST(:content AS jsonb))
RETURNING id"""
READY_SQL = """UPDATE studio_items SET status = 'ready', content = CAST(:content AS jsonb), sources = CAST(:sources AS jsonb),
  credits_used = GREATEST(credits_used, :credits), ready_at = now(), error = NULL WHERE id = :id"""   # 다시 만들어도 이미 쓴 크레딧 기록은 남긴다
FAILED_SQL = "UPDATE studio_items SET status = 'failed', error = :error WHERE id = :id"


class ReportRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=30)
    market: bool = False


def _uid(current: dict) -> int:
    try:
        return int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _llm():
    """흐름 문장 LLM. 키가 없으면 None → 코드 문장으로 만든다."""
    import os
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        return None
    from .story import openai_call
    return openai_call


def generate(item_id: int, user_id: int, codes: list[str], market: bool, today=None, llm="default") -> None:
    """백그라운드: 보고서를 만들고 저장·크레딧 차감. 실패하면 failed."""
    llm = _llm() if llm == "default" else llm
    try:
        with get_read_session() as db:
            content = build_report(db, user_id, codes, today=today, market=market, llm=llm)
        sources = [{"no": s["no"], "ref": s["ref"]} for s in content.get("sources", [])]
        with get_session() as db:
            charged = ledger.spend(db, user_id, ledger.cost("report"), "report", "studio_item", item_id)
            db.execute(text(READY_SQL), {"id": item_id, "content": json.dumps({**content, "market_on": market}, ensure_ascii=False, default=str),
                                         "sources": json.dumps(sources, ensure_ascii=False), "credits": charged})
        log.info("report ready item=%s user=%s stocks=%s meta=%s", item_id, user_id, len(content["stocks"]), content.get("story_meta"))
    except Exception as exc:
        log.exception("report failed item=%s user=%s", item_id, user_id)
        try:
            with get_session() as db:
                db.execute(text(FAILED_SQL), {"id": item_id, "error": f"{type(exc).__name__}"[:200]})
        except Exception:
            log.exception("report failed-mark failed item=%s", item_id)


@router.post("/reports", status_code=202)
def post_report(body: ReportRequest, tasks: BackgroundTasks, current: dict = Depends(get_current_user),
                db: Session = Depends(get_read_db)):
    user_id = _uid(current)
    codes = sorted(dict.fromkeys(c.strip() for c in body.codes))
    mine = {r[0] for r in db.execute(text(MY_CODES_SQL), {"u": user_id}).all()}
    if set(codes) - mine:
        raise HTTPException(422, detail="내 종목이 아닌 종목이 있어요.")
    now = datetime.now(SEOUL)
    monday, _friday = last_week(now.date())
    _start, end, partial = news_window(monday, now)
    sunday = monday + timedelta(days=6)
    same = db.execute(text(SAME_SQL), {"u": user_id, "mon": monday, "codes": codes, "market": body.market,
                                       "partial": partial, "today": now.date()}).mappings().first()
    if same is not None:
        return {"item_id": str(same["id"]), "status": same["status"], "reused": True}
    db.rollback()
    cost = ledger.cost("report")
    with get_session() as cdb:
        ledger.refresh(cdb, user_id)
        balance = ledger.balance(cdb, user_id)
    if balance < cost:
        raise HTTPException(402, detail="크레딧이 부족해요. 충전하거나 다음 달에 다시 만들어 주세요.")
    with get_session() as wdb:
        item_id = wdb.execute(text(INSERT_SQL), {"u": user_id, "title": week_label(monday)[1], "mon": monday, "fri": sunday,
                                                 "codes": codes, "content": json.dumps({"market_on": body.market})}).scalar()
    tasks.add_task(generate, int(item_id), user_id, codes, body.market)
    return {"item_id": str(item_id), "status": "generating", "reused": False}


# ─── 앞으로 지켜볼 것 → 메모에 추가 (2026-11-24) ───────────
# 보고서·실험실의 제안으로 새 메모를 저장하면 content.added["{종목코드}:{sid}"] = 메모 id 를 남긴다. 화면은 이 값으로 '추가됨'을 보여 준다
WATCH_ADDED_SQL = """UPDATE studio_items
SET content = jsonb_set(coalesce(content, '{}'::jsonb), '{added}',
                        coalesce(content->'added', '{}'::jsonb) || jsonb_build_object(:key, :memo))
WHERE id = :id AND user_id = :u AND kind IN ('report', 'lab')   -- 실험실 '앞으로 지켜볼 것'도 (2026-11-24)
  AND deleted_at IS NULL AND expires_at > now()"""


class WatchAdded(BaseModel):
    key: str = Field(min_length=3, max_length=40, pattern=r"^[0-9A-Z]{6}:[a-z0-9]{1,12}$")   # "000660:f0"
    memo_id: str = Field(min_length=1, max_length=20, pattern=r"^\d+$")


@router.post("/items/{item_id}/watch", status_code=204)
def mark_watch_added(item_id: int, body: WatchAdded, current: dict = Depends(get_current_user)):
    with get_session() as db:
        n = db.execute(text(WATCH_ADDED_SQL), {"id": item_id, "u": _uid(current), "key": body.key, "memo": body.memo_id}).rowcount
    if not n:
        raise HTTPException(404, detail="보고서를 찾을 수 없어요.")
    return Response(status_code=204)
