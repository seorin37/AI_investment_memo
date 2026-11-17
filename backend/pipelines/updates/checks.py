"""코드 검사 — LLM이 지침을 어겨도 사용자에게 보이지 않게 하는 마지막 관문 (지침서 Ⅴ-1).

형식 / 금지 표현 / 숫자 대조 / 출처 대조 / 확신도. 걸린 이유를 코드 목록으로 돌려준다 (하나라도 있으면 그 답변은 쓰지 않는다).
FACT_OVERLAP은 지침서에 없는 추가 검사(evidence.fact가 근거 글과 너무 다르면 거름)이고 min_fact_overlap=0으로 끌 수 있다.
"""

from __future__ import annotations

import re

from .models import Answer, Card, Evidence

_TAG = re.compile(r"\[E\d+\]")
_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?")
# 단위는 긴 것부터 맞춘다 ("706,565백만원"을 706,565로, "5천억"을 5천으로 읽지 않게). 뒤의 "원"은 단위가 붙은 금액인지 가리는 데만 쓴다
_UNIT = {"조": 1e12, "천억": 1e11, "백억": 1e10, "십억": 1e9, "억": 1e8, "천만": 1e7, "백만": 1e6, "만": 1e4, "천": 1e3}
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(" + "|".join(sorted(_UNIT, key=len, reverse=True)) + r")?\s*(%|퍼센트)?(\s*원)?")
# 표의 "배당금총액(원): 14,103,466,480,000"처럼 바로 앞 이름표가 "(원)"인 숫자는 원 단위 금액으로 본다
_WON_LABEL = re.compile(r"\(원\)\s*[:：]?\s*$")
# 한국식으로 나눠 쓴 금액 ("14조 1034억 6648만 8000원", "5조7천921억원", "21만7천500원")은 한 값으로 읽는다.
# 단위 없는 마지막 숫자는 뒤에 "원"이 올 때만 붙인다 ("1,000억 2026년"의 2026을 붙이지 않게)
_NUMK = r"\d[\d,]*(?:\.\d+)?(?:\s*천(?:\s*\d{1,3}(?!\d))?)?"
_RUN = re.compile(rf"(?:{_NUMK}\s*(?:조|억|만)\s*)+(?:{_NUMK}(?=\s*원))?")
_PART = re.compile(rf"({_NUMK})\s*(조|억|만)?")

DEFAULTS = {"title_max": 20, "max_sentences": 3, "sentence_max_chars": 60, "min_confidence": 0.7, "min_fact_overlap": 0.6,
            "reason_max": 80, "fact_max": 100, "max_evidence": 3, "banned_patterns": [],
            "prediction_terms": [], "prediction_exempt": [], "judgment_patterns": [], "coverage_terms": []}

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


UNIT, PCT, BARE = "unit", "pct", "bare"   # 숫자 종류: 단위(조·억·만·백만…)나 "원"이 붙은 금액 / % / 맨숫자


def _scan(text: str, combine: bool) -> list[tuple[float, str]]:
    """(값, 종류). combine이면 나눠 쓴 금액을 먼저 한 값으로 읽고 그 자리는 지운다."""
    text = _TAG.sub(" ", text or "")
    text = _DATE.sub(lambda m: " ".join(g for g in m.groups() if g), text)
    out = []
    if combine:
        def take(m):
            out.extend((v, UNIT) for v in _compound(m.group(0)))
            return " "
        text = _RUN.sub(take, text)
    for m in _NUM.finditer(text):
        raw, unit, pct, won = m.groups()
        kind = (UNIT if unit or won or _WON_LABEL.search(text[max(0, m.start() - 12):m.start()])
                else PCT if pct else BARE)
        out.append((float(raw.replace(",", "")) * _UNIT.get(unit, 1), kind))
    return out


def _card_scan(text: str) -> list[tuple[float, str]]:
    """답변 쪽 숫자 (값, 종류). 한 자리 맨숫자(3분기 등)는 비교에서 뺀다."""
    return [(round(v, 6), kind) for v, kind in _scan(text, True) if v >= 10 or kind != BARE]


