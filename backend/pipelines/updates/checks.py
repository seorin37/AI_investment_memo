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
# 개수 단위 "명·주·건·개" (2026-11-18 N30). 뒤에 조사나 한글 아닌 글자가 올 때만 ("주당"·"주식"·"건설"·"개월"은 아니다)
_COUNT_WORD = r"(?:명|주|건|개)(?=$|[^가-힣]|[이가을를은는의에과와로으도만씩입였])"
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(" + "|".join(sorted(_UNIT, key=len, reverse=True))
                  + rf")?\s*(%|퍼센트)?(\s*원)?(\s*{_COUNT_WORD})?")
_COUNT_AFTER = re.compile(rf"\s*{_COUNT_WORD}")
# 표의 "배당금총액(원): 14,103,466,480,000"처럼 바로 앞 이름표가 "(원)"인 숫자는 원 단위 금액으로 본다
_WON_LABEL = re.compile(r"\(원\)\s*[:：]?\s*$")
# 한국식으로 나눠 쓴 금액 ("14조 1034억 6648만 8000원", "5조7천921억원", "21만7천500원")은 한 값으로 읽는다.
# 단위 없는 마지막 숫자는 뒤에 "원"이 올 때만 붙인다 ("1,000억 2026년"의 2026을 붙이지 않게)
_NUMK = r"\d[\d,]*(?:\.\d+)?(?:\s*천(?:\s*\d{1,3}(?!\d))?)?"
_RUN = re.compile(rf"(?:{_NUMK}\s*(?:조|억|만)\s*)+(?:{_NUMK}(?=\s*(?:원|{_COUNT_WORD})))?")
_PART = re.compile(rf"({_NUMK})\s*(조|억|만)?")

DEFAULTS = {"title_max": 20, "max_sentences": 3, "sentence_max_chars": 60, "min_confidence": 0.7, "min_fact_overlap": 0.6,
            "reason_max": 80, "fact_max": 100, "max_evidence": 3, "banned_patterns": [],
            "prediction_terms": [], "prediction_exempt": [], "judgment_patterns": [], "coverage_terms": []}

# 회사가 한 말을 전달하는 문장은 시제 패턴(예측 표현) 검사에서 뺀다 ("회사는 ~라고 밝혔어요", 지침서 [근거 우선순위])
# "로 전망했"·"로 예상했": 증권사·언론이 주어인 전망 문장 ("KB증권은 매출이 상승할 것으로 전망했어요")
ATTRIBUTION = ("라고 밝혔", "고 밝혔", "고 발표", "고 전했", "고 설명", "예상한다고", "계획이라고", "로 전망했", "로 예상했")

# 주체를 밝힌 전망 전달 (2026-11-18 N08 결정: 전망 기사도 근거로 쓰되 "누가 무엇을 전망했다"로만).
# - 문장: 주어(은·는·이·가) + 전망한 동작("전망했어요"·"예상한다고"·"내다봤어요"·"추정했어요"…).
#   주어가 지표·대상("영업이익은"·"주가가")이면 주체가 아니다. 앞 주어가 지표여도 뒤에 출처 주어("KB증권은")가 있으면 된다
# - 출처 주어(증권·애널리스트·기관…) + 전달 동사("제시했어요"·"밝혔어요"·"찾았어요"…)도 전달이다
#   ("김 애널리스트는 이 통계를 반등 전망의 근거로 제시했어요", 2026-11-12·13 C_all·C2_all 항목 3 카드)
# - 제목: "KB증권, 4분기 영업이익 1조 2,000억원 전망"처럼 맨 앞이 출처(증권사·기관·언론·연구원…)이고 쉼표
# - 같은 문장에 주체 없는 미래 단정("늘어날 전망이에요"·"~로 전망돼요"·"오를 거예요")이 있으면 아니다
# - 막연한 주어는 주체가 아니다 (2026-11-18): 시장·업계·증권가·전문가(들)·투자자(들)·(업계) 관계자·일각·"○○들"·대명사.
#   사람은 이름이 있어야 한다 ("김 애널리스트는" O, "애널리스트는"·"한 연구원은" X). 증권사·기관·회사·언론 이름은 그대로 주체
_FORECAST_ACT = re.compile(r"(전망|예상|추정|관측|예측)(했|한다|하고|하며|해요|합니다|하는)|내다(봤|보|본)|(전망|예상|추정)치를?\s*(제시|내놓|내놨|발표|밝혔)")
# 전달 동사. "들었"은 앞이 띄어쓰기일 때만 ("근거로 들었어요" O, "줄어들었어요" X)
_SAY_ACT = re.compile(r"(제시|설명|분석|언급|강조)(했|한다고|하며|한)|밝혔|밝힌|찾았|짚었|봤어요|본다고|보고\s*있|"
                      r"(?<![가-힣])(들었|든\s)|전했|전한|꼽았|꼽은")
# 소유격 주체 "머스크의 전망이에요"·"KB증권의 실적 전망을 다룬 기사예요"·"김동원 애널리스트의 예상치예요" (2026-11-18)
# 사이 낱말에 다른 소유격("○○의")이 끼면 넘어가지 않는다 ("빅테크의 투자 동향과 모건스탠리의 투자 전망" → 모건스탠리)
_GAP = r"(?:(?![가-힣A-Za-z0-9&·]*의\s)[가-힣A-Za-z0-9·]+\s+){0,5}?"
_POSSESSIVE = re.compile(rf"([가-힣A-Za-z0-9&·]+)의\s+{_GAP}(전망치|예상치|추정치|전망|예상|추정|관측)"
                         r"(이에요|예요|입니다|이다|을|를|과|와|에|으로|은|는|이)?")
