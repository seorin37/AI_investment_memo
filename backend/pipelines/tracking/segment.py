"""문장 분리: 줄바꿈, 문장부호(. ? !) 뒤 공백, 그리고 문장부호 없이 이어 쓴 메모의 문장 끝 표현에서 자른다.

사람들은 메모를 줄바꿈·마침표 없이 한 줄로 이어 쓴다("왜 안 오르냐 요즘 상황 안좋아 7만 깨지면 손절함").
그래서 어절이 "~냐/~함/~자/~다/~요" 같은 문장 끝 표현으로 끝나면 그 뒤에서도 자른다.
명사·연결 표현이 같은 글자로 끝나는 경우("수요", "투자", "다음", "~니까", "~는지", "지금보다")는 자르지 않는다.
원문 위치(span)를 보존한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    index: int
    text: str
    span: tuple[int, int]


# 어절이 . ? ! 로 끝나면 경계. "3.5%"·"0.5배"처럼 숫자 사이 마침표는 어절 끝이 아니라 자르지 않는다.
# 문장 끝 표현 (어절 끝). 한 글자 어절("다", "싸")은 보지 않는다.
_FINAL = re.compile(r"(냐|니|죠|네요|네|군|듯|음|함|됨|봄|옴|짐|자|다|요|좋아|싫어|몰라|같아|어때|봐|줘|까)$")
# 한 글자지만 문장을 끝내는 어절 ("봐야 함", "안 함", "늘 듯", "볼 것")
_FINAL_SINGLE = frozenset({"함", "됨", "임", "듯", "것", "씀"})
# 명사로 끝나는 메모 문장 ("둘 다 체크", "추가 매수 고민", "통과 여부")
_FINAL_NOUNS = frozenset({
    "체크", "고민", "여부", "확인", "보기", "예정", "주목", "걱정", "검토", "관찰", "계획",
    "리스크", "관건", "핵심", "원칙", "가능성", "최악",  # "결과"는 "결과 나오면"처럼 이어져서 뺀다
})
# 같은 글자로 끝나지만 문장이 이어지는 연결 표현
_NOT_FINAL_SUFFIX = re.compile(r"(니까|보다|마다|에다|[는은ㄴ인던할을갈뭔건런]지|아까)$")
# 같은 글자로 끝나는 흔한 명사
_NOT_FINAL_WORDS = frozenset({
    "다음", "처음", "마음", "얼음", "소음", "포함", "수요", "필요", "중요", "주요", "투자", "이자", "적자",
    "흑자", "부자", "여자", "남자", "혼자", "숫자", "글자", "판자", "사자", "의자",
})
_TRAILING = ".,!?~…ㅋㅎㅠㅜ^"


def _is_final(word: str, alias_pattern=None) -> bool:
    core = word.rstrip(_TRAILING)
    if core in _FINAL_SINGLE or core in _FINAL_NOUNS:
        return True
    if len(core) < 2 or core in _NOT_FINAL_WORDS or _NOT_FINAL_SUFFIX.search(core):
        return False
    if alias_pattern is not None:
        hit = alias_pattern.search(core)
        if hit and hit.end() == len(core):  # "삼성전자"·"6만전자"는 "자"로 끝나도 문장 끝이 아니다
            return False
    return bool(_FINAL.search(core))


_JAMO_ONLY = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ.,!?~…^]+$")
_LAUGH = re.compile(r"^[ㅋㅎㅠㅜㅇ.,!?~…^]+$")  # 문장 끝 신호로 쓰는 웃음·울음·ㅇㅇ (ㅅㅂ 같은 욕설 자음은 제외)


def _is_filler(text: str, filler_words, profanity_stems=()) -> bool:
    """ㅋㅋ·ㅠㅠ·ㅇㅇ 같은 기호, '진짜' 같은 군더더기 말, 욕설로만 된 조각 (앞 문장에 붙인다)."""
    words = text.split()
    return all(w.strip(_TRAILING) in filler_words or not w.strip(_TRAILING) or _JAMO_ONLY.match(w)
               or (profanity_stems and w.lstrip("개").startswith(profanity_stems)) for w in words)


def _split_flat(line: str, alias_pattern=None, filler_words=frozenset(), profanity_stems=()) -> list[tuple[int, int]]:
    """한 줄을 (시작, 끝) 구간들로 자른다: 문장부호 뒤 공백, 그리고 문장 끝 표현 어절 뒤.
    같은 줄에서 앞 문장 뒤에 붙은 군더더기 조각("손절함 ㅋㅋㅋ", "개빡치네 진짜")은 앞 문장에 붙인다."""
    words = [m.span() for m in re.finditer(r"\S+", line)]
    spans, start = [], None
    for i, (ws, we) in enumerate(words):
        if start is None:
            start = ws
        last = i == len(words) - 1
        # 문장 중간의 ㅋㅋ·ㅠㅠ·ㅇㅇ는 문장이 끝났다는 신호 ("왜 계속 팔아 ㅋㅋ 요즘 수급…")
        jamo_break = i > 0 and _LAUGH.match(line[ws:we]) is not None
        if last or line[we - 1] in ".?!" or jamo_break or _is_final(line[ws:we], alias_pattern):
            spans.append((start, we))
            start = None
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and _is_filler(line[s:e], filler_words, profanity_stems):
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    # 맨 앞 조각이 군더더기·욕설뿐이면 뒤 문장에 붙인다 ("아 ㅅㅂ 오늘 -8% 실화냐")
    if len(merged) > 1 and _is_filler(line[merged[0][0]:merged[0][1]], filler_words, profanity_stems):
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)
    return merged


def split_sentences(text: str, lex=None) -> list[Segment]:
    """lex(판정 사전)를 주면 종목명 어절에서 자르지 않고, 군더더기 말 목록을 쓴다."""
    alias_pattern = lex.alias_pattern if lex is not None else None
    filler_words = lex.filler_words if lex is not None else frozenset()
    profanity_stems = lex.profanity_stems if lex is not None else ()
    segments: list[Segment] = []
    line_start = 0
    for line in text.split("\n"):
        for s, e in _split_flat(line, alias_pattern, filler_words, profanity_stems):
            start = line_start + s
            segments.append(Segment(len(segments), line[s:e], (start, line_start + e)))
        line_start += len(line) + 1
    return segments
