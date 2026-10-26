"""생성된 메모 자동 검사 — 사람 단위로 돌리고, 실패하면 그 사람만 다시 생성한다.

검사 항목 (지시서 3번):
- 인당 10개, 배정 슬롯·기업별 슬롯 수 일치. 배정 기업 언급(B5·B7·B10 예외), B10은 다른 종목만 언급
- evidence_ids가 근거 자료에 실제로 있음
- 메모 속 숫자·날짜가 근거 값과 일치 (추적형 A와 혼합형 C. 폴백 B는 개인 매매·감정이라 제외)
- 금지 표현·자기소개 0건
- 같은 사람 안 유사도 0.9 이상 쌍은 표시만 (자동 삭제 안 함)
"""

from __future__ import annotations

import difflib
import re
from datetime import date

from .common import ALIASES, OTHER_STOCKS

# ─────────────────────────────────────────────────────────────
# 숫자 해석: "7만1500", "79조 1,400억", "3.2%", "2.8배" → 값·정밀도·단위
# ─────────────────────────────────────────────────────────────
UNITS = {"천억": 1e11, "백억": 1e10, "십억": 1e9, "천만": 1e7, "백만": 1e6, "십만": 1e5,
         "조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3, "백": 1e2}
NUM = re.compile(r"(?<![A-Za-z0-9.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![A-Za-z])\s?(천억|백억|십억|천만|백만|십만|조|억|만|천|백)?")
SUFFIX = [
    ("pctp", re.compile(r"\s?(%p|%포인트|퍼센트포인트|포인트|bp)")),
    ("pct", re.compile(r"\s?(%|퍼센트|퍼|프로)")),
    ("won", re.compile(r"\s?원")),
    ("ratio", re.compile(r"\s?배")),
    ("period", re.compile(r"\s?(주일|거래일|개월|달|년간|일간|일선|일 ?평균|일 ?연속|일째|일 동안|일 만에)")),
    ("quarter", re.compile(r"\s?(분기|Q|q)")),
    ("year", re.compile(r"\s?년")),
    ("month", re.compile(r"\s?월")),
    ("day", re.compile(r"\s?일")),
    ("week_or_shares", re.compile(r"\s?주")),
    ("count", re.compile(r"\s?(번째|번|회|개|명|가지|등|위|살|세|대|시|분|층|호|차)")),
    ("usd", re.compile(r"\s?(달러|불)")),
]


def parse_numbers(text: str) -> list[dict]:
    out: list[dict] = []
    for m in NUM.finditer(text):
        int_part, frac, unit = m.group(1), m.group(2), m.group(3)
        digits = int_part.replace(",", "")
        v = float(digits + ("." + frac if frac else ""))
        mult = UNITS.get(unit, 1.0)
        if frac:
            prec = 10 ** -len(frac)
        else:
            stripped = digits.rstrip("0")
            prec = 10 ** (len(digits) - len(stripped)) if len(digits) >= 4 and stripped else 1
        rec = {"value": v * mult, "precision": prec * mult, "unit_mult": mult, "start": m.start(), "end": m.end(),
               "raw": m.group(0), "kind": "plain"}
        prev = out[-1] if out else None
        # "7만1500", "79조 1,400억", "6만9천" → 앞 숫자와 합친다
        if prev and prev["unit_mult"] > mult and prev["end"] >= m.start() - 1 and prev["kind"] == "plain" \
                and not text[prev["end"]:m.start()].strip():
            prev.update(value=prev["value"] + rec["value"], precision=rec["precision"], unit_mult=mult, end=m.end(),
                        raw=text[prev["start"]:m.end()])
            rec = prev
        else:
            out.append(rec)
        tail = text[rec["end"]:rec["end"] + 8]
        for kind, pat in SUFFIX:
            if pat.match(tail):
                rec["kind"] = kind
                break
    return out


DATE_PATTERNS = [
    re.compile(r"(?<!\d)(20\d{2})\s?[-./년]\s?(\d{1,2})\s?[-./월]\s?(\d{1,2})일?"),
    re.compile(r"(?<!\d)(\d{1,2})\s?월\s?(\d{1,2})\s?일"),
    re.compile(r"(?<![\d.])(\d{1,2})/(\d{1,2})(?![\d/])"),
]


def find_dates(text: str) -> list[tuple[int | None, int, int, tuple[int, int]]]:
    """(연도 또는 None, 월, 일, 위치) 목록. 겹치는 표기는 앞의 패턴이 우선."""
    found, taken = [], []
    for pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            g = m.groups()
            y, mo, d = (int(g[0]), int(g[1]), int(g[2])) if len(g) == 3 else (None, int(g[0]), int(g[1]))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                found.append((y, mo, d, (m.start(), m.end())))
                taken.append((m.start(), m.end()))
    return found


RELATIVE_PCT = {3, 5, 7, 10, 15, 20, 25, 30, 40, 50}


def _close(v: float, e: float, prec: float) -> bool:
    return abs(abs(v) - abs(e)) <= max(prec, abs(e) * 0.005) + 1e-9


def number_problems(text: str, evidence: list[dict], as_of: str, price_range: tuple[float, float] | None,
                    allow_price_levels: bool) -> list[str]:
    """근거에 없는 숫자·날짜를 찾는다. evidence는 슬롯에 붙은 근거 항목들(numbers·dates·text)."""
    as_of_d = date.fromisoformat(as_of)
    ev_dates = {date.fromisoformat(d) for e in evidence for d in e.get("dates", [])} | {as_of_d}
    ev_nums = [float(n) for e in evidence for n in e.get("numbers", []) if n is not None]
    ev_nums += [n["value"] for e in evidence for n in parse_numbers(e.get("text", ""))]
    problems = []
    spans = []
    for y, mo, d, span in find_dates(text):
        spans.append(span)
        if not any(x.month == mo and x.day == d and (y is None or x.year == y) for x in ev_dates):
            problems.append(f"근거에 없는 날짜 '{text[span[0]:span[1]]}'")
    months_ok = {((as_of_d.year * 12 + as_of_d.month - 1 + k) % 12) + 1 for k in range(-12, 4)}
    for n in parse_numbers(text):
        if any(s <= n["start"] < e for s, e in spans):
            continue
        v, kind, raw = n["value"], n["kind"], n["raw"].strip()
        if kind in ("week_or_shares", "count", "period"):
            continue
        if kind == "quarter" and 1 <= v <= 4:
            continue
        if kind == "year":  # "26년"(연도) 또는 "국고채 10년"·"3년 보유"(기간)
            yr = v + 2000 if v < 100 else v
            if v <= 30 or as_of_d.year - 3 <= yr <= as_of_d.year + 1:
                continue
        if kind == "month" and v in months_ok:
            continue
        if kind == "day":
            if any(x.day == v for x in ev_dates):
                continue
            problems.append(f"근거에 없는 날짜 '{raw}일'")
            continue
        if kind in ("pct", "pctp"):
            # "20% 가까이"처럼 근거 값(18.8%)을 어림한 표현은 허용: 0.5%p 또는 10% 이내
            if any(abs(abs(v) - abs(e)) <= max(0.5, abs(e) * 0.1) for e in ev_nums):
                continue
            if allow_price_levels and v in RELATIVE_PCT:  # 가격 조건의 상대 표현 "10% 빠지면"
                continue
            problems.append(f"근거와 다른 비율 '{raw}{'%p' if kind == 'pctp' else '%'}'")
            continue
        if kind == "ratio" and (v == 2 or any(abs(v - e) <= max(n["precision"], 0.1) for e in ev_nums)):
            continue
        if any(_close(v, e, n["precision"]) for e in ev_nums):
            continue
        if allow_price_levels and price_range and price_range[0] * 0.5 <= v <= price_range[1] * 1.5:
            continue
        problems.append(f"근거에 없는 숫자 '{raw}'")
    return problems


# ─────────────────────────────────────────────────────────────
# 기업 언급
# ─────────────────────────────────────────────────────────────
_ALL = sorted([(a.lower(), c) for c, al in ALIASES.items() for a in al] + [(s.lower(), s) for s in OTHER_STOCKS],
              key=lambda x: -len(x[0]))
# 별명 → 대표 이름 (다른 종목은 같은 회사 별칭을 하나로)
OTHER_CANON = {"엘지에너지솔루션": "LG에너지솔루션", "LG엔솔": "LG에너지솔루션", "엔솔": "LG에너지솔루션",
               "삼성바이오": "삼성바이오로직스", "삼바": "삼성바이오로직스", "현대자동차": "현대차", "포스코홀딩스": "POSCO홀딩스",
               "포스코": "POSCO홀딩스", "한전": "한국전력", "엔씨": "엔씨소프트", "신한금융": "신한지주", "하나금융": "하나금융지주",
               "알파벳": "구글"}


def mentions(text: str) -> list[str]:
    """메모에 나온 회사 이름(우리 4곳은 표준 이름, 그 밖은 OTHER_STOCKS 이름). 긴 이름부터 찾아 '삼성바이오'를 '삼성'으로 잘못 세지 않는다."""
    s = text.lower()
    found: list[str] = []
    for alias, comp in _ALL:
        ascii_alias = alias.isascii()
        pat = (r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])") if ascii_alias else re.escape(alias)
        for m in list(re.finditer(pat, s)):
            if "\0" in s[m.start():m.end()]:
                continue
            s = s[:m.start()] + "\0" * (m.end() - m.start()) + s[m.end():]
            name = OTHER_CANON.get(comp, comp)
            if name not in found:
                found.append(name)
    return found


