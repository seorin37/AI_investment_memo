"""화면 대본 문장 → TTS에 보낼 읽기 문장 (숫자·날짜·단위·기호를 한글로).

화면에는 '180,500원 · 3.1% · 11월 18일'을 그대로 보여 주고, 소리는 '십팔만 오백 원 · 삼 점 일 퍼센트 · 십일월 십팔일'로 만든다.
Fish Audio의 normalize도 숫자를 읽지만 한국어 단위·고유어 수사(세 곳, 두 배)를 늘 맞게 읽는지 확인되지 않아 우리 쪽에서 먼저 바꾼다.
"""
from __future__ import annotations

import re

DIG = "영일이삼사오육칠팔구"
SMALL = ["", "십", "백", "천"]
BIG = ["", "만", "억", "조", "경"]
NATIVE_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
NATIVE_TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
MONTH = {6: "유월", 10: "시월"}
TIGHT = {"년", "일"}                                            # 띄우지 않고 붙여 읽는 단위 (십팔일, 이천이십육년)

# 수사 뒤에 오는 말. 고유어로 읽는 말(세 곳·두 배)과 한자어로 읽는 말(삼 개월·이천 원)
SINO_UNITS = ["개월", "달러", "퍼센트포인트", "퍼센트", "분기", "거래일", "년", "월", "일", "원", "주", "위", "분", "초", "대",
              "포인트", "배럴", "층", "호", "회", "차"]
NATIVE_UNITS = ["번째", "가지", "시간", "군데", "차례", "종목", "마리", "개", "곳", "명", "번", "살", "권", "잔", "건", "달", "배", "줄", "시"]
_UNIT_RE = "|".join(sorted(SINO_UNITS + NATIVE_UNITS, key=len, reverse=True))
# 숫자 바로 뒤 조사: 화면 문장(2,510.40으로)과 읽는 소리(점 사)의 받침이 다를 수 있어 소리에 맞춰 다시 고른다.
# 이/가는 서술격 조사(원이었어요)와 헷갈려서 다루지 않는다.
JOSA = {"으로": ("으로", "로"), "로": ("으로", "로"), "은": ("은", "는"), "는": ("은", "는"),
        "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와")}
NUM = re.compile(rf"(?P<sign>[+\-−])?(?P<num>\d[\d,]*(?:\.\d+)?)(?P<pct>%p|%)?(?P<big>조|억|만|천)?(?:\s*(?P<unit>{_UNIT_RE}))?"
                 r"(?P<josa>으로|로|은|는|을|를|과|와)?(?(josa)(?=$|[^가-힣]|는|도|만|서|부터))")
ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
DOT_DATE = re.compile(r"(?<![\d.])(1[0-2]|0?[1-9])\.(0[1-9]|[12]\d|3[01])(?![\d%]|\s*(?:배|조|억|만|원|달러|포인트))")
SYMBOLS = [("→", " "), ("※", ""), ("·", ", "), ("/", " "), ("&", " 앤 "), ("“", ""), ("”", ""), ('"', ""), ("‘", ""),
           ("’", ""), ("'", ""), ("(", " "), (")", " "), ("[", " "), ("]", " "), ("…", "."), ("―", " "), ("—", " ")]


def sino(n: int) -> str:
    """정수를 한자어 수로 (180500 → 십팔만 오백, 10000 → 만, 100000000 → 일억)."""
    if n == 0:
        return "영"
    groups, out = [], []
    while n:
        groups.append(n % 10000)
        n //= 10000
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        s = ""
        for p in range(3, -1, -1):
            d = g // (10 ** p) % 10
            if d == 0:
                continue
            s += ("" if d == 1 and p > 0 else DIG[d]) + SMALL[p]
        if i == 1 and g == 1:
            s = ""                                          # 일만 → 만
        out.append(s + BIG[i])
    return " ".join(out)


def native(n: int) -> str:
    """1~99를 고유어 관형형으로 (세, 스무, 서른다섯). 100 이상은 한자어."""
    if not 0 < n < 100:
        return sino(n)
    if n == 20:
        return "스무"
    return NATIVE_TENS[n // 10] + NATIVE_ONES[n % 10]


def decimal(num: str) -> str:
    whole, _, frac = num.replace(",", "").partition(".")
    frac = frac.rstrip("0")
    s = sino(int(whole))
    return f"{s} 점 {''.join(DIG[int(c)] for c in frac)}" if frac else s


def fit_josa(word: str, josa: str | None) -> str:
    """읽는 소리의 마지막 글자 받침에 맞춰 조사를 붙인다 (점 사 + 으로 → 점 사로, 칠 + 으로 → 칠로)."""
    if not josa:
        return word
    ch = word.rstrip()[-1:]
    final = (ord(ch) - 0xAC00) % 28 if "가" <= ch <= "힣" else -1
    if final < 0:
        return word + josa
    with_final, without = JOSA[josa]
    if with_final == "으로":
        return word + ("으로" if final not in (0, 8) else "로")      # ㄹ 받침(8)은 '로'
    return word + (with_final if final else without)


def _sub_number(m: re.Match) -> str:
    return fit_josa(_number_word(m), m.group("josa"))


def _number_word(m: re.Match) -> str:
    sign, num, pct, big, unit = m.group("sign"), m.group("num"), m.group("pct"), m.group("big"), m.group("unit")
    raw = num.replace(",", "")
    is_int = "." not in raw
    value = int(raw) if is_int else None
    pre = {"+": "플러스 ", "-": "마이너스 ", "−": "마이너스 "}.get(sign or "", "")
    if pct:
        word = decimal(num) + (" 퍼센트포인트" if pct == "%p" else " 퍼센트")
        return pre + word + (f" {unit}" if unit else "")
    if big:
        head = "" if (is_int and value == 1 and big in ("만", "천")) else decimal(num)
        return pre + head + big + (f" {unit}" if unit else "")
    if unit == "월" and is_int:
        return pre + (MONTH[value] if value in MONTH else sino(value) + "월")
    if unit == "번째" and is_int and value == 1:
        return pre + "첫 번째"
    if unit in NATIVE_UNITS and is_int:
        return pre + native(value) + " " + unit
    word = decimal(num)
    return pre + word + ((unit if unit in TIGHT else f" {unit}") if unit else "")


def _sign_context(text: str) -> str:
    """숫자 사이 '-'(범위·날짜)는 부호로 읽지 않게 먼저 바꾼다."""
    text = re.sub(r"\s*[~∼]\s*", "부터 ", text)
    return re.sub(r"(?<=\d)-(?=\d)", " 에서 ", text)


def pronounce(text: str, words: dict[str, str] | None) -> str:
    for k in sorted(words or {}, key=len, reverse=True):
        text = text.replace(k, words[k])
    return text


def to_speech(text: str, words: dict[str, str] | None = None) -> str:
    t = pronounce(text, words)
    t = ISO_DATE.sub(lambda m: f"{int(m.group(1))}년 {int(m.group(2))}월 {int(m.group(3))}일", t)
    t = DOT_DATE.sub(lambda m: f"{int(m.group(1))}월 {int(m.group(2))}일", t)
    t = _sign_context(t)
    for a, b in SYMBOLS:
        t = t.replace(a, b)
    t = NUM.sub(_sub_number, t)
    t = re.sub(r"\s+([,.?!])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()