# 관형절 주체 "김동원 애널리스트가 제시한 전망이에요"·"머스크가 제시한 공급 확대 전망이에요" (2026-11-18)
_REL_CLAUSE = re.compile(r"([가-힣A-Za-z0-9&·]+)(?:이|가)\s+(?:제시한|밝힌|내놓은|내놨던|전한|언급한|예상한|전망한|추정한)\s+"
                         rf"{_GAP}(전망치|예상치|추정치|전망|예상|추정)"
                         r"(이에요|예요|입니다|이다|을|를|과|와|에|으로|은|는|이)?")
_PERSON_WORD = r"연구원|연구위원|애널리스트|이코노미스트|기자|대표|센터장|본부장|팀장|부장|사장|회장|위원장|총재|장관|교수"
_SOURCE_WORD = re.compile(r"(증권|증권사|금융투자|리서치|연구소|은행|신문|일보|경제|뉴스|통신|방송|협회|기구|"
                          r"정부|당국|부처|회사|그룹|센터|운용|평가|IB|S&P|무디스|피치|모건스탠리|골드만삭스|"
                          rf"JP모간|씨티|노무라|UBS|트렌드포스|가트너|IDC|옴디아|카운터포인트|WSTS|{_PERSON_WORD})$")
_VAGUE_SUBJECT = re.compile(r"^(시장|업계|증권가|증권업계|증권사|금융권|전문가|투자자|관계자|일각|기관|외국인|개인|컨센서스|"
                            r"시장참여자|외신|언론|그|그녀|이들|그들|누군가)(에서)?$|들(에서)?$")
_PERSON_ONLY = re.compile(rf"^({_PERSON_WORD})$")
_NOT_A_NAME = {"한", "어느", "일부", "다른", "많은", "여러", "몇몇", "업계", "시장", "증권가", "익명의", "해당", "이", "그"}


def _named_word(word: str, before: str) -> bool:
    """word가 막연하지 않은 주체인가. 직함만 있으면("애널리스트") before의 마지막 낱말이 이름이어야 한다."""
    if _VAGUE_SUBJECT.search(word):
        return False
    if _PERSON_ONLY.match(word):
        prev = before.split()
        # 앞말이 조사로 끝나면("이는"·"자료에서는") 이름이 아니다
        return (bool(prev) and prev[-1] not in _NOT_A_NAME and not _VAGUE_SUBJECT.search(prev[-1])
                and not re.search(r"(은|는|이|가|을|를|에|의|와|과|도|서)$", prev[-1]))
    return True


def _named(m: re.Match, text: str) -> bool:
    return _named_word(m.group(1), text[:m.start()])
_NOT_SUBJECT = re.compile(r"(이익|매출|매출액|주가|수요|공급|가격|실적|업황|비율|금액|규모|수익|출하|생산|투자|성장|전망|예상|배당|점유율)$")
_SUBJECT = re.compile(r"([가-힣A-Za-z0-9&·]+)(?:은|는|이|가)\s")
_UNATTRIBUTED = re.compile(r"(전망|예상|추정|관측|기대)(돼요|되어요|됩니다|돼|이에요|입니다|된다|이다)|(할|될)\s*전망|"
                           r"것으로\s*(보여요|보입니다|보인다)|(거|것)(예요|이에요|입니다)|가능성이?\s*(높|큽|커)")


def _source_owner(word: str, before: str, names) -> bool:
    """소유격·제목 맨 앞 낱말이 전망한 주체인가: 막연하지 않고, 출처 낱말(증권·언론·이름 있는 직함…)이거나
    카드 사실 문장에서 전망 주체로 나온 이름(names). "SK하이닉스의 실적 전망"처럼 전망 대상일 수 있는 말은 names에 있어야 한다."""
    if not _named_word(word, before) or _NOT_SUBJECT.search(word):
        return False
    return bool(_SOURCE_WORD.search(word)) or word in names


def forecast_subjects(texts) -> set[str]:
    """전망 전달 문장(attributed_forecast)의 이름 있는 주어 ("머스크는 ~로 전망했어요" → 머스크). 제목·소유격 판단에 쓴다."""
    out = set()
    for t in texts:
        t = _TAG.sub("", t or "")
        if not attributed_forecast(t):
            continue
        subjects = [m for m in _SUBJECT.finditer(t) if _named(m, t) and not _NOT_SUBJECT.search(m.group(1))]
        if subjects:                                    # 맨 앞 주어와 출처 낱말 주어만 ("머스크는 중국이 …"의 중국은 아니다)
            out |= {subjects[0].group(1)} | {m.group(1) for m in subjects if _SOURCE_WORD.search(m.group(1))}
    return out