# ─────────────────────────────────────────────────────────────
# 금지 표현·자기소개
# ─────────────────────────────────────────────────────────────
FORBIDDEN = [re.compile(p) for p in (r"분석\s?해\s?(주세요|줘|주십시오)", r"종합적으로", r"에\s?대해(서)?\s?알려\s?(주세요|줘|주십시오)")]
SELF_INTRO = [re.compile(p) for p in (
    r"(자|인|원|생|님|맘|마|빠|부|사|가|미|장)\s?(으로서|로서)(?=\s|,|$)",  # 투자자로서·직장인으로서 (배당주로서는 허용)
    r"제\s?투자\s?(목적|성향|스타일|방식|원칙)은",
    r"내\s?투자\s?(목적|성향)은",
    r"(저는|나는)\s?\d{2}\s?(대|살|세)",
    r"^(저는|나는)\s.{0,20}(입니다|이에요|예요)",
)]


def style_problems(text: str) -> list[str]:
    out = [f"금지 표현 '{m.group(0)}'" for p in FORBIDDEN for m in [p.search(text)] if m]
    out += [f"자기소개 표현 '{m.group(0)}'" for p in SELF_INTRO for m in [p.search(text)] if m]
    return out


def similar_pairs(memos: list[dict], threshold: float) -> list[tuple[int, int, float]]:
    pairs = []
    for i in range(len(memos)):
        for j in range(i + 1, len(memos)):
            r = difflib.SequenceMatcher(None, memos[i]["memo_text_raw"], memos[j]["memo_text_raw"]).ratio()
            if r >= threshold:
                pairs.append((memos[i]["slot"], memos[j]["slot"], round(r, 3)))
    return pairs


