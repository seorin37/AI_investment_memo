"""정제: 판정용 사본에서 욕설·호칭을 지우고 개인정보를 가린다. 원문은 바꾸지 않는다."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .lexicon import Lexicon


@dataclass(frozen=True)
class Cleaned:
    text: str
    flags: tuple[str, ...]


_PII = [
    (re.compile(r"01[016789][-. ]?\d{3,4}[-. ]?\d{4}"), "[전화번호]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[이메일]"),
    (re.compile(r"\d{6}-[1-4]\d{6}"), "[주민번호]"),
]
_SYMBOLS_ONLY = re.compile(r"^[\sㅋㅎㅠㅜㄷㄱ.,!?~^…·\-]*$")


def clean(text: str, lex: Lexicon) -> Cleaned:
    flags: list[str] = []
    masked = text
    for pattern, token in _PII:
        masked, count = pattern.subn(token, masked)
        if count and "pii_masked" not in flags:
            flags.append("pii_masked")
    kept: list[str] = []
    for word in masked.split():
        if lex.is_profanity(word):
            if "profanity" not in flags:
                flags.append("profanity")
            continue
        if word.lower().rstrip(",!?.~") in lex.vocatives:
            if "vocative" not in flags:
                flags.append("vocative")
            continue
        kept.append(word)
    return Cleaned(" ".join(kept), tuple(flags))


def is_meaningless(cleaned_text: str, lex: Lexicon) -> bool:
    """정제 후 군더더기 말(진짜·ㄹㅇ 등)과 기호(ㅋ·ㅠ·.)만 남았으면 True."""
    words = [w.strip(".,!?~") for w in cleaned_text.split()]
    content = [w for w in words if w and w not in lex.filler_words and not _SYMBOLS_ONLY.match(w)]
    return not content


def strip_filler(text: str, lex: Lexicon) -> str:
    """끝에 붙은 ㅋㅋ·ㅠㅠ·진짜 같은 군더더기 어절을 뗀다 (카드에 보일 메모 원문 정리용)."""
    words = text.split()
    while words and is_meaningless(words[-1], lex):
        words.pop()
    return " ".join(words)
