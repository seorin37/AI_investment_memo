"""AI 오디오(내 종목 라디오) API (2026-11-24, 0019 studio_items·audio_assets).

- GET  /api/v1/studio/audio/options   만들기 시트: 내 종목마다 기간별 새 업데이트 수 · 직전 거래일 · 크레딧
- POST /api/v1/studio/audio           {codes, period, market} → studio_items(kind=audio, queued)에 넣고 응답 뒤 백그라운드로 만든다
- GET  /api/v1/studio/audio/{id}      상태(queued → generating → ready/failed)와 ready면 플레이어 내용(content)
- GET  /api/v1/studio/audio/{id}/file 음성 파일 (audio_assets.storage_path = 레포 data/studio_audio/ 기준 상대 경로, 예: 42/episode.mp3)

- 크레딧(audio)은 ready가 됐을 때만 뺀다. 실패하면 status=failed, error에 이유 이름만.
- 같은 날·같은 종목·같은 기간·같은 증시 칸이면 이미 만든 것(또는 15분 안에 만드는 중인 것)을 돌려준다(크레딧 안 씀).
  카드는 그날 계속 붙을 수 있어서 다음 날에는 새로 만든다.
- 고른 종목에 그 기간 새 소식이 없고 증시 요약도 끄면 만들지 않는다 (422, 크레딧 안 씀).
- 대본 프롬프트는 configs/studio_audio_prompt.md. 서버는 처음 읽은 것을 기억하므로 고치면 서버를 다시 켠다.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.credits import ledger
from app.db import get_read_db, get_read_session, get_session

from .collect import PERIODS, SEOUL, audio_options, collect_brief, period_range
from .episode import NoUpdatesError, flatten, text_hash, to_content, write_script
from .prompt import config

log = logging.getLogger("studio_audio")
router = APIRouter(prefix="/api/v1/studio", tags=["studio-audio"])

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "studio_audio"          # .gitignore. 줄마다 합성 캐시는 DATA_DIR/tts_cache

SAME_SQL = """SELECT id, status FROM studio_items
WHERE user_id = :u AND kind = 'audio' AND period_start = :start AND period_end = :end AND expires_at > now() AND deleted_at IS NULL
  AND (status = 'ready' OR (status IN ('queued', 'generating') AND created_at > now() - interval '15 minutes'))
  AND (SELECT array_agg(btrim(x) ORDER BY btrim(x)) FROM unnest(symbols) x) = CAST(:codes AS text[])
  AND coalesce((content->'options'->>'market')::boolean, false) = :market
  AND (created_at AT TIME ZONE 'Asia/Seoul')::date = :today
ORDER BY created_at DESC LIMIT 1"""
INSERT_SQL = """INSERT INTO studio_items (user_id, kind, trigger, status, title, period_start, period_end, symbols, content)
VALUES (:u, 'audio', 'request', 'queued', :title, :start, :end, CAST(:codes AS char(6)[]), CAST(:content AS jsonb))
RETURNING id"""
GENERATING_SQL = "UPDATE studio_items SET status = 'generating' WHERE id = :id"
READY_SQL = """UPDATE studio_items SET status = 'ready', title = :title, content = CAST(:content AS jsonb),
  sources = CAST(:sources AS jsonb), credits_used = GREATEST(credits_used, :credits), ready_at = now(), error = NULL
