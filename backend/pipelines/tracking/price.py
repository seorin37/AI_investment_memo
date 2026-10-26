"""가격 조건 추출: 절대 가격 + 방향어 + 조건 표지("면/시/때")를 찾는다.

지원하지 않는 조건(가격 범위, 현재가 대비 %, 52주 신저가·신고가, PBR·PER 배수, 거래량 급증)은
UNSUPPORTED로 돌려 "확인 필요"가 되게 한다. 예측("20만 넘을 듯")은 조건 표지가 없어 가격 조건이 아니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .lexicon import Lexicon


@dataclass(frozen=True)
class Amount:
    value: int
    start: int
    end: int


@dataclass(frozen=True)
class PriceResult:
    kind: str                    # "condition" | "unsupported"
    direction: str | None = None  # "below" | "above"
    price: int | None = None
    rest: str = ""               # 조건 표지 뒤에 남은 말 (사용자 행동·알림 요청)
    start: int = 0               # 가격 표현이 시작하는 위치 (앞에 다른 내용이 있는지 보려고)


_KO_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
# 단위가 붙은 수(만·천·k·원)나 네 자리 이상 수만 가격으로 본다. 뒤에 주·%·배·년 등이 오면 가격이 아니다.
_NOT_PRICE_AFTER = re.compile(r"\s*(주|%|퍼센트|배|년|분기|나노|개|명|일|시간|위|등)")
_AMOUNT_PATTERNS = [
    (re.compile(r"(\d+)\s*만\s*(\d+)\s*천"), lambda m: int(m.group(1)) * 10000 + int(m.group(2)) * 1000),
    (re.compile(r"(\d+(?:\.\d+)?)\s*만(?![가-힣])|(\d+(?:\.\d+)?)\s*만(?=\s*원|선|에|\s)"),
     lambda m: int(float(m.group(1) or m.group(2)) * 10000)),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[kK](?![a-zA-Z])"), lambda m: int(float(m.group(1)) * 1000)),
    (re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}"), lambda m: int(m.group(0).replace(",", ""))),
    (re.compile(r"([일이삼사오육칠팔구])십?만"), lambda m: _KO_DIGIT[m.group(1)] * (100000 if "십" in m.group(0) else 10000)),
]
# 지원하지 않는 조건. 뒤에 조건 표지(면·시·때)가 있어야 조건으로 본다 ("PER 5배는 싸다"는 감상이지 조건이 아니다).
_COND_MARK = r"[^.?!]*?(?:면|시(?=\s|$)|때)"
_UNSUPPORTED = [
    re.compile(r"52\s*주\s*(신)?(저가|고가|최저|최고)" + _COND_MARK),
    re.compile(r"(PBR|PER|PSR|EV/EBITDA)\s*\d" + _COND_MARK, re.IGNORECASE),
    re.compile(r"거래량.{0,6}(터지|급증|폭증|늘)" + _COND_MARK),
    re.compile(r"(지금|현재|평단|매수가|고점|저점)\w*\s*(보다|대비|에서)?\s*\d+(\.\d+)?\s*%" + _COND_MARK),
]


def find_amounts(text: str) -> list[Amount]:
    taken: list[tuple[int, int]] = []
    amounts: list[Amount] = []
    for pattern, to_value in _AMOUNT_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(s < end and start < e for s, e in taken):
                continue
            if _NOT_PRICE_AFTER.match(text, end):
                continue
            taken.append((start, end))
            amounts.append(Amount(to_value(match), start, end))
    return sorted(amounts, key=lambda a: a.start)


def _condition_after(text: str, pos: int, words: tuple[str, ...]) -> tuple[int, int] | None:
    """pos 뒤 짧은 범위에서 방향어 + 조건 표지를 찾는다. (방향어 시작, 조건 끝)."""
    window = text[pos:pos + 16]
    for word in sorted(words, key=len, reverse=True):
        idx = window.find(word)
        if idx < 0:
            continue
        after = pos + idx + len(word)
        if word.endswith("면"):
            return pos + idx, after
        tail = re.match(r"\s*(?:원\s*)?(?:으로\s*)?(?:가|내려가|올라가|떨어지|오|되|하)?\s*(?:면|시(?=\s|$)|때|언제)", text[after:])
        if tail:
            return pos + idx, after + tail.end()
    return None


def parse_price(text: str, lex: Lexicon) -> PriceResult | None:
    """첫 가격 조건 (호환용). 여러 조건은 parse_conditions."""
    found = parse_conditions(text, lex)
    return found[0] if found else None


def parse_conditions(text: str, lex: Lexicon) -> list[PriceResult]:
    """문장 안의 가격 조건을 모두 찾는다 ("30만 뚫으면 익절, 25만 깨지면 손절" → 2개).
    각 조건의 rest는 그 조건 뒤에서 다음 가격 표현 전까지의 말이다. 미지원 조건이면 [unsupported] 하나."""
    if any(p.search(text) for p in _UNSUPPORTED):
        return [PriceResult("unsupported", rest=_rest_after_condition(text))]
    amounts = find_amounts(text)
    if len(amounts) >= 2 and re.search(r"사이|~|∼|부터", text):
        return [PriceResult("unsupported", rest=_rest_after_condition(text))]
    results: list[PriceResult] = []
    for k, amount in enumerate(amounts):
        nxt = amounts[k + 1].start if k + 1 < len(amounts) else len(text)
        for direction, words in (("below", lex.price_below), ("above", lex.price_above)):
            found = _condition_after(text, amount.end, words)
            if found and found[1] <= nxt + 16:
                results.append(PriceResult("condition", direction, amount.value,
                                           text[found[1]:nxt].strip(" ,"), amount.start))
                break
    return results


def _rest_after_condition(text: str) -> str:
    match = re.search(r"(?:면|시|때)\s+(.+)$", text)
    return match.group(1).strip() if match else ""


REST_MAX_WORDS = 5
_MORE_CONDITION = re.compile(r"(?:면|시|때)(?=\s|$|[,.])")


def classify_rest(rest: str, lex: Lexicon) -> str:
    """조건 뒤 말: 'action'(사용자 행동, C1) / 'notify'(알림 요청, A2) / 'none'(아무 말 없음) /
    'other'(다른 조건·내용이 더 있음 → 로직이 확정하지 않고 LLM에 넘긴다)."""
    words = [w.strip(".,!?~") for w in rest.split() if w.strip(".,!?~")]
    if not words:
        return "none"
    if len(words) > REST_MAX_WORDS or _MORE_CONDITION.search(rest):
        return "other"
    if any(w.startswith(lex.action_words) for w in words):
        return "action"
    if all(w.startswith(lex.notify_words) for w in words):
        return "notify"
    return "other"