# 사실 문장마다 주체 (2026-11-19): 전망·분석·설명·발언을 전하는 문장은 그 문장 안에 누가 말했는지가 있어야 한다.
# 앞 문장에 주체가 있어도 문장마다 따로 본다 (카드 사실 문장은 접혀서 한 줄씩 보이고, 근거도 문장마다 다를 수 있다).
_REPORT_ACT = re.compile(rf"{_FORECAST_ACT.pattern}|{_SAY_ACT.pattern}|(고|며)\s*(밝혔|발표|전했|설명|덧붙였|강조)|"
                         r"(보도|평가|진단|지적|주장|언급|예고|제기)(했|한다고|하며)|내놨|내놓았")
_ACTOR = re.compile(r"([가-힣A-Za-z0-9&·]+)(은|는|이|가)\s")
# 주체가 될 수 없는 말: 지표·수량·때 ("출하량은 ~로 예상했어요", "올해는 ~로 전망했어요"는 누가 예상했는지 없다)
_NOT_ACTOR = re.compile(rf"{_NOT_SUBJECT.pattern}|(량|률|율|액|전망치|예상치|추정치|수치|폭|규모|비중|기간|시점|단계|계획|일정|요인|"
                        r"이유|원인|목표|기준|올해|내년|작년|지난해|분기|반기|연간|이번|향후|앞으로|최근|당분간)$")
_ADNOMINAL = re.compile(r"(라|다|하|되|있|없|겠|이라)$")   # "단계라는"·"늘었다는"·"증가하는"의 는은 주어 조사가 아니다


def _according_source(t: str) -> bool:
    """"○○에 따르면"·"KB증권 분석을 전한 기사에 따르면": '에 따르면' 앞에 이름 있는 출처가 있는가 (문장 어디든)."""
    for m in re.finditer(r"에\s*따르면", t):
        before = t[:m.start()]
        words = re.findall(r"[가-힣A-Za-z0-9&·]+", before)
        if words and _named_word(words[-1], " ".join(words[:-1])) and not _NOT_ACTOR.search(words[-1]) \
                and not _VAGUE_SUBJECT.search(words[-1]) and words[-1] not in ("기사", "보도", "자료", "발표"):
            return True
        if any(_SOURCE_WORD.search(w) and _named_word(w, "") for w in words[-6:]):
            return True
    return False


def missing_subject(text: str) -> bool:
    """전달 문장(전망·분석·설명·발언)인데 그 문장에 이름 있는 주체가 없는가.
    주체: 은·는 주어(막연한 말·지표·때 말 제외), 출처 낱말(증권·신문·회사 …)이 붙은 이·가 주어, "○○에 따르면".
    이·가 주어는 출처 낱말일 때만 인정한다 ("아틀라스가 아직 매출 이전 단계라는 분석을 전했어요"의 아틀라스는 분석한 쪽이 아니다)."""
    t = _TAG.sub("", text or "").strip()
    act = _REPORT_ACT.search(t)
    if not act:
        return False
    head = t[:act.start()]
    for m in _ACTOR.finditer(head):
        word, particle = m.group(1), m.group(2)
        if not _named(m, t) or _NOT_ACTOR.search(word) or (particle == "는" and _ADNOMINAL.search(word)):
            continue
        if particle in ("은", "는") or _SOURCE_WORD.search(word):
            return False
    return not _according_source(t)


def attributed_forecast(text: str, headline: bool = False, names=frozenset()) -> bool:
    """주체를 밝힌 전망 전달 문장인가 (위 설명). headline이면 "출처, …" 제목 형식도 본다.
    names: 카드 사실 문장의 전망 주체 이름 (forecast_subjects). 제목 맨 앞·소유격 주체로 인정한다."""
    t = _TAG.sub("", text or "").strip()
    if not t:
        return False
    # 소유격 주체: "○○의 전망이에요"를 지운 나머지에 주체 없는 단정이 없으면 전달
    stripped = _POSSESSIVE.sub(lambda m: " " if _source_owner(m.group(1), t[:m.start()], names) else m.group(0), t)
    stripped = _REL_CLAUSE.sub(lambda m: " " if _source_owner(m.group(1), stripped[:m.start()], names) else m.group(0),
                               stripped)
    if stripped != t and not _UNATTRIBUTED.search(stripped):
        return True
    if _UNATTRIBUTED.search(t):
        return False
    if headline:
        head, sep, _ = t.partition(",")
        words = head.split()
        if sep and words and _source_owner(words[-1], " ".join(words[:-1]), names):
            return True
    act = _FORECAST_ACT.search(t)
    if act:
        subjects = list(_SUBJECT.finditer(t[:act.start()]))
        first_ok = bool(subjects) and _named(subjects[0], t) and not _NOT_SUBJECT.search(subjects[0].group(1))
        if first_ok or any(_SOURCE_WORD.search(m.group(1)) and _named(m, t) for m in subjects):
            return True
    # 출처 주어의 전달 동사: "김 애널리스트는 … 반등 전망의 근거로 제시했어요", "KB증권이 … 전망의 근거로 제시한 통계예요"
    say = _SAY_ACT.search(t)
    # 출처 낱말 주어 또는 사실 문장의 전망 주체(names: "머스크가 … 가능성을 언급한 기사예요")
    return bool(say and any((_SOURCE_WORD.search(m.group(1)) or m.group(1) in names) and _named(m, t)
                            for m in _SUBJECT.finditer(t[:say.start()])))


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


