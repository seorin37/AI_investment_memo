"""공시 청크의 의결권 현황·자본금 주석에서 BPS용 주식 수를 엄격히 추출한다 (WO-016).

인접 기간 값은 사용하지 않는다. 의결권 현황은 기준일이 대상 period_end와 같아야 하고,
의결권없는 주식수(B)의 비고가 자기주식·빈 값·'-'인 행만 자기주식으로 인정한다.
자본금 주석 fallback은 호출자가 명시적으로 허용한 종목·기간에만 사용한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .financials import ShareCounts


COUNT = r"(?:-|[\d,]+)"
SHARE_KIND = r"(?:보통주|우선주|종류주)"


@dataclass(frozen=True)
class ParsedShares:
    counts: ShareCounts | None
    source: dict

    @property
    def reason(self) -> str | None:
        return self.source.get("reason")


def _int(value: str) -> int | None:
    text = value.strip().replace(",", "")
    if text == "-":
        return 0
    return int(text) if text.isdigit() else None


def _date_tokens(period_end: str) -> set[str]:
    target = date.fromisoformat(period_end)
    return {
        f"{target.year}년{target.month:02d}월{target.day:02d}일",
        f"{target.year}.{target.month:02d}.{target.day:02d}",
        f"{target.year}-{target.month:02d}-{target.day:02d}",
    }


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _structured_rows(text: str, label: str) -> list[dict]:
    pattern = re.compile(
        rf"구\s*분:\s*{re.escape(label)}\s*\|\s*주식의\s*종류:\s*(?P<kind>{SHARE_KIND})\s*\|\s*"
        rf"주식수:\s*(?P<count>{COUNT})\s*\|\s*비고:\s*(?P<note>.*?)(?=\s+구\s*분:|$)",
        re.S,
    )
    return [{"kind": m.group("kind"), "count": m.group("count"), "note": m.group("note").strip()} for m in pattern.finditer(text)]


def _flat_rows(text: str, label: str) -> list[dict]:
    # KB금융의 평문 청크처럼 열 구분자가 없는 경우. 다음 종류 행 또는 다음 표 항목 직전까지만 비고로 잡는다.
    start = text.find(label)
    if start < 0:
        return []
    next_labels = [text.find(name, start + len(label)) for name in ("발행주식총수(A)", "의결권없는 주식수(B)", "정관에 의하여")]
    ends = [position for position in next_labels if position >= 0]
    block = text[start : min(ends) if ends else len(text)]
    pattern = re.compile(rf"(?P<kind>{SHARE_KIND})\s+(?P<count>{COUNT})(?:\s+(?P<note>자기주식|-))?")
    return [{"kind": m.group("kind"), "count": m.group("count"), "note": (m.group("note") or "").strip()} for m in pattern.finditer(block)]


def _rows(text: str, label: str) -> list[dict]:
    return _structured_rows(text, label) or _flat_rows(text, label)


def parse_voting_rights(text: str, period_end: str) -> ParsedShares:
    """의결권 현황 한 청크를 파싱한다. 기준일·A·B 조건 중 하나라도 불명확하면 사용하지 않는다."""
    compact = _compact(text)
    if not any(token in compact for token in _date_tokens(period_end)):
        return ParsedShares(None, {"reason": f"의결권 현황 기준일이 {period_end}와 일치하지 않음"})
    a_rows = _rows(text, "발행주식총수(A)")
    b_rows = _rows(text, "의결권없는 주식수(B)")
    if not a_rows or not b_rows:
        return ParsedShares(None, {"reason": "의결권 현황 A 또는 B 행을 찾지 못함"})
    invalid_notes = [row for row in b_rows if _compact(row["note"]) not in {"", "-", "자기주식"}]
    if invalid_notes:
        return ParsedShares(None, {"reason": "의결권없는 주식수(B)의 비고가 자기주식 근거가 아님", "invalid_b": invalid_notes})
    a_values = [_int(row["count"]) for row in a_rows]
    b_values = [_int(row["count"]) for row in b_rows]
    if None in a_values or None in b_values or not any(value for value in a_values):
        return ParsedShares(None, {"reason": "의결권 현황 A 또는 B 주식수가 숫자가 아님", "a_rows": a_rows, "b_rows": b_rows})
    issued, treasury = sum(a_values), sum(b_values)
    if issued - treasury <= 0:
        return ParsedShares(None, {"reason": f"의결권 현황 분모가 0 이하: 발행 {issued}, 자기 {treasury}", "a_rows": a_rows, "b_rows": b_rows})
    return ParsedShares(
        ShareCounts(issued, treasury, issued - treasury, "의결권 현황 표"),
        {"source": "voting_rights", "period_end": period_end, "a_rows": a_rows, "b_rows": b_rows},
    )


def _note_count(text: str, label: str, kind: str) -> int | None:
    match = re.search(rf"{re.escape(label)}\s*\|[^\n]*?{kind}:\s*({COUNT})", text)
    if not match or match.group(1).strip() == "-":
        return None
    return _int(match.group(1))


def parse_capital_note(text: str, period_end: str) -> ParsedShares:
    """연결재무제표 자본금 주석의 당기 발행·유통주식수. 이전 기간 표는 사용하지 않는다."""
    current = text
    if "당분기말" in current:
        current = current.split("당분기말", 1)[1].split("전기말", 1)[0]
    issued = [_note_count(current, label, kind) for kind in ("보통주", "우선주") for label in ("발행주식수(소각주식수 제외)(주)", "발행주식수(주)")]
    outstanding = [_note_count(current, label, kind) for kind in ("보통주", "우선주") for label in ("분기말 유통주식수(주)", "유통주식수(주)")]
    # 종류별로 두 라벨 중 먼저 찾은 하나만 쓴다.
    issued_by_kind = [next((value for value in issued[i : i + 2] if value is not None), None) for i in (0, 2)]
    outstanding_by_kind = [next((value for value in outstanding[i : i + 2] if value is not None), None) for i in (0, 2)]
    if any(value is None for value in issued_by_kind + outstanding_by_kind):
        return ParsedShares(None, {"reason": "자본금 주석의 당기 발행·유통주식수를 모두 찾지 못함"})
    total_issued, total_outstanding = sum(issued_by_kind), sum(outstanding_by_kind)
    treasury = total_issued - total_outstanding
    if treasury < 0 or total_outstanding <= 0:
        return ParsedShares(None, {"reason": f"자본금 주석 주식수 관계 불일치: 발행 {total_issued}, 유통 {total_outstanding}"})
    return ParsedShares(
        ShareCounts(total_issued, treasury, total_outstanding, "연결 자본금 주석"),
        {"source": "capital_note", "period_end": period_end, "issued_rows": issued_by_kind, "outstanding_rows": outstanding_by_kind},
    )


def parse_capital_issued(text: str, period_end: str) -> int | None:
    """교차 검증용 당기 발행주식수. 유통주식수가 없어도 발행주식수만 안전하게 읽는다."""
    full = parse_capital_note(text, period_end)
    if full.counts is not None:
        return full.counts.issued
    current = text
    for marker in ("[표] 주식에 대한 공시 당분기말", "주식의 분류에 대한 공시 / 당분기말", "14-A. 자본 주식의 분류에 대한 공시 당반기말",
                   "14-A. 자본 주식의 분류에 대한 공시 당분기말"):
        if marker in current:
            current = current.split(marker, 1)[1]
            break
    current = current.split("전기말", 1)[0]
    pair = re.search(
        r"(?:소각주식\s*수를\s*제외한\s*발행주식수|발행주식수\(소각주식수\s*제외\))[^|]*\|\s*"
        rf"보통주:\s*({COUNT})\s*\|\s*우선주:\s*({COUNT})",
        current,
    )
    if pair:
        values = [value for value in (_int(pair.group(1)), _int(pair.group(2))) if value is not None]
        return sum(values) if len(values) == 2 else None
    sk = re.search(rf"보통주\s*발행주식수[^|]*\|\s*보통주:\s*({COUNT})", current)
    if sk:
        return _int(sk.group(1))
    kb = re.search(r"보통주\s+발행할\s*주식의\s*총수\s+[\d,]+.*?\b발행주식수\s+([\d,]+)", current, re.S)
    return _int(kb.group(1)) if kb else None
