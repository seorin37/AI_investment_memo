"""금융사 건전성 비율 추출 → financials_fin.bis_ratio · kics_ratio · ncr_ratio.

정기보고서 청크(disclosure_chunks, 읽기 전용)의 비율 표에서 그 보고서 기간(당기) 값을 찾는다.
  - bis_ratio  : 은행·은행지주 BIS 총자본비율 (`총자본비율(A/B)`, `BIS자기자본비율`, `BIS기준 자기자본비율`)
  - kics_ratio : 보험사 지급여력비율 (K-ICS, 경과조치 적용 후 = 공시 기본값)
  - ncr_ratio  : 증권사 순자본비율 (`순자본비율[(A-B)/C]`)

규칙 (docs/financials-ratios.md):
1. 행: 비율 이름으로 시작하는 표 행만 쓴다. 문장 속 언급·제도 설명(`총자본비율 8.0% 이상`)·셀 값(`지표명: BIS기준 자기자본비율`)은 쓰지 않는다.
2. 열: 표의 **첫 번째 값 열**만 쓰고, 그 열 머리가 보고서 기간과 맞아야 한다.
   `제77기 반기`·`2026년 6월 말`·`FY2026 2Q`·`2026.06`·`'26년2분기말`처럼 기간 종류(1분기·반기·3분기·연간)와 연도가 맞는지 본다.
   `제N기` 표는 첫 열의 N이 표 안에서 가장 커야 한다. 열 머리가 기간이 아니면 표 제목의 기준일(`기준일 : 2026.06.30`)을 본다.
3. 섹션: `재무건전성` → `이사의 경영진단` → 나머지 순. 재무제표 주석(소수 표기 0.1478)·임원 보수·감사 섹션과
   정정 공시의 `정정 전·후` 대조 청크는 쓰지 않는다.
4. 같은 순위 안에서는 보고서 앞쪽 표를 쓴다 (지주·연결 표가 자회사·별도 표보다 앞에 온다).
   다른 후보 값은 출처에 남기고, 같은 값이 보고서 다른 곳(다른 표·본문 문장)에 또 나오면 `corroborated`로 표시한다.
5. 범위를 벗어나면 None + 사유. 잠정치 표시는 `provisional`로 남긴다 (값은 쓴다, 정정 공시가 들어오면 다시 실행해 바뀐다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class RatioSpec:
    column: str
    name: str
    row_re: re.Pattern
    exclude_row_re: re.Pattern | None
    low: Decimal
    high: Decimal
    keywords: tuple[str, ...]  # 청크 1차 선별 (position(...) > 0)


SPECS: dict[str, RatioSpec] = {
    "bis_ratio": RatioSpec(
        column="bis_ratio",
        name="BIS 총자본비율",
        row_re=re.compile(r"(?:BIS\s*(?:기준\s*)?)?총\s*(?:자기\s*)?자본\s*비율|BIS\s*(?:기준\s*)?자기\s*자본\s*비율|BIS\s*비율"
                          r"|자기\s*자본\s*비율\s*\(\s*A\s*/\s*B\s*\)"),
        exclude_row_re=re.compile(r"보통주|기본\s*자본|보완|하락|민감도|규제|최소|기준\s*\(B\)"),
        low=Decimal("1"), high=Decimal("60"),
        keywords=("총자본비율", "BIS"),
    ),
    "kics_ratio": RatioSpec(
        column="kics_ratio",
        name="지급여력비율(K-ICS)",
        row_re=re.compile(r"지급\s*여력\s*비율"),
        exclude_row_re=re.compile(r"경과\s*조치\s*(?:前|전|적용\s*전)|RBC|기본\s*자본|적용\s*전"),
        low=Decimal("10"), high=Decimal("3000"),
        keywords=("지급여력비율",),
    ),
    "ncr_ratio": RatioSpec(
        column="ncr_ratio",
        name="순자본비율(NCR)",
        row_re=re.compile(r"순\s*자본\s*비율"),
        exclude_row_re=None,
        low=Decimal("10"), high=Decimal("99999"),
        keywords=("순자본비율",),
    ),
}

# 금융 세부 업종 → 채울 비율 (나머지 비율은 not_applicable)
COLUMN_FOR_FIN_TYPE = {"bank": "bis_ratio", "holding": "bis_ratio", "insurance": "kics_ratio", "securities": "ncr_ratio"}
# 업종은 맞지만 그 비율을 공시하지 않는 회사 (은행이 없는 금융지주). 보고서에 나오는 BIS는 자회사(저축은행) 값이거나 업계 통계다
NOT_APPLICABLE_SYMBOLS = {
    "bis_ratio": {
        "071050": "한국금융지주 — 은행 자회사가 없는 금융지주 (보고서의 BIS는 한국투자저축은행 값)",
        "138040": "메리츠금융지주 — 은행 자회사가 없는 금융지주 (보고서의 총자본비율은 금융지주 업계 통계)",
    },
}


def target_column(symbol: str, fin_type: str | None) -> str | None:
    """이 회사가 채워야 할 비율 컬럼. 없으면 None (세 비율 모두 not_applicable)."""
    column = COLUMN_FOR_FIN_TYPE.get(fin_type or "")
    if column and symbol in NOT_APPLICABLE_SYMBOLS.get(column, {}):
        return None
    return column

CORRECTION_RE = re.compile(r"정정\s*[전후]")
EXCLUDED_SECTION_RE = re.compile(r"재무제표\s*주석|임원|감사|이사회")
PROVISIONAL_RE = re.compile(r"잠\s*정")
NUMBER_RE = re.compile(r"\s*(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+,\d{1,2}(?!\d)|\d+(?:\.\d+)?)\s*%?")
# 행 이름 뒤 `|` 전까지 (예: `(A/B)`, ` 주1,2)`, `: (3/4)*100`). `:`는 `(` 앞일 때만 허용 — `(단위 : 억원)` 제목을 행으로 보지 않는다
ROW_TAIL = r"(?:[^|:\n]|:(?=\s*\())"
HEADER_KEY_RE = re.compile(r"열:\s*([^|]{1,40}?)\s*\|")
FLAT_HEADER_RE = re.compile(r"구\s*분[^|:\n]{0,10}\|")
DATE_RE = re.compile(r"(20\d\d)\s*[.\-년]\s*(\d{1,2})\s*[.\-월]\s*(\d{1,2})")


def section_rank(section: str) -> int | None:
    if EXCLUDED_SECTION_RE.search(section):
        return None
    if "재무건전성" in section:
        return 0
    if "경영진단" in section:
        return 1
    return 2


def parse_number(text: str) -> Decimal | None:
    """`1,912.64%`·`208.2`·`13,65`(소수점 오타) → Decimal."""
    raw = text.strip().rstrip("%").strip()
    if re.fullmatch(r"\d+,\d{1,2}", raw):
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class PeriodLabel:
    kind: str  # month · q1 · half · q3 · annual
    year: int | None
    month: int | None
    term: int | None  # 제N기


def classify_label(label: str) -> PeriodLabel | None:
    """열 머리를 기간으로 해석한다. 기간이 아니면 None."""
    spaced = re.sub(r"\s+", " ", label)
    s = spaced.replace(" ", "")
    term_m = re.search(r"제(\d{1,3})(?:\((?:당|전|전전)\))?기", s)
    term = int(term_m.group(1)) if term_m else None
    year_m = re.search(r"(?<!\d)(20\d\d)(?!\d)", spaced)  # `FY2025 1분기`: 공백을 지우기 전에 찾는다
    year = int(year_m.group(1)) if year_m else None
    if year is None:
        short = re.search(r"'?(?<!\d)(\d\d)년", s)
        year = 2000 + int(short.group(1)) if short else None
    month_m = re.search(r"20\d\d\.(\d{1,2})(?!\d)", s) or re.search(r"(?<!\d)(\d{1,2})월", s)
    if month_m and year is not None:
        return PeriodLabel("month", year, int(month_m.group(1)), term)
    if term is None and year is None:
        return None
    if re.search(r"1분기|1Q", s):
        kind = "q1"
    elif re.search(r"3분기|3Q", s):
        kind = "q3"
    elif re.search(r"반기|2분기|2Q", s):
        kind = "half"
    else:
        kind = "annual"  # `제76기`, `2025년`, `2025년말`, `FY2025`, `4분기`
    return PeriodLabel(kind, year, None, term)


def is_current(label: PeriodLabel, period_end: str, period_type: str) -> bool:
    year, month = int(period_end[:4]), int(period_end[5:7])
    if label.kind == "month":
        return label.year == year and label.month == month
    if label.kind != period_type:
        return False
    if label.year is None:
        return True
    standard = {3: "q1", 6: "half", 9: "q3", 12: "annual"}.get(month) == period_type
    return label.year == year if standard else abs(label.year - year) <= 1


@dataclass
class Candidate:
    chunk_index: int
    section: str
    rank: int
    position: int
    row: str
    label: str
    value: Decimal
    provisional: bool


@dataclass
class RatioResult:
    value: Decimal | None
    source: dict = field(default_factory=dict)
    null_code: str | None = None

    @property
    def reason(self) -> str | None:
        return self.source.get("reason")


def _cells(text: str, start: int) -> list[tuple[str | None, str]]:
    """`|` 뒤 셀들을 (열 머리 or None, 숫자 문자열)로. 숫자가 아닌 셀에서 멈춘다."""
    cells: list[tuple[str | None, str]] = []
    rest = text[start:]
    for part in rest.split("|")[1:]:
        label = None
        body = part
        labeled = re.match(r"\s*([^:|\n]{1,40}?)\s*:\s*(?=\d)", part)
        if labeled:
            label, body = labeled.group(1), part[labeled.end():]
        number = NUMBER_RE.match(body)
        if not number:
            break
        cells.append((label, number.group("num")))
        if body[number.end():].strip():  # 셀이 숫자 뒤 다음 행 이름으로 이어지면 이 행은 여기까지
            break
        if len(cells) >= 8:
            break
    return cells


def _flat_header(text: str, row_start: int) -> list[str]:
    """평문 표(`구 분 | 제71기 반기 | 제70기 | …  지급여력비율(A/B) | 208.2 | …`)의 열 머리."""
    headers = list(FLAT_HEADER_RE.finditer(text, max(0, row_start - 1500), row_start))
    if not headers:
        return []
    segment = text[headers[-1].end():row_start]
    return [cell.strip() for cell in segment.split("|")]


def _title_date(text: str, row_start: int) -> tuple[int, int] | None:
    found = list(DATE_RE.finditer(text, max(0, row_start - 400), row_start))
    if not found:
        return None
    return int(found[-1].group(1)), int(found[-1].group(2))


def _row_starts(spec: RatioSpec, text: str):
    pattern = re.compile(rf"(?:{spec.row_re.pattern}){ROW_TAIL}{{0,40}}\|")
    for match in pattern.finditer(text):
        if match.start() and re.match(r"[가-힣]", text[match.start() - 1]):
            continue  # 낱말 중간 (`조정자기자본비율`, `영업용순자본비율`의 `순자본비율`)
        before = text[max(0, match.start() - 60):match.start()]
        stripped = before.rstrip()
        if stripped.endswith(":"):
            # 구조화 행 `구 분: 총자본비율(A/B) | …` — 키가 표의 첫 열 머리일 때만 (셀 값 `지표명: …` 제외)
            key = re.search(r"([^|:\n]{1,40}):$", stripped)
            # 줄바꿈 없이 이어진 청크에서는 앞 행의 마지막 값(`241,639 구 분:`)이 붙어 온다
            key_text = re.sub(r"^\s*[\d,.%△\-]+\s+", "", key.group(1)) if key else ""
            headers = list(HEADER_KEY_RE.finditer(text, max(0, match.start() - 3000), match.start()))
            # (머리 마지막 열 `제25기 구 분:`처럼 앞말이 붙을 수 있어 끝부분으로 비교)
            if key and headers and not re.sub(r"\s+", "", key_text).endswith(re.sub(r"\s+", "", headers[-1].group(1))):
                continue
        elif stripped:
            # 앞 낱말이 한글로 끝나면 다른 말에 붙은 이름(`기본자본 지급여력비율`)이라 버린다.
            # 평문 표 머리의 마지막 열(`… | 제37기 지급여력비율(A/B) | 176.7`)은 기간 이름이라 허용
            prev = stripped.split()[-1]
            if re.search(r"[가-힣]$", prev) and classify_label(prev) is None:
                continue
        row = text[match.start():match.end() - 1].strip()
        if spec.exclude_row_re and spec.exclude_row_re.search(row):
            continue
        yield match.start(), match.end() - 1, row


def parse_candidates(spec: RatioSpec, chunk_index: int, section: str, text: str, period_end: str, period_type: str,
                     prev_text: str = "", next_text: str = "") -> tuple[list[Candidate], list[str]]:
    rank = section_rank(section)
    skipped: list[str] = []
    if rank is None:
        return [], skipped
    if CORRECTION_RE.search(text):
        return [], [f"{chunk_index}: 정정 대조 청크"]
    found: list[Candidate] = []
    joined = prev_text + text
    offset = len(prev_text)
    for start, bar, row in _row_starts(spec, text):
        cells = _cells(text, bar)
        if not cells:
            continue
        first_label, first_value = cells[0]
        labels: list[str] = [lab for lab, _ in cells if lab]
        if first_label is None:
            header = _flat_header(joined, offset + start)
            labels = header[: len(cells)]
            first_label = header[0] if header else None
        parsed = classify_label(first_label) if first_label else None
        ok = False
        if parsed is not None:
            ok = is_current(parsed, period_end, period_type)
            if ok and parsed.term is not None:
                terms = [p.term for p in (classify_label(lab) for lab in labels) if p and p.term is not None]
                ok = parsed.term == max(terms, default=parsed.term)
        else:
            date = _title_date(joined, offset + start)
            ok = date == (int(period_end[:4]), int(period_end[5:7]))
            first_label = f"기준일 {date[0]}.{date[1]:02d}" if date else first_label
        if not ok:
            skipped.append(f"{chunk_index}: '{row}' 첫 열 '{first_label}'이 대상 기간 아님")
            continue
        value = parse_number(first_value)
        if value is None:
            continue
        tail = text[bar:bar + 500] + " " + next_text[:400]
        found.append(Candidate(chunk_index, section, rank, start, row, re.sub(r"\s+", " ", first_label or ""), value,
                               bool(PROVISIONAL_RE.search(tail))))
    return found, skipped


def _mentions(value: Decimal, text: str) -> bool:
    plain = format(value.normalize(), "f")
    forms = {plain, f"{value:,.2f}", f"{value:,.1f}", f"{value:.2f}", f"{value:.1f}"}
    return any(re.search(rf"(?<![\d.,]){re.escape(form)}(?![\d])", text) for form in forms)


def extract_ratio(column: str, chunks: list[tuple[int, str, str]], period_end: str, period_type: str) -> RatioResult:
    """chunks: (chunk_index, section, chunk_text) — 비율 키워드 청크와 그 앞뒤 청크. 값은 % 소수 2자리."""
    spec = SPECS[column]
    by_index = {index: text for index, _, text in chunks}
    candidates: list[Candidate] = []
    skipped: list[str] = []
    for index, section, text in chunks:
        if not any(k in text for k in spec.keywords):
            continue
        found, why = parse_candidates(spec, index, section, text, period_end, period_type,
                                      by_index.get(index - 1, ""), by_index.get(index + 1, ""))
        candidates.extend(found)
        skipped.extend(why)
    if not candidates:
        return RatioResult(None, {"reason": f"{spec.name} 표에서 대상 기간 열을 찾지 못함", "skipped": skipped[:20]}, "extract_failed")
    candidates.sort(key=lambda c: (c.rank, c.chunk_index, c.position))
    best = candidates[0]
    value = best.value.quantize(Decimal("0.01"))
    if not spec.low <= value <= spec.high:
        return RatioResult(None, {"reason": f"{spec.name} 범위({spec.low}~{spec.high})를 벗어남: {value}",
                                  "chunk_indexes": [best.chunk_index]}, "needs_review")
    others = [c for c in candidates[1:] if not (c.chunk_index == best.chunk_index and c.position == best.position)]
    corroborated = any(c.value == best.value for c in others) or any(
        _mentions(best.value, text) for index, _, text in chunks if index != best.chunk_index)
    return RatioResult(
        value,
        {
            "row": best.row,
            "column": best.label,
            "chunk_indexes": [best.chunk_index],
            "section": best.section,
            "provisional": best.provisional,
            "corroborated": corroborated,
            "alternatives": [f"#{c.chunk_index} {c.row} {c.label}={c.value}" for c in others if c.value != best.value][:10],
        },
    )
