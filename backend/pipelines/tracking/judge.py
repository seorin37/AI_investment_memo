"""문장 판정 (기준표 v0.2 판정 순서).

⓪ 정제 → ① 의미 없음(B7)·광고(B6) → ② 가격 조건(A2/C1/확인 필요) → ③ 종목 표시
→ ④ 문장 전체 범위 밖(B5) → ⑤ 캐시(호출자 주입) → ⑥ 나머지는 LLM 대기(pending_llm).
로직이 확신할 때만 판정하고, 그 밖은 모두 LLM으로 넘긴다.
가격 조건 앞에 다른 내용이 있으면(문장 분리가 덜 된 경우) 가격 항목만 확정해 두고 문장은 LLM에도 넘긴다.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .clean import clean, is_meaningless, strip_filler
from .domain import has_domain_word
from .lexicon import Lexicon
from .price import classify_rest, parse_conditions
from .segment import split_sentences


def _decision_question(text: str) -> bool:
    """판단 질문 표지(tracking_lexicon.yaml decision_question_markers)가 있는지. 질문 답 단계(updates.decision_note)와 같은 목록."""
    from ..updates.decision_note import is_decision_question
    return is_decision_question(text)

PENDING = "pending_llm"
_URL = re.compile(r"https?://|www\.|bit\.ly", re.IGNORECASE)
_CONDITIONAL_QUESTION_END = re.compile(r"(?:까(?:요)?|나(?:요)?|고민\s*중(?:이야)?|고민돼|고민이야|\?)\s*[.!?~]*$")
_ALERT_REQUEST = re.compile(r"알림|알려\s*(?:줘|주|줄|달)")
# 광고·범위 밖은 짧은 조각에서만 확정한다. 긴 조각은 문장 분리가 덜 돼 다른 내용이 섞였을 수 있어 LLM에 넘긴다.
SPAM_MAX_WORDS = 10
OUT_OF_SCOPE_MAX_WORDS = 6


@dataclass
class Judgment:
    sentence_index: int
    text: str
    span: tuple[int, int]
    cleaned_text: str
    flags: list[str]
    decision: str                     # normal | partial | full_fallback | needs_confirmation | pending_llm
    category: str | None = None
    reason_code: str | None = None
    symbols: list[str] = field(default_factory=list)
    other_symbol: str | None = None
    items: list[dict] = field(default_factory=list)
    context_note: str | None = None
    judged_by: str = "rule"           # rule | llm | cache | pending
    resolved_reference: str | None = None
    merge_into: dict | None = None    # 앞 문장 항목에 합칠 때 {"sentence_index", "item_index"}
    sub_sentences: list[str] = field(default_factory=list)  # 덜 나뉜 조각을 LLM이 다시 나눈 결과 (화면 표시용)
    confidence: float | None = None
    # 실험(2026-11-16, docs/memo-intent-redesign-proposal.md): 한 번 답하면 끝나는 질문 [{"question", "kind": explain|check}].
    # 추적 항목(items)과 따로 둔다. 지시문 configs/tracking_judge_prompt_intent.md가 채운다 (기존 지시문은 비워 둔다)
    asks: list[dict] = field(default_factory=list)
    # 2026-11-25: "140만원 넘으면 살까?"처럼 질문의 전제로 쓴 가격 조건 (price_item 모양). 추적하지 않고, 답 카드에서
    # "140만원 넘으면 알려드릴까요?" 새 메모 제안으로만 쓴다 (app/board/analysis.py → 질문 항목의 가격 칸)
    ask_alerts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["span"] = list(self.span)
        return data


def price_item(direction: str, price: int) -> dict:
    word = "아래로" if direction == "below" else "위로"
    return {"type": f"price_{direction}", "description": f"{price:,}원 {word}", "keywords": None,
            "price_threshold": price, "time_hint": None}


def judge_sentence(index: int, text: str, span: tuple[int, int], memo_symbol: str, lex: Lexicon) -> Judgment:
    cleaned = clean(text, lex)
    j = Judgment(index, text, span, cleaned.text, list(cleaned.flags), PENDING, judged_by="pending")
    symbols = lex.find_symbols(cleaned.text)
    j.symbols = symbols or [memo_symbol]
    others = [s for s in symbols if s != memo_symbol]
    j.other_symbol = others[0] if others else None

    def decide(decision, category, reason, items=(), note=None):
        j.decision, j.category, j.reason_code = decision, category, reason
        j.items, j.context_note, j.judged_by = list(items), note, "rule"
        return j

    # ① 의미 없음·광고
    if is_meaningless(cleaned.text, lex):
        return decide("full_fallback", "B7", "MEANINGLESS")
    # 욕을 지우고 나니 종목 이름만 남았다 ("삼성 개씨발") → 추적할 대상 없는 감정
    if "profanity" in cleaned.flags and is_meaningless(lex.alias_pattern.sub(" ", cleaned.text), lex):
        return decide("full_fallback", "B1", "EMOTION")
    if any(w in cleaned.text for w in lex.spam_strong) or (
        _URL.search(cleaned.text) and any(w in cleaned.text for w in lex.spam_with_link)
    ):
        # 종목·금융 내용이 같이 있으면(문장 분리가 덜 된 경우) 버리지 않고 LLM에 넘긴다
        if (not symbols and not any(w in cleaned.text for w in lex.finance_words)
                and len(cleaned.text.split()) <= SPAM_MAX_WORDS):
            return decide("full_fallback", "B6", "SPAM")
        j.flags.append("spam_suspect")
        return j

    # ② 가격 조건 (한 문장에 여러 개일 수 있다)
    conditions = parse_conditions(cleaned.text, lex)
    # 가격이 질문의 전제일 수 있다. 알림 요청이 없는 "140만원 넘으면 살까?"는 ask로 보낸다.
    tracked_conditions = [
        c for c in conditions
        if not (_CONDITIONAL_QUESTION_END.search(c.rest)
                and not _ALERT_REQUEST.search(c.rest)
                and (classify_rest(c.rest, lex) == "action" or _decision_question(c.rest)))
    ]
    if len(tracked_conditions) != len(conditions):
        j.items = [price_item(c.direction, c.price) for c in tracked_conditions if c.kind == "condition"]
        j.ask_alerts = [price_item(c.direction, c.price) for c in conditions
                        if c not in tracked_conditions and c.kind == "condition"]
        return j
    if conditions and conditions[0].kind == "unsupported":
        return decide("needs_confirmation", None, "UNSUPPORTED_CONDITION", note=conditions[0].rest or None)
    if conditions:
        items = [price_item(c.direction, c.price) for c in conditions]
        rests = [strip_filler(c.rest, lex) for c in conditions]
        note = ", ".join(r for r in rests if r) or None
        kinds = [classify_rest(c.rest, lex) for c in conditions]
        prefix = lex.alias_pattern.sub(" ", cleaned.text[:conditions[0].start])
        if not is_meaningless(prefix, lex) or "other" in kinds:
            # 앞에 다른 내용이 있거나 조건 뒤에 다른 조건·내용이 더 있다 → 가격 항목만 확정, 나머지는 LLM
            j.items, j.context_note = items, note
            return j
        if "action" in kinds:
            return decide("partial", "C1", "USER_ACTION", items, note=note)
        return decide("normal", "A2", "PRICE", items)

    # ④ 문장 전체가 범위 밖 (종목 별칭·금융 단어가 하나도 없을 때만)
    if (any(w in cleaned.text for w in lex.out_of_scope) and not symbols
            and not any(w in cleaned.text for w in lex.finance_words)
            and len(cleaned.text.split()) <= OUT_OF_SCOPE_MAX_WORDS):
        return decide("full_fallback", "B5", "OUT_OF_SCOPE")

    # ④-2 종목명·도메인 단어·요청 표지가 하나도 없는 짧은 문장 ("이상규 맥북 개쓰레기") → 범위 밖 (API 없이)
    if (lex.domain_vocab and not symbols and len(cleaned.text.split()) <= OUT_OF_SCOPE_MAX_WORDS
            and not cleaned.text.rstrip().endswith("?")
            and not any(m in cleaned.text for m in lex.intent_markers)
            and not any(w in cleaned.text for w in lex.finance_words)
            and not has_domain_word(cleaned.text, lex.domain_vocab)
            and not _decision_question(cleaned.text)):          # 2026-11-25: "사야하나 고민중이야"·"존버 vs 손절"은 물음표 없어도 판단 질문 → LLM
        j.flags.append("no_domain")
        return decide("full_fallback", "B5", "OUT_OF_SCOPE")

    # ⑥ 나머지는 LLM
    return j


def judge_memo(text: str, memo_symbol: str, lex: Lexicon, cache: dict | None = None) -> list[Judgment]:
    """메모 전체를 문장으로 나눠 로직 판정. cache(정제 문장 → 판정 dict)가 있으면 ⑤로 재사용한다."""
    results = []
    for seg in split_sentences(text, lex):
        j = judge_sentence(seg.index, seg.text, seg.span, memo_symbol, lex)
        if j.decision == PENDING and cache and j.cleaned_text in cache:
            hit = cache[j.cleaned_text]
            j.decision, j.category, j.reason_code = hit["decision"], hit.get("category"), hit.get("reason_code")
            j.items, j.context_note, j.judged_by = list(hit.get("items", [])), hit.get("context_note"), "cache"
        results.append(j)
    return results
