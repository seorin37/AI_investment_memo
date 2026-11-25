"""LLM 2차 판정 인터페이스 — 프롬프트 생성, 응답 검증, 판정 반영. 실제 호출은 하지 않는다.

메모 하나의 로직 미판정 문장을 한 번에 묶어 보낸다(메모당 1회). 앞뒤 문장도 맥락으로 함께 보내
"그거" 같은 대명사를 보완하게 한다. 응답은 JSON 배열이고, 검증을 통과하지 못하면 해당 문장은
"확인 필요"로 둔다(조용히 버리지 않는다).
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Callable, Protocol

from ..common.config import resolve_path

from .judge import PENDING, Judgment

DECISIONS = {"normal", "partial", "full_fallback", "needs_confirmation"}
CATEGORIES = {f"A{i}" for i in range(1, 6)} | {f"B{i}" for i in range(1, 11)} | {f"C{i}" for i in range(1, 6)}
ITEM_TYPES = {"topic", "price_below", "price_above"}

# 2026-11-25 기본값을 v2로: '사야 되나·오르나·가격 괜찮아' 같은 판단 질문을 반려하지 않고 사실 질문(ask)으로 한 번 답한다
# (팀장님 요청, docs/memo-decision-question-design.md). 운영 서버에 TRACKING_PROMPT_PATH가 없어 옛 지시문으로 돌며 질문을 버리고 있었다.
PROMPT_PATH = "configs/tracking_judge_prompt_intent_v2.md"
# 환경변수로 지시문을 바꿔 끼운다 (예: 옛 지시문 configs/tracking_judge_prompt.md). 없으면 위 기본값.
PROMPT_ENV = "TRACKING_PROMPT_PATH"
ASK_KINDS = {"explain", "check"}


def prompt_path() -> str:
    return os.getenv(PROMPT_ENV) or PROMPT_PATH


@lru_cache(maxsize=4)
def load_guide(path: str = PROMPT_PATH) -> str:
    """판정 지시문(프롬프트)을 설정 파일에서 읽는다. 코드 수정 없이 고치고, 평가셋과 겹치지 않게 관리한다(WO-028)."""
    return resolve_path(path).read_text(encoding="utf-8").strip()


class LLMJudge(Protocol):
    def __call__(self, prompt: str) -> str: ...


def build_prompt(memo_symbol: str, stock_name: str, judgments: list[Judgment], guide: str | None = None) -> str:
    lines = [guide or load_guide(prompt_path()), "", f"메모 종목: {stock_name} ({memo_symbol})", "문장 (판정 대상은 [판정], 나머지는 맥락):"]
    for j in judgments:
        mark = "[판정]" if j.decision == PENDING else "[맥락]"
        lines.append(f"{j.sentence_index}. {mark} {j.cleaned_text}")
    return "\n".join(lines)


REASON = {
    "A1": "TOPIC", "A2": "PRICE", "A3": "EVENT", "A4": "QUESTION", "A5": "HYPOTHESIS",
    "B1": "EMOTION", "B2": "PAST_FACT", "B3": "PRINCIPLE", "B4": "SELF_TODO", "B5": "OUT_OF_SCOPE", "B6": "SPAM",
    "B7": "MEANINGLESS", "B8": "PRICE_GUESS", "B9": "NEGATION", "B10": "OTHER_STOCK",
    "C1": "USER_ACTION", "C2": "EMOTION_MIXED", "C3": "OTHER_STOCK_MIXED", "C4": "PREDICTION_MIXED", "C5": "OUT_OF_SCOPE_MIXED",
}
DECISION_OF = {"A": "normal", "B": "full_fallback", "C": "partial"}


def _expand(row: dict) -> dict:
    """짧은 키(i·cat·dec·items[d,k,t]·merge[s,n]) 응답을 내부 형식으로 바꾼다. 긴 키도 그대로 받는다."""
    if "i" not in row:
        return row
    items = [{"type": it.get("type", "topic"), "description": it.get("d") or it.get("description"),
              "keywords": it.get("k") or it.get("keywords"), "price_threshold": it.get("price_threshold"),
              "time_hint": it.get("t") or it.get("time_hint")} for it in row.get("items") or [] if isinstance(it, dict)]
    merge = row.get("merge")
    asks = [{"question": str(a.get("q") or a.get("question") or "").strip(), "kind": a.get("kind")}
            for a in row.get("ask") or [] if isinstance(a, dict)]
    asks = [a for a in asks if a["question"] and a["kind"] in ASK_KINDS]
    return {"sentence_index": row.get("i"), "category": row.get("cat"), "decision": row.get("dec"), "items": items,
            "asks": asks,
            "merge_into": {"sentence_index": merge.get("s"), "item_index": merge.get("n", 0)} if isinstance(merge, dict) else None,
            "resolved_reference": row.get("ref"), "context_note": row.get("note"), "sub_sentences": row.get("subs"),
            "confidence": row.get("conf", 0)}


def _consistent(row: dict) -> dict:
    """category와 decision이 어긋나면 category를 따른다 (B인데 추적, A인데 버림 같은 모순 제거)."""
    cat = row.get("category")
    if cat in CATEGORIES:
        row["decision"] = DECISION_OF[cat[0]]
        row["reason_code"] = row.get("reason_code") or REASON[cat]
        if row["decision"] == "full_fallback":
            row["items"], row["merge_into"] = [], None
    elif cat is None:
        row["decision"] = "needs_confirmation"
        row["reason_code"] = row.get("reason_code") or "LOW_CONFIDENCE"
    return row


def parse_response(raw: str) -> list[dict]:
    """응답에서 JSON 배열을 꺼내 형식이 맞는 원소만 돌려준다."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    valid = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        row = _consistent(_expand(row))
        if not isinstance(row.get("sentence_index"), int):
            continue
        if row.get("decision") not in DECISIONS:
            continue
        if row.get("category") not in CATEGORIES | {None}:
            continue
        items = row.get("items") or []
        if not all(isinstance(it, dict) and it.get("type") in ITEM_TYPES and it.get("description") for it in items):
            continue
        merge = row.get("merge_into")
        if merge is not None and not (isinstance(merge, dict) and isinstance(merge.get("sentence_index"), int)):
            row["merge_into"] = None
        subs = row.get("sub_sentences")
        row["sub_sentences"] = [s for s in subs if isinstance(s, str) and s.strip()] if isinstance(subs, list) else []
        valid.append(row)
    return valid