# 숫자 종류: 단위(조·억·만·백만…)나 "원"이 붙은 금액 / % / 맨숫자 / 개수 단위(명·주·건·개)가 붙은 수 ("30,853천 명" = 30,853,000명)
UNIT, PCT, BARE, COUNT = "unit", "pct", "bare", "count"
# 외화 금액 (2026-11-19): 숫자(배수 포함) 바로 뒤에 달러·USD·엔 … 이 붙은 값. 원화 금액(UNIT)과 따로 대조한다
# ("(단위: 백만달러)" 표의 9,435 → "9,435백만달러"는 통과, "(단위 : USD)" 표의 5,000 → "5,000원"은 실패)
FX = "fx"
_FX_AFTER = re.compile(r"\s*(?:달러|USD|유로|EUR|엔|JPY|위안|CNY)(?![A-Za-z])")


def _scan(text: str, combine: bool) -> list[tuple[float, str]]:
    """(값, 종류). combine이면 나눠 쓴 금액·개수("3,085만 3천 명")를 먼저 한 값으로 읽고 그 자리는 지운다."""
    text = _TAG.sub(" ", text or "")
    text = _DATE.sub(lambda m: " ".join(g for g in m.groups() if g), text)
    out = []
    if combine:
        def take(m):
            kind = (COUNT if _COUNT_AFTER.match(m.string, m.end())
                    else FX if _FX_AFTER.match(m.string, m.end()) else UNIT)
            out.extend((v, kind) for v in _compound(m.group(0)))
            return " "
        text = _RUN.sub(take, text)
    for m in _NUM.finditer(text):
        raw, unit, pct, won, count = m.groups()
        kind = (COUNT if count and not won and not pct
                else FX if not won and not pct and _FX_AFTER.match(text, m.end())
                else UNIT if unit or won or _WON_LABEL.search(text[max(0, m.start() - 12):m.start()])
                else PCT if pct else BARE)
        out.append((float(raw.replace(",", "")) * _UNIT.get(unit, 1), kind))
    return out


def _card_scan(text: str) -> list[tuple[float, str]]:
    """답변 쪽 숫자 (값, 종류). 한 자리 맨숫자(3분기 등)·한 자리 개수("1주당"의 1주)는 비교에서 뺀다."""
    return [(round(v, 6), kind) for v, kind in _scan(text, True) if v >= 10 or kind not in (BARE, COUNT)]


def numbers(text: str) -> set[float]:
    """글 속 숫자를 단위를 맞춰 값으로 바꾼다 (7만 = 70,000, 1.5조 = 1.5e12, 14조 1034억 = 14,103,400,000,000,
    706,565백만원 = 706,565,000,000). 한 자리 일반 숫자(3분기 등)는 비교에서 뺀다."""
    return {v for v, _ in _card_scan(text)}


def all_numbers(text: str) -> set[float]:
    """근거 쪽은 한 자리 숫자도 모두 모은다 (답변 쪽에서 뺀 것과 비교가 어긋나지 않게).
    나눠 쓴 금액은 합친 값과 조각 값을 모두 넣는다 (기사에 "1조9075억원"이 있으면 답변의 "9075억"도 인정)."""
    return {round(v, 6) for v, _ in _scan(text, True) + _scan(text, False)}


# 표 단위. 금액 단위는 표 숫자를 원으로, 개수 단위(명·주·건·개, 배수 천·만·백만… 포함)는 개수로 환산한다.
# 그 밖의 단위(%·배·회)는 환산하지 않되 금액·개수로도 보지 않는다
_MONEY_FACTOR = {"원": 1.0, "천원": 1e3, "백만원": 1e6, "억원": 1e8, "십억원": 1e9, "조원": 1e12}
_COUNT_MULT = {"": 1.0, "천": 1e3, "만": 1e4, "십만": 1e5, "백만": 1e6, "천만": 1e7, "억": 1e8}
_COUNT_FACTOR = {m + b: f for m, f in _COUNT_MULT.items() for b in ("명", "주", "건", "개")}
# 외화 + 배수 ("(단위: 백만달러)"·"천USD"·"억엔", 2026-11-19 M021 삼성바이오로직스 수주잔고 표 "9,435" → 카드 "9,435백만달러").
# 숫자 검사는 통화를 가리지 않고 배수만 맞춘다 (카드 쪽도 "백만"·"억"만 값으로 읽는다). 원화 단위와 한 머리에 섞이면 모르는 단위
_FX_CODES = ("달러", "USD", "유로", "EUR", "엔", "JPY", "위안", "CNY")
_FX_FACTOR = {m + c: f for m, f in {**_COUNT_MULT, "십억": 1e9}.items() for c in _FX_CODES}
_MONEY_FACTOR_ALL = {**_MONEY_FACTOR, **_FX_FACTOR}
_OTHER_UNITS = ("%", "배", "회")
_UNITS_RE = "|".join(sorted([*_MONEY_FACTOR_ALL, *_COUNT_FACTOR, *_OTHER_UNITS], key=len, reverse=True))
# 표 머리 "(단위 : 백만원)"·"(단위: 원, %)"·"(단위 : 천명)" (쉼표 뒤는 무시하고 첫 단위만).
# 쌍점 뒤 단위를 모르면("(단위 : USD)"·"(단위 : 천)"·"(단위 : 백만)"·"(단위 : 천단위)") _UNKNOWN: 앞 표 단위 범위를 끊는다 (2026-11-18)
_UNKNOWN = "?"
_UNIT_HEADER = re.compile(rf"단위\s*[:：]?\s*({_UNITS_RE})(?![가-힣A-Za-z])|단위\s*[:：]\s*([^\s,)\]/:：]{{1,15}})")
# 표 행 이름표의 단위 "주당배당금(단위: 원)"·"기본주당이익(손실) (단위 : 원)"·"배당금총액(원)"·"비율(%)"·"임직원수(천명)".
# "단위" 없는 괄호는 금액·%·개수만 단위로 보고 "(주)"는 뺀다 ("(주)한화"의 (주)는 주식회사. "(천주)"는 단위).
# "(단위: USD)"처럼 모르는 단위면 그 줄은 _UNKNOWN
_BARE_LABEL_UNITS = [*_MONEY_FACTOR, "%", *(u for u in _COUNT_FACTOR if u != "주")]
_LABEL_UNIT = re.compile(rf"\(\s*(?:단위\s*[:：]?\s*({_UNITS_RE})|("
                         + "|".join(sorted(_BARE_LABEL_UNITS, key=len, reverse=True))
                         + r")|단위\s*[:：]\s*([^\s,)]{1,15}))\s*[,)]")
