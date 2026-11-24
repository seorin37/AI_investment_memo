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
# 조건 표지 '시'는 낱말 끝의 '시'가 아닐 때만 ("다시·역시·혹시·당시·동시"의 '시'는 조건이 아니다, 2026-11-09 "지금보다 15%는 다시 갈 거요")
_SI = r"(?<!다)(?<!역)(?<!혹)(?<!당)(?<!동)시(?=\s|$)"
_COND_MARK = rf"[^.?!]*?(?:면|{_SI}|때)"
_UNSUPPORTED = [
    re.compile(r"52\s*주\s*(신)?(저가|고가|최저|최고)" + _COND_MARK),
    re.compile(r"(PBR|PER|PSR|EV/EBITDA)\s*\d" + _COND_MARK, re.IGNORECASE),
    re.compile(r"거래량.{0,6}(터지|급증|폭증|늘)" + _COND_MARK),
    # 기준점 대비 % ("고점에서 30% 빠지면", "여기서 10% 더 빠지면", "최근 바닥에서 10% 넘게 오르면")
    re.compile(r"(지금|현재|평단|매수가|고점|저점|여기|바닥)\w*\s*(보다|대비|에서)?\s*\d+(\.\d+)?\s*%" + _COND_MARK),
    # 거래량 배수·평소 대비 ("거래량 평소 두 배 넘으면")
    re.compile(r"거래량.{0,10}(\d+(\.\d+)?\s*배|[두세네]\s*배|평소|평균|전일|전날)" + _COND_MARK),
    # 52주 표시가 없는 신저가·신고가, 직전 저점·고점, 이동평균선 ("전저점 깨지면", "60일선 넘으면")
    re.compile(r"(신저가|신고가|전저점|전고점|역사적\s*(저점|고점)|최근\s*(저점|고점|바닥)|\d+\s*일\s*(이동평균)?\s*선|이평선|이동평균선)"
               + _COND_MARK),
]
# 기준어 없는 상대 % 조건 ("10% 오르면 체크"). 실적·배당 같은 사업 수치의 변화("영업이익 10% 늘면")와 구분하려고
# % 앞 12자 안에 사업 수치 단어가 있으면 가격 조건으로 보지 않는다. %와 동사 사이 '더·넘게·이상'은 허용 ("10% 더 빠지면")
_RELATIVE_PCT = re.compile(r"\d+(\.\d+)?\s*%\s*(?:(?:더|넘게|이상)\s*)*(오르|올라|내리|내려|빠지|떨어지|하락|상승|급락|급등)" + _COND_MARK)
_NOT_PRICE_SUBJECT = re.compile(r"(이익|매출|실적|배당|수익|금리|환율|이자|점유율|마진|성장|증가|비중|비용|부채)")


def _relative_pct_condition(text: str) -> bool:
    return any(not _NOT_PRICE_SUBJECT.search(text[max(0, m.start() - 12):m.start()]) for m in _RELATIVE_PCT.finditer(text))


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
        # 2026-11-16 '아래로 내려오면'·'위로 올라오면'·'밑으로 빠지면'이 조건으로 잡히지 않아 가격 항목이 빠졌다 (memo_intent_eval_v1 I07)
        # 2026-11-19 '12만 밑이면'·'5만 아래이면': 방향어 뒤 '이면' (코스피 메모 dry-run K05 "엘전 12만 밑이면 산다"가 항목 없이 빠졌다)
        tail = re.match(rf"\s*(?:원\s*)?(?:으로\s*)?(?:가|내려가|올라가|내려오|올라오|떨어지|빠지|오|되|하|이(?=면))?\s*(?:면|{_SI}|때|언제)",
                        text[after:])
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
    if any(p.search(text) for p in _UNSUPPORTED) or _relative_pct_condition(text):
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
    match = re.search(rf"(?:면|{_SI}|때)\s+(.+)$", text)
    return match.group(1).strip() if match else ""


REST_MAX_WORDS = 5
_MORE_CONDITION = re.compile(r"(?:면|(?<!다)(?<!역)(?<!혹)(?<!당)(?<!동)시|때)(?=\s|$|[,.])")


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


# ---------------------------------------------------------------- 상대 가격 조건 풀어 보기 (2026-11-10, 확인 필요 질문용)
# 판정은 바꾸지 않는다 (상대 조건은 계속 확인 필요). 확인 질문의 선택지를 코드가 계산할 수 있게 기준어·%·방향만 꺼낸다.

@dataclass(frozen=True)
class RelativeCondition:
    base: str                    # high(고점) | low(저점·바닥) | current(지금·현재·여기, 기준어 없는 %) | cost(평단·매수가)
    pct: float                   # 기준값에서 몇 % (0이면 기준값 그대로: "전고점 뚫으면", "신저가 찍으면")
    direction: str | None        # below | above | None(방향을 못 찾음)
    base_word: str               # 문장에 쓰인 기준어 ("최근 고점"). 기준어 없는 %면 ""


_BASES = [  # 앞에 있을수록 먼저 본다 (긴 말 먼저)
    ("high", r"52\s*주\s*(?:신)?(?:고가|최고가?)|전고점|신고가|역사적\s*고점|최근\s*고점|고점|꼭지"),
    ("low", r"52\s*주\s*(?:신)?(?:저가|최저가?)|전저점|신저가|역사적\s*저점|최근\s*(?:저점|바닥)|저점|바닥"),
    ("cost", r"평단가?|평균\s*단가|매수가|산\s*가격|매입가"),
    ("current", r"지금|현재가?|여기"),
]
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|퍼센트|프로)")
_DOWN = re.compile(r"빠지|빠져|떨어지|떨어져|내리|내려|하락|급락|깨지|깨면|이탈|밀리")
# '넘게'(오타 '넘넘게' 포함)는 정도 표현이라 방향어가 아니다 (2026-11-10 P042-L3 "고점 대비 20% 넘넘게 빠지면"을 위로 읽었다).
# '찍으면'은 방향이 없다 (신고가·신저가는 기준어로 정한다)
_UP = re.compile(r"오르|올라|상승|급등|뚫|(?<!넘)넘(?![넘게])|돌파")


def parse_relative(text: str) -> RelativeCondition | None:
    """"고점에서 30% 넘게 빠지면" → (high, 30, below, "고점"). 기준어도 %도 없으면 None.
    방향은 기준어·% 뒤의 첫 방향어로 정한다. '넘게'는 정도 표현이라 방향어로 보지 않는다.
    신고가·신저가처럼 방향어가 없으면 고점은 위로, 저점은 아래로 본다."""
    found = None                 # 고점·저점·평단을 '지금'보다 먼저 본다 ("지금 고점 대비 30%"의 기준은 고점)
    hits = [(base, m) for base, pattern in _BASES if (m := re.search(pattern, text))]
    specific = [h for h in hits if h[0] != "current"]
    if specific or hits:
        found = min(specific or hits, key=lambda h: h[1].start())
    pct = _PCT.search(text, found[1].end() if found else 0)
    if found is None and pct is None:
        return None
    base, word = (found[0], re.sub(r"\s+", " ", found[1].group(0))) if found else ("current", "")
    tail_from = pct.end() if pct else found[1].end()
    tail = text[tail_from:]
    down, up = _DOWN.search(tail), _UP.search(tail)
    direction = None
    if down and (not up or down.start() < up.start()):
        direction = "below"
    elif up:
        direction = "above"
    elif base in ("high", "low") and pct is None:
        direction = "above" if base == "high" else "below"
    return RelativeCondition(base, float(pct.group(1)) if pct else 0.0, direction, word)