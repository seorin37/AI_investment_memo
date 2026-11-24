"""LLM 답의 형식 (OpenAI 구조화 출력, strict)과 답을 받은 뒤의 검사."""
from __future__ import annotations

import re

LEAF_FIELDS = ("t", "why", "note", "check", "check_why")
LAB_SCHEMA = {
    "name": "lab_paths",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["paths"],
        "properties": {
            "paths": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["var", "dir", "leaves"],
                    "properties": {
                        "var": {"type": "string"},
                        "dir": {"type": "string", "enum": ["상승", "하락"]},
                        "leaves": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": list(LEAF_FIELDS),
                                "properties": {name: {"type": "string"} for name in LEAF_FIELDS},
                            },
                        },
                    },
                },
            },
        },
    },
}

# 프롬프트의 글자 수보다 조금 넉넉하게 검사한다.
LIMITS = {"t": (2, 20), "why": (10, 100), "note": (5, 60), "check": (2, 30), "check_why": (2, 30)}
BANNED = [
    (re.compile(r"매수|매도|사세요|파세요|사야|팔아야|추천"), "매수·매도 권유나 추천 표현"),
    (re.compile(r"목표\s*주가|전망"), "목표주가·전망 표현"),
    (re.compile(r"호재|악재|수혜"), "호재·악재·수혜 표현"),
    (re.compile(r"급등|급락|폭등|폭락"), "급등·급락 표현"),
    (re.compile(r"장중"), "'장중' 표현"),
    (re.compile(r"(?<!불)확실|반드시|무조건"), "단정 표현"),
    (re.compile(r"주가[^.。]{0,12}(오르|올라|오를|상승|내리|내릴|떨어|하락)"), "주가 방향 예측"),
]
NUMBER = re.compile(r"\d[\d,]*(\.\d+)?\s*(%|퍼센트|배|원|억|조|bp|달러)")
RATE_VARS = {"한국 기준금리", "미국 10년물 국채금리"}
# 금리와 채권 가격은 반대로 움직인다.
BOND_WRONG = {
    "하락": re.compile(r"채권[^.]{0,20}손실"),
    "상승": re.compile(r"채권[^.]{0,20}평가\s*(이익|차익)"),
}


def check(answer: dict, changed: list[tuple[str, str]], facts: list[str]) -> list[str]:
    """문제 목록을 돌려준다. 빈 목록이면 통과."""
    paths = answer.get("paths")
    if not isinstance(paths, list):
        return ["paths가 목록이 아니에요"]
    errors: list[str] = []
    if len(paths) != len(changed):
        errors.append(f"바꾼 가정은 {len(changed)}개인데 경로가 {len(paths)}개예요")
    texts: list[str] = []
    for index, (path, (var, direction)) in enumerate(zip(paths, changed), 1):
        tag = f"{index}번 경로"
        if path.get("var") != var or path.get("dir") != direction:
            errors.append(f"{tag}: var/dir가 입력({var}/{direction})과 달라요")
        leaves = path.get("leaves")
        if not isinstance(leaves, list) or not 1 <= len(leaves) <= 2:
            errors.append(f"{tag}: leaves는 1~2개여야 해요")
            continue
        for leaf in leaves:
            if var in RATE_VARS and BOND_WRONG[direction].search(f"{leaf.get('t', '')} {leaf.get('why', '')}"):
                errors.append(f"{tag}: 금리 {direction}과 채권 평가 방향이 반대예요")
            for name, (low, high) in LIMITS.items():
                value = str(leaf.get(name, "")).strip()
                texts.append(value)
                if not low <= len(value) <= high:
                    errors.append(f"{tag}: {name}은 {low}~{high}자여야 해요 (지금 {len(value)}자)")
    text = " ".join(texts)
    for pattern, label in BANNED:
        match = pattern.search(text)
        if match:
            errors.append(f"쓰면 안 되는 말이 있어요: {label} ('{match.group(0)}')")
    allowed = " ".join(facts)
    for match in NUMBER.finditer(text):
        if match.group(0) not in allowed:
            errors.append(f"입력에 없는 숫자를 썼어요: '{match.group(0)}'")
    return errors