_NO_CONTEXT = None          # 표 머리·이름표가 없는 글: 맨숫자를 금액·개수로도 인정 (기사·문단)
_HEAD_CELL = re.compile(r"\|\s*\(\s*단위\s*[:：][^()|]*\)\s*$")          # 줄 끝 칸 전체가 "(단위 : X)"
_LABEL_CURRENCY = re.compile(r"\[\s*[A-Z]{3}\s*[,\]]")                   # 이름표의 통화 표시 "[USD, 천]"


def table_unit(unit: str) -> tuple[str, float] | None:
    """표 단위 문자열 → (종류, 배수). 숫자 검사가 모르는 단위면 None. ("백만원" → (UNIT, 1e6), "천명" → (COUNT, 1e3), "%" → (PCT, 1))"""
    if unit in _FX_FACTOR:
        return FX, _FX_FACTOR[unit]
    if unit in _MONEY_FACTOR:
        return UNIT, _MONEY_FACTOR[unit]
    if unit in _COUNT_FACTOR:
        return COUNT, _COUNT_FACTOR[unit]
    if unit in _OTHER_UNITS:
        return PCT if unit == "%" else BARE, 1.0
    return None


def _row_split(line: str) -> int:
    """표 행 줄이면 첫 " | "의 위치 (이름표 끝), 아니면 -1. 청크 제목 "[KB금융 2026 3분기 | III. …]" 안의 " | "는 빼고 찾는다."""
    depth = 0
    for i, ch in enumerate(line):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif depth == 0 and line.startswith(" | ", i):
            return i
    return -1


def _segments(text: str):
    """(글 조각, 단위). 단위는 그 조각의 맨숫자에 적용할 단위 (없으면 _NO_CONTEXT).
    - 표 머리: 숫자마다 그 앞에 나온 가장 가까운 "(단위 : …)"를 쓴다 (한 근거에 표가 여러 개, 2026-11-18)
    - 행 이름표: 같은 줄 이름표(첫 " | " 앞)에 단위가 있으면 그 줄 값들은 표 머리 대신 그 단위 (줄 단위로만)
    - 모르는 단위 머리·이름표는 _UNKNOWN: 그 숫자는 맨숫자로만 인정한다 (금액·개수로 보지 않는다)
    DART 청크는 표 한 행이 한 줄이다 (disclosures/chunker. 토큰 한도를 넘는 행만 잘리며, 284만 청크 중 잘린 조각 758줄)."""
    header = _NO_CONTEXT
    for line in (text or "").split("\n"):
        cut = _row_split(line)
        label, rest = (line[:cut], line[cut:]) if cut >= 0 else ("", line)
        # 행 줄 안의 "(단위: …)"는 그 칸 단위라 표 머리로 쓰지 않는다. 단 줄 끝 칸 전체가 "(단위 : X)"면 표 머리
        # ("(대상기간 : | 2026년 02월 13일 | ~ | … ) | (단위 : 천주)", 2026-11-18 실제 공시 확인)
        heads = _UNIT_HEADER.findall(line) if cut < 0 or _HEAD_CELL.search(line) else []
        if heads:
            # 한 머리에 모르는 단위가 섞이면 모르는 단위 ("(외화단위: 천USD, …, 원화단위: 백만원)"의 USD 칸을 백만원으로 보지 않게)
            fx = {a in _FX_FACTOR for a, _ in heads if a in _MONEY_FACTOR_ALL}
            header = _UNKNOWN if any(not a for a, _ in heads) or len(fx) > 1 else heads[-1][0]
        units = [a or b or _UNKNOWN for a, b, _ in _LABEL_UNIT.findall(label)]
        if _LABEL_CURRENCY.search(label):                         # "기초통화금액, USD [USD, 천]"
            units = [_UNKNOWN]
        # 행 안 칸에 모르는 단위가 적힌 줄("한도단위: USD | 한도액: 350,000")은 그 줄만 모르는 단위 (2026-11-18 실제 공시 확인)
        if not units and cut >= 0 and any((not a and b) or a in _FX_FACTOR for a, b in _UNIT_HEADER.findall(rest)):
            units = [_UNKNOWN]
        # 숫자가 없는 열 머리 행의 이름표 단위는 표 머리 ("구분(단위 : 천명) | SO수 | 가입자 | 점유율")
        # (데이터 행은 "칸: 값" 꼴이라 뺀다: "주당배당금(원) | 당기: - | 전기: -")
        if units and cut >= 0 and not re.search(r"[\d:：]", rest):
            header = units[-1]
        if label:
            yield label, header
        yield rest, units[-1] if units else header


