"""수시공시 "항목 경로: 값" 목록 → 종류별 필드 (LLM 없이 규칙으로).

규칙은 configs/disclosure_events.yaml의 `fields`에 있다.

    fields:
      dividend:
        required: [dps_common, record_date]
        rules:
          dps_common: {path: '^3\\.1주당배당금\\(원\\)>보통주', type: int}

- path: 공백을 지운 경로에 re.search. 표 순서대로 처음 맞는 값을 쓴다.
- acode: XML 값 칸의 항목 코드 (있으면 path보다 먼저 본다).
- type: text | int | float | number(정수면 int, 아니면 float) | date | krw | unit
  · krw는 scale에 적은 unit 필드(예: "단위 : 백만원")를 곱해 원 단위 정수로 바꾼다.
  · 값이 "-"·빈칸이면 None (항목은 있지만 해당 없음).
- 정정공시면 정정일자·정정사유·원래 공시 제출일을 correction에 따로 담는다.

parse_status: ok (required 모두 있음) · partial (일부 없음 또는 형식 오류) · failed (원문 파싱 실패)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .events_parse import Pair


EMPTY_VALUES = {"", "-", "--", "—", "해당없음", "해당사항없음", "N/A"}
UNIT_SCALE = [  # 긴 것부터
    ("십억원", 10**9),
    ("백만원", 10**6),
    ("천만원", 10**7),
    ("억원", 10**8),
    ("조원", 10**12),
    ("천원", 10**3),
    ("원", 1),
]
DATE_RE = re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})")
NUMBER_RE = re.compile(r"^[△▲(-]?\s*[\d,]+(\.\d+)?\s*\)?$")
CORRECTION_RULES = {
    "date": re.compile(r"^정정일자$"),
    "original_title": re.compile(r"^1\.정정관련공시서류$"),
    "original_date": re.compile(r"^2\.정정관련공시서류제출일$"),
    "reason": re.compile(r"^3\.정정사유$"),
}


def compact(path: str) -> str:
    return re.sub(r"\s+", "", path)


def parse_unit(value: str) -> int | None:
    text = compact(value)
    for name, scale in UNIT_SCALE:
        if name in text:
            return scale
    return None


def parse_number(value: str) -> float | None:
    """'1,877,789' → 1877789, '△123'·'(123)'·'-123' → -123, '19.07' → 19.07. 숫자가 아니면 ValueError."""
    text = value.strip().replace(" ", "")
    if text in EMPTY_VALUES:
        return None
    if not NUMBER_RE.match(text):
        raise ValueError(f"숫자가 아닙니다: {value!r}")
    negative = text[0] in "△▲(-"
    digits = re.sub(r"[^\d.]", "", text)
    number = float(digits)
    return -number if negative else number


def parse_date(value: str) -> str | None:
    text = value.strip()
    if compact(text) in EMPTY_VALUES:
        return None
    match = DATE_RE.search(text)
    if not match:
        raise ValueError(f"날짜가 아닙니다: {value!r}")
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day).isoformat()


@dataclass(frozen=True)
class FieldRule:
    name: str
    type: str = "text"
    path: re.Pattern | None = None
    acode: tuple[str, ...] = ()
    scale: str | None = None

    @classmethod
    def from_config(cls, name: str, spec: dict) -> "FieldRule":
        field_type = spec.get("type", "text")
        if field_type not in {"text", "int", "float", "number", "date", "krw", "unit"}:
            raise ValueError(f"{name}: 알 수 없는 type {field_type}")
        if field_type == "krw" and not spec.get("scale"):
            raise ValueError(f"{name}: krw에는 scale(단위 필드 이름)이 필요합니다.")
        acode = spec.get("acode") or ()
        if isinstance(acode, str):
            acode = (acode,)
        if not spec.get("path") and not acode:
            raise ValueError(f"{name}: path나 acode가 필요합니다.")
        return cls(
            name=name,
            type=field_type,
            path=re.compile(spec["path"]) if spec.get("path") else None,
            acode=tuple(acode),
            scale=spec.get("scale"),
        )

    def find(self, pairs: list[Pair]) -> Pair | None:
        if self.acode:
            for pair in pairs:
                if pair.acode in self.acode:
                    return pair
        if self.path is not None:
            for pair in pairs:
                if self.path.search(compact(pair.path)):
                    return pair
        return None


@dataclass
class EventFieldRules:
    rules: dict[str, list[FieldRule]]  # event_type → 규칙 (unit·scale 순서 보장 위해 unit 먼저)
    required: dict[str, list[str]]  # 항목 "a|b"는 둘 중 하나

    @classmethod
    def from_config(cls, config: dict) -> "EventFieldRules":
        rules: dict[str, list[FieldRule]] = {}
        required: dict[str, list[str]] = {}
        for event_type, spec in (config.get("fields") or {}).items():
            parsed = [FieldRule.from_config(name, rule) for name, rule in spec.get("rules", {}).items()]
            names = {rule.name for rule in parsed}
            for rule in parsed:
                if rule.scale and rule.scale not in names:
                    raise ValueError(f"{event_type}.{rule.name}: scale 필드 {rule.scale}가 없습니다.")
            missing = [
                name for group in spec.get("required", []) for name in group.split("|") if name not in names
            ]
            if missing:
                raise ValueError(f"{event_type}: required에 규칙이 없는 필드가 있습니다: {missing}")
            rules[event_type] = sorted(parsed, key=lambda rule: rule.type != "unit")
            required[event_type] = list(spec.get("required", []))
        return cls(rules, required)


@dataclass
class ExtractResult:
    fields: dict
    parse_status: str  # ok | partial
    missing: list[str] = field(default_factory=list)  # required인데 못 찾았거나 값이 없는 필드
    errors: list[str] = field(default_factory=list)  # 형식 오류 (숫자·날짜로 못 바꿈)
    correction: dict = field(default_factory=dict)


def _convert(rule: FieldRule, raw: str, values: dict):
    if rule.type == "text":
        text = raw.strip()
        return None if compact(text) in EMPTY_VALUES else text
    if rule.type == "date":
        return parse_date(raw)
    if rule.type == "unit":
        if compact(raw) in EMPTY_VALUES:
            return None
        scale = parse_unit(raw)
        if scale is None:
            raise ValueError(f"단위를 알 수 없습니다: {raw!r}")
        return scale
    number = parse_number(raw)
    if number is None:
        return None
    if rule.type == "float":
        return number
    if rule.type == "number":  # 정수면 int, 소수면 float (주당 배당금 630.67원 등)
        return int(number) if number == int(number) else number
    if rule.type == "krw":
        scale = values.get(rule.scale)
        if scale is None:
            raise ValueError(f"단위({rule.scale})를 몰라 원 단위로 바꿀 수 없습니다: {raw!r}")
        return int(round(number * scale))
    if number != int(number):
        raise ValueError(f"정수가 아닙니다: {raw!r}")
    return int(number)


def extract_correction(pairs: list[Pair]) -> dict:
    result = {}
    for key, pattern in CORRECTION_RULES.items():
        for pair in pairs:
            if pattern.search(compact(pair.path)):
                value = pair.value.strip()
                if key in {"date", "original_date"}:
                    try:
                        value = parse_date(value)
                    except ValueError:
                        pass
                result[key] = value
                break
    return result


def extract_fields(event_type: str, pairs: list[Pair], rules: EventFieldRules) -> ExtractResult:
    values: dict = {}
    errors: list[str] = []
    for rule in rules.rules.get(event_type, []):
        pair = rule.find(pairs)
        if pair is None:
            continue
        try:
            values[rule.name] = _convert(rule, pair.value, values)
        except ValueError as exc:
            values[rule.name] = None
            errors.append(f"{rule.name}: {exc}")
    # required 항목 "a|b"는 둘 중 하나만 있으면 된다.
    missing = [
        group for group in rules.required.get(event_type, [])
        if all(values.get(name) is None for name in group.split("|"))
    ]
    status = "partial" if missing or errors else "ok"
    return ExtractResult(values, status, missing, errors, extract_correction(pairs))
