"""판단 질문(사야 되나·오르나·가격 괜찮아?)의 답 끝에 붙이는 고정 문장 (2026-11-23, docs/memo-decision-question-design.md).

LLM이 쓰지 않고 코드가 붙인다 — 문구가 매번 같고, 빠지지 않는다.
붙이는 조건: 질문 원문(item.memo_text)에 configs/tracking_lexicon.yaml의 decision_question_markers 중 하나가 있을 때.
설명 질문("HBM이 뭐야?")·원인 확인("~때문에 떨어졌던데")에는 붙이지 않는다.
설정(cfg)에 decision_note: false 를 주면 끈다.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from ..common.config import resolve_path

LEXICON_PATH = "configs/tracking_lexicon.yaml"


@lru_cache(maxsize=1)
def _load() -> tuple[tuple[str, ...], str]:
    with resolve_path(LEXICON_PATH).open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    groups = raw.get("decision_question_markers") or []
    markers = tuple(str(m) for g in groups for m in (g if isinstance(g, list) else [g]))
    return markers, str(raw.get("decision_note") or "").strip()


def is_decision_question(text: str) -> bool:
    markers, _ = _load()
    t = (text or "").replace("\n", " ") + " "
    return any(m in t for m in markers)


def add_decision_note(draft, cfg: dict | None = None) -> bool:
    """판단 질문이면 답 문단(explanation, 없으면 summary) 끝에 고정 문장을 붙인다. 붙였으면 True."""
    if (cfg or {}).get("decision_note") is False:
        return False
    _, note = _load()
    if not note or not is_decision_question(getattr(draft.item, "memo_text", "")):
        return False
    field = "explanation" if draft.explanation else "summary"
    body = (getattr(draft, field) or "").rstrip()
    if note in body:
        return False
    setattr(draft, field, f"{body} {note}".strip())
    draft.decision_note = note
    return True