class EvidenceNumbers:
    """근거 숫자 두 묶음.
    - plain: 답변의 맨숫자·%와 대조. 근거의 모든 값 + 표 머리 환산값 (이전 evidence_numbers와 같다)
    - unit: 답변에서 단위·"원"이 붙은 금액과 대조. 근거에 단위·원과 함께 적힌 값, 표 숫자를 그 줄 단위(행 이름표 → 가장 가까운
      앞 표 머리)로 환산한 값 (표의 706,565를 "706,565원"으로 쓰면 걸리게). 표 머리·이름표가 없는 글의 맨숫자는 그대로 넣는다.
    - count: 답변에서 명·주·건·개가 붙은 수와 대조. 근거에 개수 단위와 함께 적힌 값, 표 숫자를 개수 단위(천명·백만주…)로
      환산한 값, 그 밖의 맨숫자 원래 값 (배수 붙은 개수 단위 표만 빼고). 개수 환산값은 plain·unit에 넣지 않는다
      ("30,853천명"으로 "30,853,000원"·"30,853명" 불가)"""

    __slots__ = ("plain", "unit", "count", "fx")

    def __init__(self, plain: set[float] | None = None, unit: set[float] | None = None,
                 count: set[float] | None = None, fx: set[float] | None = None):
        self.plain = set(plain or ())
        self.unit = set(unit or ())
        self.count = set(count or ())
        self.fx = set(fx or ())          # 외화 금액 (2026-11-19): 달러·USD·엔이 붙은 값, 외화 단위 표 숫자를 배수로 환산한 값

    def copy(self) -> "EvidenceNumbers":
        return EvidenceNumbers(self.plain, self.unit, self.count, self.fx)

    def __ior__(self, other: "EvidenceNumbers") -> "EvidenceNumbers":
        self.plain |= other.plain
        self.unit |= other.unit
        self.count |= other.count
        self.fx |= other.fx
        return self

    def supports(self, text: str) -> bool:
        """답변 글의 숫자가 모두 근거에 있나. 금액은 unit, 개수는 count, 나머지는 plain과 대조한다."""
        pick = {UNIT: self.unit, COUNT: self.count, FX: self.fx}
        return all(v in pick.get(kind, self.plain) for v, kind in _card_scan(text))


def evidence_number_sets(text: str) -> EvidenceNumbers:
    """근거 글의 숫자 (EvidenceNumbers). 표 숫자는 그 줄 단위로 본다 (_segments: 행 이름표 "(단위: 원)" → 가장 가까운 앞 표 머리).
    금액 단위(천원·백만원…)면 원 단위로 환산한 값도 인정하고, 개수 단위(천명·백만주…)면 개수로만 환산하며,
    %·배 같은 단위면 금액·개수로 인정하지 않는다.
    표 머리·이름표가 없으면 환산하지 않으므로, 모델이 근거에 없는 단위를 붙이면 그대로 걸린다."""
    out = EvidenceNumbers()
    for seg, unit in _segments(text):
        free = unit is _NO_CONTEXT
        kind_u, factor = (None, None) if free else (table_unit(unit) or (None, None))
        for v, kind in _scan(seg, True) + _scan(seg, False):
            v = round(v, 6)
            out.plain.add(v)
            if kind == UNIT or (free and kind not in (COUNT, FX)):
                out.unit.add(v)
            if kind == FX or (free and kind not in (COUNT, UNIT)):
                out.fx.add(v)
            # 맨숫자 원래 값을 개수로도 인정한다. 단 표 단위가 배수 붙은 개수 단위(천명·백만주…)면 환산값만.
            # 금액 표의 맨숫자는 개수로 둔다: "(단위 : 백만원)" 자기주식 소각 표의 "소각수량: 18,162,721"(주)처럼 열마다 단위가 다르다
            if kind == COUNT or (kind == BARE and unit != _UNKNOWN and kind_u != FX and not (kind_u == COUNT and factor != 1)):
                out.count.add(v)
            if kind == BARE and kind_u == UNIT:
                out.plain.add(round(v * factor, 6))
                out.unit.add(round(v * factor, 6))
            elif kind == BARE and kind_u == COUNT:
                out.count.add(round(v * factor, 6))
            elif kind == BARE and kind_u == FX:
                out.plain.add(round(v * factor, 6))
                out.fx.add(round(v * factor, 6))
    return out


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
            if any(a in t for a in ATTRIBUTION) or attributed_forecast(t, headline=True):
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


# 회사가 스스로 밝힌 계획·발언을 전하는 문장 (공시·발표 내용 자체가 사실이다)
COMPANY_STATEMENT = ("라고 밝혔", "고 밝혔", "고 발표", "고 설명", "계획이라고")