def numbers(text: str) -> set[float]:
    """글 속 숫자를 단위를 맞춰 값으로 바꾼다 (7만 = 70,000, 1.5조 = 1.5e12, 14조 1034억 = 14,103,400,000,000,
    706,565백만원 = 706,565,000,000). 한 자리 일반 숫자(3분기 등)는 비교에서 뺀다."""
    return {v for v, _ in _card_scan(text)}


def all_numbers(text: str) -> set[float]:
    """근거 쪽은 한 자리 숫자도 모두 모은다 (답변 쪽에서 뺀 것과 비교가 어긋나지 않게).
    나눠 쓴 금액은 합친 값과 조각 값을 모두 넣는다 (기사에 "1조9075억원"이 있으면 답변의 "9075억"도 인정)."""
    return {round(v, 6) for v, _ in _scan(text, True) + _scan(text, False)}


_UNIT_HEADER = re.compile(r"단위\s*[:：]?\s*(천원|백만원|억원|조원)")
_HEADER_FACTOR = {"천원": 1e3, "백만원": 1e6, "억원": 1e8, "조원": 1e12}


class EvidenceNumbers:
    """근거 숫자 두 묶음.
    - plain: 답변의 맨숫자·%와 대조. 근거의 모든 값 + 표 머리 환산값 (이전 evidence_numbers와 같다)
    - unit: 답변에서 단위·"원"이 붙은 금액과 대조. 표 머리("(단위 : 백만원)")가 있으면 근거에 단위·원과 함께 적힌 값과
      표 숫자를 머리 단위로 환산한 값만 (표의 706,565를 "706,565원"으로 쓰면 걸리게). 머리가 없으면 plain과 같다."""

    __slots__ = ("plain", "unit")

    def __init__(self, plain: set[float] | None = None, unit: set[float] | None = None):
        self.plain = set(plain or ())
        self.unit = set(unit or ())

    def __ior__(self, other: "EvidenceNumbers") -> "EvidenceNumbers":
        self.plain |= other.plain
        self.unit |= other.unit
        return self

    def supports(self, text: str) -> bool:
        """답변 글의 숫자가 모두 근거에 있나. 단위·원이 붙은 숫자는 unit, 나머지는 plain과 대조한다."""
        return all(v in (self.unit if kind == UNIT else self.plain) for v, kind in _card_scan(text))


def evidence_number_sets(text: str) -> EvidenceNumbers:
    """근거 글의 숫자 (EvidenceNumbers). 표 머리에 "(단위: 천원)"이 있으면 표 안 숫자를 원 단위로 환산한 값도 인정한다 (DART 재무 표).
    머리가 글에 없으면 환산하지 않으므로, 모델이 근거에 없는 단위를 붙이면 그대로 걸린다."""
    pairs = _scan(text, True) + _scan(text, False)
    values = {round(v, 6) for v, _ in pairs}
    m = _UNIT_HEADER.search(text or "")
    if not m:
        return EvidenceNumbers(values, values)
    factor = _HEADER_FACTOR[m.group(1)]
    return EvidenceNumbers(values | {round(v * factor, 6) for v in values},
                           {round(v, 6) for v, kind in pairs if kind == UNIT}
                           | {round(v * factor, 6) for v, kind in pairs if kind == BARE})


def evidence_numbers(text: str) -> set[float]:
    """근거 글의 모든 숫자 값 (표 머리 환산값 포함). 단위 구분 없이 값만 필요한 곳(compare_prior·same_event)이 쓴다.
    답변 숫자 검사는 evidence_number_sets(...).supports를 쓴다."""
    return evidence_number_sets(text).plain


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
    seen = EvidenceNumbers()
    for e in evidence:
        seen |= evidence_number_sets(f"{e.candidate.title} {e.shown_text} {e.candidate.date}")
    if not seen.supports(body):
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


# 회사가 스스로 밝힌 계획·발언을 전하는 문장 (공시·발표 내용 자체가 사실이다). ATTRIBUTION과 달리 "로 전망했"·"로 예상했"
# (증권사·언론이 주어인 전망)는 넣지 않는다: 2026-11-09 결정으로 남의 전망은 주체를 써도 사실 근거로 쓰지 않는다
COMPANY_STATEMENT = ("라고 밝혔", "고 밝혔", "고 발표", "고 설명", "계획이라고")


