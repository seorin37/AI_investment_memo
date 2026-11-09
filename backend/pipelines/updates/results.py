"""결과 저장: DB가 아니라 results/updates/run_<실행시각>/ 폴더의 파일로만 남긴다.

cards.jsonl  : 만들어진 카드(UpdateDraft) 한 줄에 한 건. 나중에 DB에 넣을 내용과 같은 모양
report.md    : 사람이 읽는 보고서 (후보 표, LLM 카드, 검사 결과)
summary.json : 집계 (유사도 분포, 처리 결과, 검사 실패 코드, 토큰 사용량)
candidates.csv: 후보 전체(임계값 아래 포함) + 비어 있는 '관련(O/X)' 열. 사람이 채우면 calibrate가 임계값을 계산한다
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from ..common.config import REPO_ROOT
from .models import Candidate, TrackingItem, UpdateDraft

RESULTS_ROOT = "results/updates"


def new_run_dir(root: str | Path | None = None, now: datetime | None = None) -> Path:
    base = Path(root) if root else REPO_ROOT / RESULTS_ROOT
    run = base / f"run_{(now or datetime.now()):%Y%m%d_%H%M%S}"
    run.mkdir(parents=True, exist_ok=False)
    return run


def draft_to_dict(d: UpdateDraft) -> dict:
    return {
        "item_id": d.item.item_id, "symbol": d.item.symbol, "item_type": d.item.type,
        "description": d.item.description, "category": d.item.category,
        "memo_text": d.item.memo_text, "company_name": d.item.company_name,
        "update_type": d.type, "title": d.title, "summary": d.summary, "reason": d.reason,
        "sources": [{"ref": r, "quote": q} for r, q in d.sources],
        "related_news": [{"ref": r, "title": t} for r, t in d.related_news],
        "price_state": d.price_state, "details": d.details, "observed_trade_date": d.observed_trade_date,
        "origin": d.origin,
    }


def write_results(run_dir: Path, drafts: list[UpdateDraft], report: str, summary: dict) -> None:
    with (run_dir / "cards.jsonl").open("w", encoding="utf-8") as f:
        for d in drafts:
            f.write(json.dumps(draft_to_dict(d), ensure_ascii=False, default=str) + "\n")
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


CANDIDATE_COLUMNS = ["item_id", "symbol", "category", "항목", "메모 문장", "종류", "ref", "날짜", "제목", "내용(앞부분)", "유사도", "관련(O/X)"]


def write_candidates_csv(run_dir: Path, rows: list[tuple[TrackingItem, Candidate]]) -> Path:
    """항목×후보 한 줄씩. 엑셀에서 바로 열리도록 utf-8-sig로 쓴다. 마지막 열 '관련(O/X)'을 사람이 채운다."""
    path = run_dir / "candidates.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CANDIDATE_COLUMNS)
        for item, c in rows:
            kind = "news_chunks" if c.doc == "chunk" else c.kind     # 원문 청크 후보는 calibrate가 따로 센다
            w.writerow([item.item_id, item.symbol, item.category, item.description, item.memo_text, kind, c.ref,
                        c.date, c.title, (c.text or "").replace("\n", " ")[:500], f"{c.similarity:.4f}", ""])
    return path