def _missing_threshold(item: dict) -> bool:
    """가격 항목인데 조건가가 없거나 양수가 아니다 (상대 가격 조건 "고점 대비 30%"를 LLM이 가격 항목으로 낸 경우)."""
    if not str(item.get("type", "")).startswith("price_"):
        return False
    value = item.get("price_threshold")
    return isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0


def apply_llm(judgments: list[Judgment], rows: list[dict], min_confidence: float = 0.7) -> list[Judgment]:
    """검증된 응답을 대기 문장에 반영한다. 응답이 없거나 확신이 낮은 대기 문장은 확인 필요.
    로직이 미리 넣어 둔 가격 항목(분리가 덜 된 문장)은 지우지 않는다.
    조건가가 빈 가격 항목이 있으면 그 문장은 카드 단계로 넘기지 않고 확인 필요(PRICE_THRESHOLD_MISSING)."""
    by_index = {r["sentence_index"]: r for r in rows}
    for j in judgments:
        if j.decision != PENDING:
            continue
        row = by_index.get(j.sentence_index)
        if row is None or float(row.get("confidence", 0)) < min_confidence:
            j.decision, j.reason_code = "needs_confirmation", "LOW_CONFIDENCE"
            j.judged_by = "llm" if row else "pending"
            continue
        j.decision, j.category, j.reason_code = row["decision"], row.get("category"), row.get("reason_code")
        # 로직이 먼저 확정한 가격 항목은 유지하고, LLM 항목 중 같은 가격 조건은 겹치지 않게 뺀다
        kept = {(it["type"], it.get("price_threshold")) for it in j.items}
        extra = [it for it in row.get("items") or [] if (it["type"], it.get("price_threshold")) not in kept]
        j.items = j.items + extra
        if any(_missing_threshold(it) for it in j.items):
            j.decision, j.reason_code = "needs_confirmation", "PRICE_THRESHOLD_MISSING"
        j.context_note, j.judged_by = row.get("context_note") or j.context_note, "llm"
        j.asks = list(row.get("asks") or [])
        j.resolved_reference, j.confidence = row.get("resolved_reference"), float(row.get("confidence", 0))
        merge = row.get("merge_into")
        j.merge_into = merge if merge and merge["sentence_index"] < j.sentence_index else None
        # 나눈 조각은 원문(정제본) 안에 실제로 있는 문장만 받는다 (LLM이 지어낸 문장 방지)
        j.sub_sentences = [s for s in row.get("sub_sentences", []) if s.strip() in j.cleaned_text]
        if len(j.sub_sentences) < 2:
            j.sub_sentences = []
    return judgments


def judge_with_llm(judgments: list[Judgment], memo_symbol: str, stock_name: str,
                   call: Callable[[str], str] | None) -> list[Judgment]:
    """대기 문장이 있을 때만 call을 1회 호출한다. call이 없으면 그대로 둔다(로직 전용 평가)."""
    if call is None or not any(j.decision == PENDING for j in judgments):
        return judgments
    return apply_llm(judgments, parse_response(call(build_prompt(memo_symbol, stock_name, judgments))))