# ─────────────────────────────────────────────────────────────
# 사람 단위 검사
# ─────────────────────────────────────────────────────────────
MENTION_EXEMPT = {"B5", "B7", "B10"}
NUMBER_CHECKED = ("A", "C")
PRICE_LEVEL_TYPES = {"A2", "C1", "C4"}
MAX_CHARS = 300


def check_person(design: dict, memos: list[dict], known_ids: set[str], packs_items: dict[str, dict],
                 price_ranges: dict[str, tuple[float, float]], similarity: float) -> tuple[list[str], list[str]]:
    """(문제 목록, 표시 목록). 문제가 하나라도 있으면 재생성 대상."""
    problems: list[str] = []
    want = {s["slot"]: s for s in design["slots"]}
    got = {m["slot"]: m for m in memos}
    if len(memos) != len(want) or set(got) != set(want):
        problems.append(f"메모 수·슬롯 불일치: 받은 슬롯 {sorted(got)} / 배정 {sorted(want)}")
    counts_want, counts_got = {}, {}
    for s in want.values():
        counts_want[s["target_company"]] = counts_want.get(s["target_company"], 0) + 1
    for m in got.values():
        counts_got[m["target_company"]] = counts_got.get(m["target_company"], 0) + 1
    if counts_want != counts_got:
        problems.append(f"기업별 슬롯 수 불일치: {counts_got} ≠ {counts_want}")
    for slot, m in sorted(got.items()):
        s = want.get(slot)
        if s is None:
            continue
        text = m["memo_text_raw"]
        tag = f"슬롯 {slot}({s['sentence_type']})"
        if not text.strip():
            problems.append(f"{tag}: 빈 메모")
            continue
        if len(text) > MAX_CHARS:
            problems.append(f"{tag}: {len(text)}자 — 메모장 메모치고 너무 김")
        ment = m["companies_mentioned"]
        if s["sentence_type"] == "B10":
            if s["target_company"] in ment or not [c for c in ment if c != s["target_company"]]:
                problems.append(f"{tag}: B10은 배정 기업 없이 다른 종목만 말해야 함 (언급: {ment})")
        elif s["sentence_type"] not in MENTION_EXEMPT and s["target_company"] not in ment:
            problems.append(f"{tag}: 배정 기업 {s['target_company']}(또는 별명) 언급 없음")
        missing = [i for i in m["evidence_ids"] if i not in known_ids]
        if missing:
            problems.append(f"{tag}: 근거 자료에 없는 ID {missing[:3]}")
        if s["sentence_type"][0] in NUMBER_CHECKED:
            ev = [packs_items[k] for k in s.get("evidence_keys", []) if k in packs_items]
            problems += [f"{tag}: {p}" for p in number_problems(
                text, ev, s["as_of_date"], price_ranges.get(s["target_company"]),
                s["sentence_type"] in PRICE_LEVEL_TYPES)]
        problems += [f"{tag}: {p}" for p in style_problems(text)]
    flags = [f"유사 메모: 슬롯 {a}↔{b} (유사도 {r})" for a, b, r in similar_pairs(list(got.values()), similarity)]
    return problems, flags
