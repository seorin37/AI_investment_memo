"""코드 검사 — LLM이 지침을 어겨도 사용자에게 보이지 않게 하는 마지막 관문 (지침서 Ⅴ-1).

형식 / 금지 표현 / 숫자 대조 / 출처 대조 / 확신도. 걸린 이유를 코드 목록으로 돌려준다 (하나라도 있으면 그 답변은 쓰지 않는다).
FACT_OVERLAP은 지침서에 없는 추가 검사(evidence.fact가 근거 글과 너무 다르면 거름)이고 min_fact_overlap=0으로 끌 수 있다.
"""

from __future__ import annotations

import re

from .models import Answer, Card, Evidence

_TAG = re.compile(r"\[E\d+\]")
_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?")
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(조|억|만|천)?\s*(%|퍼센트)?")
_UNIT = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
# 한국식으로 나눠 쓴 금액 ("14조 1034억 6648만 8000원", "5조7천921억원", "21만7천500원")은 한 값으로 읽는다.
# 단위 없는 마지막 숫자는 뒤에 "원"이 올 때만 붙인다 ("1,000억 2026년"의 2026을 붙이지 않게)
_NUMK = r"\d[\d,]*(?:\.\d+)?(?:\s*천(?:\s*\d{1,3}(?!\d))?)?"
_RUN = re.compile(rf"(?:{_NUMK}\s*(?:조|억|만)\s*)+(?:{_NUMK}(?=\s*원))?")
_PART = re.compile(rf"({_NUMK})\s*(조|억|만)?")

DEFAULTS = {"title_max": 20, "max_sentences": 3, "sentence_max_chars": 60, "min_confidence": 0.7, "min_fact_overlap": 0.6,
            "reason_max": 80, "fact_max": 100, "max_evidence": 3, "banned_patterns": []}

# 회사가 한 말을 전달하는 문장은 시제 패턴(예측 표현) 검사에서 뺀다 ("회사는 ~라고 밝혔어요", 지침서 [근거 우선순위])
# "로 전망했"·"로 예상했": 증권사·언론이 주어인 전망 문장 ("KB증권은 매출이 상승할 것으로 전망했어요")
ATTRIBUTION = ("라고 밝혔", "고 밝혔", "고 발표", "고 전했", "고 설명", "예상한다고", "계획이라고", "로 전망했", "로 예상했")


def _korean(num: str) -> float:
    """"7천921" = 7,921, "7천" = 7,000, "1,034" = 1,034."""
    head, sep, tail = num.partition("천")
    if not sep:
        return float(num.replace(",", ""))
    return float(head.replace(",", "").strip()) * 1e3 + float(tail.strip() or 0)


def _compound(run: str) -> list[float]:
    """나눠 쓴 금액을 더한다. 단위가 조 → 억 → 만 순서가 아니면 더하지 않고 하나씩 돌려준다."""
    parts = [(_korean(n), _UNIT[u] if u else 1.0) for n, u in _PART.findall(run)]
    factors = [f for _, f in parts]
    if factors != sorted(set(factors), reverse=True):
        return [v * f for v, f in parts]
    return [sum(v * f for v, f in parts)]


def _scan(text: str, combine: bool) -> list[tuple[float, bool]]:
    """(값, 단위나 %가 붙었나). combine이면 나눠 쓴 금액을 먼저 한 값으로 읽고 그 자리는 지운다."""
    text = _TAG.sub(" ", text or "")
    text = _DATE.sub(lambda m: " ".join(g for g in m.groups() if g), text)
    out = []
    if combine:
        def take(m):
            out.extend((v, True) for v in _compound(m.group(0)))
            return " "
        text = _RUN.sub(take, text)
    for raw, unit, pct in _NUM.findall(text):
        out.append((float(raw.replace(",", "")) * _UNIT.get(unit, 1), bool(unit or pct)))
    return out


def numbers(text: str) -> set[float]:
    """글 속 숫자를 단위를 맞춰 값으로 바꾼다 (7만 = 70,000, 1.5조 = 1.5e12, 14조 1034억 = 14,103,400,000,000).
    한 자리 일반 숫자(3분기 등)는 비교에서 뺀다."""
    return {round(v, 6) for v, has_unit in _scan(text, True) if v >= 10 or has_unit}


def all_numbers(text: str) -> set[float]:
    """근거 쪽은 한 자리 숫자도 모두 모은다 (답변 쪽에서 뺀 것과 비교가 어긋나지 않게).
    나눠 쓴 금액은 합친 값과 조각 값을 모두 넣는다 (기사에 "1조9075억원"이 있으면 답변의 "9075억"도 인정)."""
    return {round(v, 6) for v, _ in _scan(text, True) + _scan(text, False)}


_UNIT_HEADER = re.compile(r"단위\s*[:：]?\s*(천원|백만원|억원|조원)")
_HEADER_FACTOR = {"천원": 1e3, "백만원": 1e6, "억원": 1e8, "조원": 1e12}


def evidence_numbers(text: str) -> set[float]:
    """근거 글의 숫자. 표 머리에 "(단위: 천원)"이 있으면 표 안 숫자는 원 단위로 환산한 값도 함께 인정한다 (DART 재무 표).
    머리가 글에 없으면 환산하지 않으므로, 모델이 근거에 없는 단위를 붙이면 그대로 걸린다."""
    out = all_numbers(text)
    m = _UNIT_HEADER.search(text or "")
    if m:
        factor = _HEADER_FACTOR[m.group(1)]
        out |= {round(v * factor, 6) for v in out}
    return out


