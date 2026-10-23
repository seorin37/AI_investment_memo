"""KB금융 BIS 총자본비율 추출 → financials_fin.solvency_ratio (WO-015 ③단계).

공시 청크(disclosure_chunks, 읽기 전용)의 "BIS기준 자기자본비율" 표에서 대상 기간 말(당기) 총자본비율을 찾는다.
- 지주 기준만 쓴다: 표 앞의 가장 가까운 주체 표시가 `[지배회사에 관한 사항]`·`[KB금융지주]`인 표.
  `[KB국민은행]`·`[주요 종속회사에 관한 사항]` 등 종속회사 표는 쓰지 않는다.
- 열 머리(예: `2024년 1분기`, `2025년 반기말`, `2025년`)가 대상 기간과 맞는 열만 쓴다 (전기·비교 열 배제).
- 정정 공시의 `정정 전`·`정정 후` 대조 청크는 쓰지 않는다.
- 찾지 못하거나 후보 값이 둘 이상이면 None + 사유 (추정 금지).

청크 표 형식은 두 가지다.
  구조화: `열: 구분 | 2025년 | 2024년` / `구분: 총자본비율(a/f) | 2025년: 16.20 | 2024년: 16.43`
  평문:   `구분 2024년 1분기 2023년 2022년 자기자본(a=b+e) … 총자본비율(a/f) 16.54 16.73 16.16`
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal


ENTITY_RE = re.compile(r"\[(지배회사에 관한 사항|주요 종속회사에 관한 사항|종속회사에 관한 사항|KB[^\]\n]{1,20})\]")
HOLDING_ENTITIES = {"지배회사에 관한 사항", "KB금융지주"}
CORRECTION_RE = re.compile(r"정정\s*[전후]")
PERIOD_LABEL_RE = re.compile(r"\d{4}\s*년(?:\s*(?:[1-4]\s*분기|상반기|반기))?(?:\s*말)?")
STRUCTURED_ROW_RE = re.compile(r"총자본비율\s*\([^)\n]*\)\s*\|([^\n]+)")
FLAT_ROW_RE = re.compile(r"총자본비율\s*\([^)\n]*\)((?:\s+-?\d+(?:\.\d+)?)+)")
FLAT_HEADER_RE = re.compile(r"구\s*분\s+((?:\d{4}\s*년[^\d가-힣]*(?:[1-4]\s*분기|상반기|반기)?\s*(?:말)?\s*)+)")
BIS_TITLE_RE = re.compile(r"BIS\s*기\s*준")
PROVISIONAL_RE = re.compile(r"잠\s*정")
TABLE_END_RE = re.compile(r"\(2\)|\[(?:지배회사에 관한 사항|주요 종속회사에 관한 사항|종속회사에 관한 사항|KB[^\]\n]{1,20})\]")


def _compact(label: str) -> str:
    return re.sub(r"\s+", "", label)


def target_labels(period_end: str) -> set[str]:
    """대상 기간 말 열 머리 후보 (공백 제거 형태)."""
    year, month = period_end[:4], period_end[5:7]
    stems = {"03": ["1분기"], "06": ["반기", "상반기", "2분기"], "09": ["3분기"], "12": [""]}[month]
    return {f"{year}년{stem}{suffix}" for stem in stems for suffix in ("", "말")}


@dataclass
class Candidate:
    chunk_index: int
    section: str
    entity: str | None
    labels: list[str]
    values: list[Decimal]
    provisional: bool


@dataclass
class BisResult:
    value: Decimal | None
    source: dict = field(default_factory=dict)

    @property
    def reason(self) -> str | None:
        return self.source.get("reason")


def _entity_before(text: str, position: int) -> str | None:
    entity = None
    for match in ENTITY_RE.finditer(text, 0, position):
        entity = match.group(1).strip()
    return entity


def parse_candidates(chunk_index: int, section: str, text: str) -> list[Candidate]:
    """청크 하나에서 BIS 총자본비율 행을 (열 머리, 값) 목록으로 뽑는다. 주체는 행 앞의 가장 가까운 표시."""
    found: list[Candidate] = []
    for match in STRUCTURED_ROW_RE.finditer(text):
        pairs = [cell.split(":", 1) for cell in match.group(1).split("|") if ":" in cell]
        labels = [_compact(label) for label, _ in pairs]
        try:
            values = [Decimal(value.strip()) for _, value in pairs]
        except ArithmeticError:
            continue
        found.append(_candidate(chunk_index, section, text, match.start(), labels, values))
    for match in FLAT_ROW_RE.finditer(text):
        # 열 머리는 같은 표(행 앞 가장 가까운 BIS 표 제목 이후)에서만 찾는다 — 앞선 다른 표의 머리와 짝짓지 않는다
        titles = list(BIS_TITLE_RE.finditer(text, 0, match.start()))
        if not titles:
            continue
        headers = list(FLAT_HEADER_RE.finditer(text, titles[-1].end(), match.start()))
        if not headers:
            continue
        labels = [_compact(label) for label in PERIOD_LABEL_RE.findall(headers[-1].group(1))]
        values = [Decimal(v) for v in match.group(1).split()]
        if len(labels) != len(values):
            continue
        found.append(_candidate(chunk_index, section, text, match.start(), labels, values))
    return found


def _candidate(chunk_index: int, section: str, text: str, position: int, labels: list[str], values: list[Decimal]) -> Candidate:
    entity = _entity_before(text, position)
    start = max((m.start() for m in ENTITY_RE.finditer(text, 0, position)), default=0)
    window = text[start:position]
    titles = list(BIS_TITLE_RE.finditer(window))
    # 잠정 표시는 이 표의 범위(BIS 표 제목 ~ 다음 하위 항목 `(2)`·다음 주체 표시 전, 최대 300자)에서만 찾는다
    stop = min([m.start() for m in TABLE_END_RE.finditer(text, position + 1)] + [len(text), position + 300])
    table_text = (window[titles[-1].start():] if titles else "") + text[position:stop]
    return Candidate(
        chunk_index=chunk_index,
        section=section,
        entity=entity if titles else None,
        labels=labels,
        values=values,
        provisional=bool(PROVISIONAL_RE.search(table_text)),
    )


def extract_total_capital_ratio(chunks: list[tuple[int, str, str]], period_end: str) -> BisResult:
    """chunks: (chunk_index, section, chunk_text). 지주 기준 대상 기간 말 총자본비율 % (소수 2자리)."""
    wanted = target_labels(period_end)
    picked: list[tuple[Candidate, Decimal, str]] = []
    skipped: list[str] = []
    for chunk_index, section, text in chunks:
        if CORRECTION_RE.search(text):
            skipped.append(f"{chunk_index}: 정정 대조 청크")
            continue
        for candidate in parse_candidates(chunk_index, section, text):
            if candidate.entity not in HOLDING_ENTITIES:
                skipped.append(f"{chunk_index}: 지주 표 아님 (주체 {candidate.entity})")
                continue
            columns = [(label, value) for label, value in zip(candidate.labels, candidate.values) if label in wanted]
            if not columns:
                skipped.append(f"{chunk_index}: 대상 기간 열 없음 (열 {candidate.labels})")
                continue
            for label, value in columns:
                picked.append((candidate, value, label))
    values = {value for _, value, _ in picked}
    if not picked:
        return BisResult(None, {"reason": "지주 기준 BIS 총자본비율 표에서 대상 기간 열을 찾지 못함", "skipped": skipped[:20]})
    if len(values) > 1:
        detail = [f"청크 {c.chunk_index} {label}={value}" for c, value, label in picked]
        return BisResult(None, {"reason": f"후보 값이 여러 개로 모호함: {detail}", "skipped": skipped[:20]})
    value = values.pop().quantize(Decimal("0.01"))
    if not Decimal(0) < value < Decimal(100):
        return BisResult(None, {"reason": f"비율 범위를 벗어남: {value}"})
    first, _, label = picked[0]
    return BisResult(
        value,
        {
            "basis": "지주 기준 (KB금융지주)",
            "entity_marker": first.entity,
            "column": label,
            "chunk_indexes": sorted({c.chunk_index for c, _, _ in picked}),
            "section": first.section,
            "provisional": any(c.provisional for c, _, _ in picked),
            "excluded": skipped[:20],
        },
    )