WHERE id = :id"""
ASSET_SQL = """INSERT INTO audio_assets (studio_item_id, storage_path, mime_type, bytes, duration_sec, provider, voice, text_hash)
VALUES (:id, :path, :mime, :bytes, :dur, :provider, :voice, :hash)"""
FAILED_SQL = "UPDATE studio_items SET status = 'failed', error = :error WHERE id = :id"
ITEM_SQL = """SELECT id, status, title, period_start, period_end, symbols, content, error, credits_used, created_at, ready_at
FROM studio_items WHERE id = :id AND user_id = :u AND kind = 'audio' AND deleted_at IS NULL AND expires_at > now()"""
FILE_SQL = """SELECT a.storage_path, a.mime_type FROM audio_assets a JOIN studio_items s ON s.id = a.studio_item_id
WHERE s.id = :id AND s.user_id = :u AND s.kind = 'audio' AND s.status = 'ready' AND s.deleted_at IS NULL AND s.expires_at > now()
ORDER BY a.created_at DESC LIMIT 1"""


class AudioRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=30)
    period: Literal["전날", "최근 3일", "최근 7일"] = "전날"
    market: bool = True


def _uid(current: dict) -> int:
    try:
        return int(current["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, detail="유효하지 않은 인증 사용자입니다.") from exc


def _llm(cfg: dict):
    """대본 LLM. 키가 없으면 None → 규칙 대본(fallback)."""
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        return None
    from .llm import openai_call
    return lambda msgs: openai_call(msgs, cfg)


def _synth(cfg: dict):
    """Fish Audio. 키·목소리가 없으면 만들지 않는다 (LLM 비용을 쓰기 전에 확인)."""
    from .tts import FishTTS
    synth = FishTTS(cfg["tts"], DATA_DIR / "tts_cache")
    problems = synth.check_ready()
    if problems:
        raise RuntimeError("tts_not_ready: " + " / ".join(problems))
    return synth


def _dur(sec: int) -> str:
    return f"{sec // 60}:{sec % 60:02d}"


def _title(end) -> str:
    return f"{end.month:02d}.{end.day:02d} 내 종목 라디오"


def _mark_failed(item_id: int, error: str) -> None:
    try:
        with get_session() as db:
            db.execute(text(FAILED_SQL), {"id": item_id, "error": error[:200]})
    except Exception:
        log.exception("audio failed-mark failed item=%s", item_id)


def generate(item_id: int, user_id: int, codes: list[str], period: str, market: bool, now: datetime | None = None,
             llm="default", synth="default") -> None:
    """백그라운드: 브리프 → 대본 → 음성 → 저장·크레딧 차감. 실패하면 failed (크레딧 안 씀)."""
    from .tts import synthesize
    cfg = config()
    now = now or datetime.now(SEOUL)
    try:
        with get_session() as db:
            db.execute(text(GENERATING_SQL), {"id": item_id})
        synth = _synth(cfg) if synth == "default" else synth
        llm = _llm(cfg) if llm == "default" else llm
        start, end = period_range(period, now)
        with get_read_session() as db:
            brief = collect_brief(db, user_id, start, end, codes, max_cards_per_stock=cfg["brief"]["max_cards_per_stock"],
                                  max_memos_per_stock=cfg["brief"]["max_memos_per_stock"], now=now, include_market=market)
        script, meta = write_script(brief, llm, cfg)
        lines = flatten(script, cfg)
        out = DATA_DIR / str(item_id)
        res = synthesize(lines, synth, cfg["tts"], out)
        voices = {sp: synth.voice(sp) for sp in ("A", "B")}
        content = to_content(brief, script, lines, res["starts"], res["duration"], meta, cfg)
        content["options"] = {"codes": [s.code for s in brief.stocks], "period": period, "market": market}
        content["meta"] = f"오디오 · {len(brief.stocks)}종목 · {period} · {_dur(content['dur'])}"
        content["audio"] = {"mime": res["mime"], "bytes": res["bytes"], "duration_sec": round(res["duration"], 1)}
        from .llm import model_name
        content["script_meta"] = {"model": model_name(cfg) if llm else None, "tries": meta["tries"],
                                  "usage": meta.get("usage"), "errors": len(meta.get("errors") or [])}
        path = Path(res["path"])
        with get_session() as db:
            charged = ledger.spend(db, user_id, ledger.cost("audio"), "audio", "studio_item", item_id)
            db.execute(text(READY_SQL), {"id": item_id, "title": _title(end), "credits": charged,
                                         "content": json.dumps(content, ensure_ascii=False, default=str),
                                         "sources": json.dumps(content["sources"], ensure_ascii=False, default=str)})
            db.execute(text(ASSET_SQL), {"id": item_id, "path": path.relative_to(DATA_DIR).as_posix(), "mime": res["mime"],
                                         "bytes": res["bytes"], "dur": int(round(res["duration"])), "provider": synth.provider,
                                         "voice": json.dumps(voices), "hash": text_hash(lines, voices, synth.model)})
        log.info("audio ready item=%s user=%s stocks=%s source=%s tries=%s dur=%.0f", item_id, user_id, len(brief.stocks),
                 meta["source"], meta["tries"], res["duration"])
    except NoUpdatesError:
        _mark_failed(item_id, "no_updates")
    except Exception as exc:
        log.exception("audio failed item=%s user=%s", item_id, user_id)
        _mark_failed(item_id, str(exc) if str(exc).startswith("tts_not_ready") else type(exc).__name__)


@router.get("/audio/options")
def get_options(current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    return {**audio_options(db, _uid(current)), "cost": ledger.cost("audio")}


@router.post("/audio", status_code=202)
def post_audio(body: AudioRequest, tasks: BackgroundTasks, current: dict = Depends(get_current_user),
               db: Session = Depends(get_read_db)):
    user_id = _uid(current)
    codes = sorted(dict.fromkeys(c.strip() for c in body.codes))
    now = datetime.now(SEOUL)
    opts = {s["stock_code"]: s for s in audio_options(db, user_id, now)["stocks"]}
    if set(codes) - set(opts):
        raise HTTPException(422, detail="내 종목이 아닌 종목이 있어요.")
    k = list(PERIODS).index(body.period)
    if not body.market and not any(opts[c]["news"][k] for c in codes):
        raise HTTPException(422, detail="고른 종목에 이 기간 새 소식이 없어요. 증시 요약을 켜면 만들 수 있어요.")
    start, end = period_range(body.period, now)
    same = db.execute(text(SAME_SQL), {"u": user_id, "start": start, "end": end, "codes": codes, "market": body.market,
                                       "today": now.date()}).mappings().first()
    if same is not None:
        return {"item_id": str(same["id"]), "status": same["status"], "reused": True}
    db.rollback()
    cost = ledger.cost("audio")
    with get_session() as cdb:
        ledger.refresh(cdb, user_id)
        balance = ledger.balance(cdb, user_id)
    if balance < cost:
        raise HTTPException(402, detail="크레딧이 부족해요. 충전하거나 다음 달에 다시 만들어 주세요.")
    options = {"codes": codes, "period": body.period, "market": body.market}
    with get_session() as wdb:
        item_id = wdb.execute(text(INSERT_SQL), {"u": user_id, "title": _title(end), "start": start, "end": end, "codes": codes,
                                                 "content": json.dumps({"options": options}, ensure_ascii=False)}).scalar()
    tasks.add_task(generate, int(item_id), user_id, codes, body.period, body.market)
    return {"item_id": str(item_id), "status": "queued", "reused": False}


@router.get("/audio/{item_id}")
def get_audio(item_id: int, current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    r = db.execute(text(ITEM_SQL), {"id": item_id, "u": _uid(current)}).mappings().first()
    if r is None:
        raise HTTPException(404, detail="오디오를 찾을 수 없어요.")
    content = r["content"] if not isinstance(r["content"], str) else json.loads(r["content"])
    ready = r["status"] == "ready"
    return {"id": str(r["id"]), "status": r["status"], "title": r["title"], "error": r["error"],
            "period": {"start": r["period_start"], "end": r["period_end"]}, "symbols": [s.strip() for s in r["symbols"] or []],
            "credits_used": int(r["credits_used"] or 0), "created_at": r["created_at"], "ready_at": r["ready_at"],
            "content": content if ready else {"options": (content or {}).get("options")},
            "file_url": f"/api/v1/studio/audio/{r['id']}/file" if ready else None}


@router.get("/audio/{item_id}/file")
def get_audio_file(item_id: int, current: dict = Depends(get_current_user), db: Session = Depends(get_read_db)):
    r = db.execute(text(FILE_SQL), {"id": item_id, "u": _uid(current)}).mappings().first()
    if r is None:
        raise HTTPException(404, detail="오디오 파일을 찾을 수 없어요.")
    path = (DATA_DIR / r["storage_path"]).resolve()
    if not path.is_relative_to(DATA_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, detail="오디오 파일을 찾을 수 없어요.")
    return FileResponse(path, media_type=r["mime_type"], headers={"Cache-Control": "private, max-age=86400"})