def prediction_text(texts: list[str], cfg: dict) -> str | None:
    """예측(전망·예상·추정·관측·가능성 …)을 핵심 사실로 쓴 글. 시제 패턴과 달리 "증권사는 ~로 전망했어요"처럼 주체를 쓴 문장도
    잡는다 (2026-11-09 "네이버 3분기 매출 3조5천143억원 전망" 카드). 실제 실적을 예상치와 견준 표현(prediction_exempt)과
    회사가 스스로 밝힌 계획·발언(COMPANY_STATEMENT)은 뺀다."""
    exempt = [re.compile(p) for p in cfg["prediction_exempt"]]
    for t in texts:
        if any(a in t for a in COMPANY_STATEMENT):
            continue
        rest = t
        for p in exempt:
            rest = p.sub(" ", rest)
        if any(term in rest for term in cfg["prediction_terms"]):
            return t
    return None


def check_card(card: Card, evidence: list[Evidence], banned: list[str], cfg: dict | None = None) -> list[str]:
    """status가 update인 카드 검사. 걸린 이유 코드 목록 (비어 있으면 통과)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    codes: list[str] = []
    if not card.title.strip() or len(card.title) > cfg["title_max"]:
        codes.append("FORMAT_TITLE")
    if not card.reason.strip() or len(card.reason) > cfg["reason_max"]:
        codes.append("FORMAT_REASON")
    codes += _check_body(card.summary, card.evidence, [card.title, card.reason], card.confidence, evidence, banned, cfg)
    # 핵심 사실(제목·요약·근거 fact)이 예측이면 실패. 이유(reason)는 메모와의 연결 설명이라 보지 않는다
    if cfg["prediction_terms"] and prediction_text([card.title, *(_TAG.sub("", s) for s in card.summary),
                                                    *(f for _, f in card.evidence)], cfg):
        codes.append("PREDICTION")
    return list(dict.fromkeys(codes))


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KDATE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_SENT_END = re.compile(r"[.!?。](?=\s|$)")


def text_dates(text: str) -> set[str]:
    """글 속 날짜를 YYYY-MM-DD로 ("2026-10-28", "2026.10.28", "2026년 10월 28일")."""
    out = set()
    for m in list(_DATE.finditer(text or "")) + list(_KDATE.finditer(text or "")):
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if d:
            out.add(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
    return out


def _banned_hit(texts: list[str], banned: list[str], cfg: dict) -> bool:
    """v1 _check_body와 같은 금지 표현 검사: 사전은 부분 문자열, 시제 패턴은 회사 발언 전달 문장을 뺀 문장에만."""
    if any(term in " ".join(texts) for term in banned):
        return True
    patterns = [re.compile(p) for p in cfg["banned_patterns"]]
    return any(not any(a in t for a in ATTRIBUTION) and any(p.search(t) for p in patterns) for t in texts)


def _ev_text(e: Evidence) -> str:
    return f"{e.candidate.title} {e.shown_text} {e.candidate.date}"


def check_card_v2(card, evidence: list[Evidence], banned: list[str], cfg: dict | None = None) -> list[str]:
    """v2 카드(CardV2) 검사. v1과 같은 이유 코드를 쓰고, 숫자·날짜는 facts 문장마다 그 문장의 evidence_id 근거 하나와 대조한다
    (다른 근거의 숫자를 섞으면 NUMBER). "비교 자료 없음"(evidence_id "")만 근거 없이 허용한다.
    - FORMAT_TITLE headline · FORMAT_WHEN when(YYYY-MM-DD, 쓴 근거의 날짜나 근거 본문에 적힌 날짜)
    - FORMAT_SUMMARY facts 개수(1~max_sentences, 비교 자료 없음 제외)·문장 길이·[E#] 표시
    - FORMAT_REASON memo_link(한 문장, reason_max자) · SOURCE 번호·sources 목록·비교용 근거만으로 만든 카드
    - BANNED · PREDICTION(headline·facts·memo_link) · LOW_CONF. FACT_OVERLAP(v1의 evidence.fact 대조)는 v2에 없다."""
    cfg = {**DEFAULTS, **(cfg or {})}
    ids = {e.eid: e for e in evidence}
    codes: list[str] = []
    if not card.headline or len(card.headline) > cfg["title_max"]:
        codes.append("FORMAT_TITLE")
    facts = [(t, eid) for t, eid in card.facts if not (t == "비교 자료 없음" and not eid)]
    cited = [ids[eid] for _, eid in facts if eid in ids]
    allowed = set()
    for e in cited:
        allowed |= {e.candidate.date} | text_dates(_ev_text(e))
    if not _ISO.match(card.when or "") or card.when not in allowed:
        codes.append("FORMAT_WHEN")
    if not (1 <= len(facts) <= cfg["max_sentences"]) or any(
            not t or len(t) > cfg["sentence_max_chars"] or _TAG.search(t) for t, _ in facts):
        codes.append("FORMAT_SUMMARY")
    if (not card.memo_link or len(card.memo_link) > cfg["reason_max"]
            or len(_SENT_END.findall(card.memo_link.strip())) > 1):
        codes.append("FORMAT_REASON")
    used = [eid for _, eid in facts]
    if (any(eid not in ids for eid in used) or {s for s in card.sources if s} != set(used)
            or (cited and all(e.candidate.doc == "compare" for e in cited))):
        codes.append("SOURCE")
    exp_cfg = cfg.get("explanation") or {}
    exp = (getattr(card, "explanation", "") or "") if exp_cfg.get("enabled") else ""
    if exp_cfg.get("enabled") and (not exp or len(exp) > exp_cfg.get("max_chars", 400) or _TAG.search(exp)
                                   or len(_SENT_END.findall(exp.strip())) > exp_cfg.get("max_sentences", 4)):
        codes.append("FORMAT_EXPLANATION")
    texts = [card.headline, *(t for t, _ in facts), card.memo_link] + ([exp] if exp else [])
    if _banned_hit(texts, banned, cfg):
        codes.append("BANNED")
    # 숫자: 문장마다 그 근거 하나에만. 제목·memo_link는 쓴 근거 전체 안에서
    union = EvidenceNumbers()
    for e in cited:
        union |= evidence_number_sets(_ev_text(e))
    bad = any(eid in ids and not evidence_number_sets(_ev_text(ids[eid])).supports(t) for t, eid in facts)
    if bad or not all(union.supports(t) for t in (card.headline, card.memo_link, exp)):
        codes.append("NUMBER")
    if cfg["prediction_terms"] and prediction_text(texts, cfg):
        codes.append("PREDICTION")
    # 자료 범위 밖을 전제로 한 말 ("처음", "줄곧" …): 그 말이 쓴 근거에 그대로 있을 때만 (2026-11-11, 범위 밖 원인·추이를 단정하지 않게)
    def outside(text: str, hay: str) -> bool:
        return any(term in text and term not in hay for term in cfg["coverage_terms"])
    all_ev = " ".join(_ev_text(e) for e in cited)
    if (any(eid in ids and outside(t, _ev_text(ids[eid])) for t, eid in facts)
            or outside(card.headline, all_ev) or outside(card.memo_link, all_ev) or outside(exp, all_ev)):
        codes.append("COVERAGE")
    # 비교 판단·선택 권유 ("KB가 더 나아요", "갈아타는 게 좋아요"): 두 대상의 사실만 나란히 보여 주고 판단은 하지 않는다 (2026-11-10)
    judges = [re.compile(p) for p in cfg["judgment_patterns"]]
    if any(p.search(t) for p in judges for t in texts):
        codes.append("JUDGMENT")
    if card.confidence < cfg["min_confidence"]:
        codes.append("LOW_CONF")
    return list(dict.fromkeys(codes))


def check_no_update_v2(card) -> list[str]:
    ok = not card.headline and not card.when and not card.memo_link and not card.facts and not card.sources
    return [] if ok else ["FORMAT_STATE"]


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