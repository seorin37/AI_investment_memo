"""입력 → LLM → 검사 → (재시도) → (일반 경로로 대체) → 앱·웹 결과 화면 형식."""
from __future__ import annotations

import logging
from typing import Callable

from .prompt import PROMPT_VERSION, StockCtx, messages
from .rules import VARS, fallback
from .schema import LEAF_FIELDS, check

log = logging.getLogger("studio_lab")

THEORY_BASE = "일반적인 경로 · 회사 공시 없음"
LLMCall = Callable[[list[dict]], dict]


def run_lab(stock: StockCtx, dirs: list[str], llm: LLMCall, macro: list[tuple[str, str]] | None = None,
            as_of: str = "") -> dict:
    """dirs: VARS 순서의 상승·유지·하락. 바뀐 조건이 하나 이상이어야 한다."""
    picked = [(index, VARS[index], direction) for index, direction in enumerate(dirs) if direction != "유지"]
    if not picked:
        raise ValueError("바꾼 가정이 없어요")
    changed = [(var, direction) for _, var, direction in picked]
    allowed = stock.facts + [f"{name} {value}" for name, value in macro or []]
    meta = {"prompt": PROMPT_VERSION, "tries": 0, "errors": [], "usage": {}}
    answer, fix, source = None, None, "rules"

    for attempt in (1, 2):
        meta["tries"] = attempt
        try:
            raw = llm(messages(stock, changed, macro, as_of, fix))
        except Exception as exc:
            meta["errors"].append(f"try{attempt}: {type(exc).__name__}")
            log.warning("lab llm error %s try=%s: %s", stock.stock_code, attempt, type(exc).__name__)
            continue
        errors = check(raw, changed, allowed)
        if not errors:
            answer, source, meta["usage"] = raw, "llm", raw.get("_usage", {})
            break
        meta["errors"].append(f"try{attempt}: " + " | ".join(errors))
        fix = errors
    if answer is None:
        answer = fallback(stock.financial, changed)
        log.warning("lab fallback %s %s", stock.stock_code, meta["errors"])

    groups = []
    for (index, _, direction), path in zip(picked, answer["paths"]):
        leaves = [{**{name: str(leaf[name]).strip() for name in LEAF_FIELDS}, "ev": False, "base": THEORY_BASE}
                  for leaf in path["leaves"]]
        groups.append({"i": index, "d": direction, "leaves": leaves})
    return {"stock_code": stock.stock_code, "name": stock.name, "groups": groups, "source": source, "_meta": meta}