def prediction_text(texts: list[str], cfg: dict, names=frozenset()) -> str | None:
    """예측(전망·예상·추정·관측·가능성 …)을 핵심 사실로 쓴 글 (2026-11-09 "네이버 3분기 매출 3조5천143억원 전망" 카드).
    2026-11-18 N08 결정: 주체를 밝힌 전망 전달("KB증권은 ~로 전망했어요", 제목 "KB증권, ~ 전망")은 예측이 아니다
    (attributed_forecast). 주체 없는 전망("~로 전망돼요"·"영업이익은 ~로 전망했어요")은 그대로 걸린다.
    실제 실적을 예상치와 견준 표현(prediction_exempt)과 회사가 스스로 밝힌 계획·발언(COMPANY_STATEMENT)도 뺀다."""
    exempt = [re.compile(p) for p in cfg["prediction_exempt"]]
    # 문장마다 본다 (설명 문단의 한 문장이 전달 문장이라고 문단 전체를 빼지 않게)
    sentences = [s for t in texts for s in re.split(r"(?<=[.!?])\s+", t or "") if s.strip()]
    for t in sentences:
        if any(a in t for a in COMPANY_STATEMENT) or attributed_forecast(t, headline=True, names=names):
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
_QUOTED = re.compile(r"[‘'“\"「]([^‘’'“”\"「」]{1,80})[’'”\"」]")


# 메모의 질문을 되풀이하며 근거에 없다고 답하는 문장 (2026-11-19 K02 "다만 배당을 계속 늘리겠다는 계획은 이번 자료로는 확인되지 않아요")
_UNCONFIRMED = re.compile(r"(확인되지\s*않|확인할\s*수\s*없|확인이\s*어렵|찾지\s*못했|찾을\s*수\s*없|나와\s*있지\s*않|없었어요|없어요)")


def _restates_unconfirmed(sentence: str, term: str, memo_text: str) -> bool:
    """자료 범위 낱말(term, "계속" 등)이 메모 원문에서 온 말이고, 그 문장이 '자료로는 확인되지 않는다'는 답이면 범위 밖 단정이 아니다."""
    return bool(memo_text) and term in memo_text and bool(_UNCONFIRMED.search(sentence))


def strip_memo_quotes(text: str, memo_text: str) -> str:
    """따옴표 안의 글이 메모 원문에 그대로 있으면(띄어쓰기 무시) 지운다. memo_link가 메모 표현을 옮긴 부분은
    카드가 한 말이 아니라서 자료 범위(COVERAGE) 검사에서 뺀다 (2026-11-19 현대차 "메모의 '배당은 계속 늘려주나'" 카드).
    메모에 없는 따옴표 글(카드가 지어낸 인용)은 그대로 두고 검사한다."""
    memo = re.sub(r"\s+", "", memo_text or "")
    if not memo:
        return text or ""
    return _QUOTED.sub(lambda m: " " if re.sub(r"\s+", "", m.group(1)) in memo else m.group(0), text or "")


