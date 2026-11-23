"""스튜디오 만든 항목 (studio_items, 0019) — 목록·삭제·실험실 결과 저장 (2026-11-23).

- 목록은 내 것 중 만료(expires_at) 전인 것만, 최근 것부터.
- 실험실은 LLM 답이 나왔을 때만 저장한다 (규칙 대체 답은 저장하지 않는다 — 크레딧 차감과 같은 기준).
- 주간보고서·오디오는 아직 생성 백엔드가 없어 여기서 만들지 않는다.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from sqlalchemy import text

# 실험실 조건 4칸 순서 (프론트 mockLabVars·routes.MACRO_TEXT와 같은 순서). 제목은 괄호를 뺀 이름
LAB_VAR_NAMES = ("원/달러 환율", "국제유가", "한국 기준금리", "미국 10년물 국채금리")

LIST_SQL = """SELECT id, kind, status, title, symbols, content, credits_used, created_at, expires_at
FROM studio_items WHERE user_id = :uid AND expires_at > now() ORDER BY created_at DESC, id DESC"""

DELETE_SQL = "DELETE FROM studio_items WHERE id = :id AND user_id = :uid"

INSERT_LAB_SQL = """INSERT INTO studio_items (user_id, kind, trigger, status, title, symbols, content, credits_used, ready_at)
VALUES (:uid, 'lab', 'request', 'ready', :title, ARRAY[:symbol]::char(6)[], CAST(:content AS jsonb), :credits, now())
RETURNING id"""


def lab_title(name: str, dirs: list[str]) -> str:
    """프론트 labTitle과 같은 모양: '삼성전자 · 원/달러 환율 하락·한국 기준금리 상승 실험'."""
    picked = [f"{n} {d}" for n, d in zip(LAB_VAR_NAMES, dirs) if d != "유지"]
    return f"{name} · {'·'.join(picked)} 실험"


def days_left(expires_at: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return max(0, math.ceil((expires_at - now).total_seconds() / 86400))


def _row(r, now: datetime | None = None) -> dict:
    content = r["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return {"id": str(r["id"]), "kind": r["kind"], "status": r["status"], "title": r["title"],
            "symbols": [s.strip() for s in (r["symbols"] or [])], "content": content or {},
            "credits_used": int(r["credits_used"] or 0), "created_at": r["created_at"], "expires_at": r["expires_at"],
            "days_left": days_left(r["expires_at"], now)}


def list_items(db, user_id: int, now: datetime | None = None) -> list[dict]:
    return [_row(r, now) for r in db.execute(text(LIST_SQL), {"uid": user_id}).mappings().all()]


def delete_item(db, user_id: int, item_id: int) -> bool:
    return db.execute(text(DELETE_SQL), {"id": item_id, "uid": user_id}).rowcount > 0


def save_lab(db, user_id: int, stock_code: str, name: str, dirs: list[str], groups: list, credits: int) -> str:
    content = {"stock_code": stock_code, "name": name, "dirs": list(dirs), "groups": groups}
    new_id = db.execute(text(INSERT_LAB_SQL), {"uid": user_id, "title": lab_title(name, dirs), "symbol": stock_code,
                                               "content": json.dumps(content, ensure_ascii=False),
                                               "credits": int(credits)}).scalar()
    return str(new_id)