# 문장 끝 해요체·합니다체 어미 ("결정했어요." → "결정", "1,167원이에요" → "1,167원")
_ENDING = re.compile(r"(?:했|됐|되었|였|이었|었|았|이)?(?:어요|에요|예요|입니다|습니다|니다)(?=[\s.,]|$)")


def _bigrams(text: str) -> set[str]:
    t = re.sub(r"\s+", "", text)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _tags(text: str) -> list[str]:
    return re.findall(r"\[(E\d+)\]", text)


def _check_body(lines: list[str], ev_pairs: list[tuple[str, str]], extra: list[str], confidence: float,
                evidence: list[Evidence], banned: list[str], cfg: dict) -> list[str]:
    """summary(또는 answer)와 evidence에 대한 공통 검사 (지침서 3-1)."""
    codes: list[str] = []
    ids = {e.eid: e for e in evidence}

    if not (1 <= len(lines) <= cfg["max_sentences"]) or any(
            not s.strip() or len(_TAG.sub("", s).strip()) > cfg["sentence_max_chars"] for s in lines):
        codes.append("FORMAT_SUMMARY")
    if not ev_pairs or len(ev_pairs) > cfg["max_evidence"] or any(len(f) > cfg["fact_max"] or not f.strip() for _, f in ev_pairs):
        codes.append("FORMAT_EVIDENCE")

    # 출처 대조: 문장마다 근거 번호가 있고, 모두 넣어 준 번호여야 하며, evidence에는 실제 쓴 번호만 있어야 한다
    used = set()
    for s in lines:
        tags = _tags(s)
        used |= set(tags)
        if not tags or any(t not in ids for t in tags):
            codes.append("SOURCE")
            break
    if any(sid not in ids or sid not in used for sid, _ in ev_pairs):
        codes.append("SOURCE")

    # 금지 표현: 사전은 부분 문자열, 시제 패턴은 회사 발언 전달 문장을 뺀 문장에만
    texts = [_TAG.sub("", s) for s in lines] + extra + [f for _, f in ev_pairs]
    body = " ".join(texts)
    if any(term in body for term in banned):
        codes.append("BANNED")
    else:
        patterns = [re.compile(p) for p in cfg["banned_patterns"]]
        for t in texts:
            if any(a in t for a in ATTRIBUTION):
                continue
            if any(p.search(t) for p in patterns):
                codes.append("BANNED")
                break

    # 숫자 대조: 답변의 모든 숫자가 넣어 준 근거에 있어야 한다
    seen = set()
    for e in evidence:
        seen |= evidence_numbers(f"{e.candidate.title} {e.shown_text} {e.candidate.date}")
    if not numbers(body) <= seen:
        codes.append("NUMBER")

    # fact가 해당 근거 글과 비슷한가 (추가 검사). 해요체 어미는 근거 글에 없으니 빼고 비교하고,
    # 수시공시("항목: 값" 표)는 풀어 쓰면 겹치는 글자가 적어 기준을 따로 둔다 (min_fact_overlap_event)
    for sid, fact in ev_pairs:
        e = ids.get(sid)
        limit = cfg["min_fact_overlap"]
        if e is not None and e.candidate.doc == "event":
            limit = cfg.get("min_fact_overlap_event", limit)
        fb = _bigrams(_ENDING.sub("", fact))
        if e is not None and fb and limit > 0:
            eb = _bigrams(f"{e.candidate.title} {e.shown_text}")
            if len(fb & eb) / len(fb) < limit:
                codes.append("FACT_OVERLAP")
                break

    if confidence < cfg["min_confidence"]:
        codes.append("LOW_CONF")
    return codes


def check_card(card: Card, evidence: list[Evidence], banned: list[str], cfg: dict | None = None) -> list[str]:
    """status가 update인 카드 검사. 걸린 이유 코드 목록 (비어 있으면 통과)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    codes: list[str] = []
    if not card.title.strip() or len(card.title) > cfg["title_max"]:
        codes.append("FORMAT_TITLE")
    if not card.reason.strip() or len(card.reason) > cfg["reason_max"]:
        codes.append("FORMAT_REASON")
    codes += _check_body(card.summary, card.evidence, [card.title, card.reason], card.confidence, evidence, banned, cfg)
    return list(dict.fromkeys(codes))


def check_no_update(card: Card) -> list[str]:
    """no_update는 제목·이유가 비고 summary·evidence가 빈 배열이어야 한다 (지침서 3-2). 확신도 기준은 적용하지 않는다."""
    ok = not card.title and not card.reason and not card.summary and not card.evidence
    return [] if ok else ["FORMAT_STATE"]


def check_answer(ans: Answer, evidence: list[Evidence], banned: list[str], cfg: dict | None = None) -> list[str]:
    """즉시 답변 검사 (지침서 3-1, 3-2). cannot_answer는 형식만 보고 확신도 기준은 적용하지 않는다."""
    cfg = {**DEFAULTS, **(cfg or {})}
    if ans.status == "cannot_answer":
        ok = not ans.answer and not ans.evidence and ans.reason_code != "none"
        return [] if ok else ["FORMAT_STATE"]
    if ans.reason_code != "none":
        return ["FORMAT_STATE"]
    return list(dict.fromkeys(_check_body(ans.answer, ans.evidence, [], ans.confidence, evidence, banned, cfg)))