def text_dates(text: str) -> set[str]:
    """글 속 날짜를 YYYY-MM-DD로 ("2026-10-28", "2026.10.28", "2026년 10월 28일")."""
    out = set()
    for m in list(_DATE.finditer(text or "")) + list(_KDATE.finditer(text or "")):
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if d:
            out.add(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
    return out


def _banned_hit(texts: list[str], banned: list[str], cfg: dict, names=frozenset()) -> bool:
    """v1 _check_body와 같은 금지 표현 검사: 사전은 부분 문자열, 시제 패턴은 회사 발언 전달 문장을 뺀 문장에만."""
    if any(term in " ".join(texts) for term in banned):
        return True
    patterns = [re.compile(p) for p in cfg["banned_patterns"]]
    return any(not (any(a in t for a in ATTRIBUTION) or attributed_forecast(t, headline=True, names=names))
               and any(p.search(t) for p in patterns) for t in texts)


def _ev_text(e: Evidence) -> str:
    return f"{e.candidate.title} {e.shown_text} {e.candidate.date}"


_EARNINGS_METRIC = re.compile(r"(매출(?:액)?|영업이익|순이익|세전이익|법인세비용차감전)")


def _earnings_figure(text: str) -> bool:
    """실적 숫자(금액·%)가 있는 글인가. 제품 이름 속 맨숫자("CT-P13 바이오시밀러 외" 매출, 2026-11-19 M023)는 실적이 아니다."""
    return any(kind in (UNIT, PCT) for _, kind in _card_scan(text))


def _earnings_basis(e: Evidence) -> str:
    """DART 잠정실적 보고서명의 연결/별도 기준.

    DART는 연결 공시 제목에 '연결재무제표기준'을 붙이고, 같은 날의
    '영업(잠정)실적(공정공시)'은 별도 재무제표 수치다.
    """
    title = re.sub(r"\s+", "", e.candidate.title)
    if e.candidate.kind == "disclosure" and e.candidate.doc == "event" and "연결재무제표기준영업" in title:
        return "연결"
    if e.candidate.kind == "disclosure" and e.candidate.doc == "event" and "영업(잠정)실적(공정공시)" in title:
        return "별도"
    # 뉴스·정기보고서는 근거에 기준이 명시된 경우에만 검사한다.
    hay = re.sub(r"\s+", "", _ev_text(e))
    connected = "연결기준" in hay or "연결재무제표" in hay
    separate = "별도기준" in hay or "별도재무제표" in hay
    if connected != separate:
        return "연결" if connected else "별도"
    return ""


def check_card_v2(card, evidence: list[Evidence], banned: list[str], cfg: dict | None = None,
                  memo_text: str = "") -> list[str]:
    """v2 카드(CardV2) 검사. v1과 같은 이유 코드를 쓰고, 숫자·날짜는 facts 문장마다 그 문장의 evidence_id 근거 하나와 대조한다
    (다른 근거의 숫자를 섞으면 NUMBER). "비교 자료 없음"(evidence_id "")만 근거 없이 허용한다.
    - FORMAT_TITLE headline · FORMAT_WHEN when(YYYY-MM-DD, 쓴 근거의 날짜나 근거 본문에 적힌 날짜)
    - FORMAT_SUMMARY facts 개수(1~max_sentences, 비교 자료 없음 제외)·문장 길이·[E#] 표시
    - FORMAT_REASON memo_link(한 문장, reason_max자) · SOURCE 번호·sources 목록·비교용 근거만으로 만든 카드
    - BANNED · PREDICTION(headline·facts·memo_link) · LOW_CONF. FACT_OVERLAP(v1의 evidence.fact 대조)는 v2에 없다.
    memo_text: 항목의 메모 문장. memo_link의 숫자만 쓴 근거나 메모 문장 중 하나에 있으면 인정한다
    (memo_link는 메모 표현을 따옴표로 인용한다: "메모의 '13% 아래' …", 2026-11-18). headline·facts·설명은 근거만."""
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
    # 설명 문단은 문장마다 (금지 표현 예외·예측 검사를 문장 단위로)
    texts = [card.headline, *(t for t, _ in facts), card.memo_link] + [s for s in re.split(r"(?<=[.!?])\s+", exp) if s.strip()]
    names = forecast_subjects(t for t, _ in facts)       # 제목 맨 앞·소유격 주체로 인정할 전망 주체 (사실 문장에서)
    if _banned_hit(texts, banned, cfg, names):
        codes.append("BANNED")
    # 숫자: 문장마다 그 근거 하나에만. 제목·memo_link는 쓴 근거 전체 안에서
    union = EvidenceNumbers()
    for e in cited:
        union |= evidence_number_sets(_ev_text(e))
    link = union.copy()
    link |= evidence_number_sets(memo_text)
    bad = any(eid in ids and not evidence_number_sets(_ev_text(ids[eid])).supports(t) for t, eid in facts)
    if bad or not (union.supports(card.headline) and union.supports(exp) and link.supports(card.memo_link)):
        codes.append("NUMBER")
    if cfg.get("require_financial_basis"):
        # 잠정실적 숫자는 문장마다 기준을 쓰고, 한 카드에서는 한 기준만 쓴다.
        fact_bases: list[str] = []
        for text, eid in facts:
            basis = _earnings_basis(ids[eid]) if eid in ids else ""
            if basis and _EARNINGS_METRIC.search(text) and _earnings_figure(text):
                fact_bases.append(basis)
                if basis not in text:
                    codes.append("FINANCIAL_BASIS")
        if len(set(fact_bases)) > 1:
            codes.append("FINANCIAL_BASIS")
        if exp and _EARNINGS_METRIC.search(exp) and _earnings_figure(exp) and len(set(fact_bases)) == 1:
            if fact_bases[0] not in exp:
                codes.append("FINANCIAL_BASIS")
    # 사실 문장·설명 문장마다 주체 (제목은 "출처, …" 형식을 따로 보고, memo_link는 메모와의 연결이라 보지 않는다)
    subject_on = cfg.get("fact_subject", True)
    no_subject = [t for t in [t for t, _ in facts] + [s for s in re.split(r"(?<=[.!?])\s+", exp) if s.strip()]
                  if subject_on and missing_subject(t)]
    # "~로 전망했어요"처럼 주체만 빠진 전망 전달은 예측(PREDICTION)이 아니라 주체 빠짐(ATTRIBUTION)으로 본다 (한 번 고쳐 쓸 수 있게)
    if cfg["prediction_terms"] and prediction_text([t for t in texts if t not in no_subject], cfg, names):
        codes.append("PREDICTION")
    if no_subject:
        codes.append("ATTRIBUTION")
    # 자료 범위 밖을 전제로 한 말 ("처음", "줄곧" …): 그 말이 쓴 근거에 그대로 있을 때만 (2026-11-11, 범위 밖 원인·추이를 단정하지 않게)
    def outside(text: str, hay: str) -> bool:
        return any(term in s and term not in hay and not _restates_unconfirmed(s, term, memo_text)
                   for s in re.split(r"(?<=[.!?])\s+", text or "") for term in cfg["coverage_terms"])
    all_ev = " ".join(_ev_text(e) for e in cited)
    if (any(eid in ids and outside(t, _ev_text(ids[eid])) for t, eid in facts)
            or outside(card.headline, all_ev) or outside(strip_memo_quotes(card.memo_link, memo_text), all_ev)
            or outside(exp, all_ev)):
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
