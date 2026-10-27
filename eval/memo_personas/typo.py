"""오타 후처리 — 생성 단계에서는 오타를 넣지 않고, 검사를 통과한 메모에 페르소나 오타율만큼 일부 넣는다.

- 오타율(w_typo_rate)은 '어절마다 오타가 생길 확률'로 쓴다 (0이면 그대로).
- 기업명·별명·다른 종목명, 숫자·영문이 든 어절(가격·날짜·HBM4 등)은 건드리지 않는다.
- 원문은 memo_text_raw에 그대로 남는다. 같은 메모 ID면 항상 같은 오타가 나온다.
"""

from __future__ import annotations

import random
import re

from .common import ALIASES, OTHER_STOCKS

_PROTECTED = sorted({a.lower() for al in ALIASES.values() for a in al} | {s.lower() for s in OTHER_STOCKS}, key=len,
                    reverse=True)
_HANGUL = re.compile(r"^[가-힣]+[.,!?~ㅋㅎㅠㅜ]*$")
JONG_SS, JONG_S = 20, 19  # ㅆ, ㅅ 받침


def _split(ch: str):
    code = ord(ch) - 0xAC00
    return code // 588, (code % 588) // 28, code % 28


def _join(cho: int, jung: int, jong: int) -> str:
    return chr(0xAC00 + cho * 588 + jung * 28 + jong)


def _mutations(word: str) -> list[str]:
    core = re.match(r"[가-힣]+", word).group(0)
    tail = word[len(core):]
    out = []
    for i, ch in enumerate(core):
        cho, jung, jong = _split(ch)
        if jong == JONG_SS:  # 했 → 햇
            out.append(core[:i] + _join(cho, jung, JONG_S) + core[i + 1:])
        elif jong and i == len(core) - 1 and len(core) >= 2:  # 끝 받침 빠뜨림: 확인 → 확이
            out.append(core[:i] + _join(cho, jung, 0) + core[i + 1:])
    if len(core) >= 3:
        i = len(core) // 2
        out.append(core[:i - 1] + core[i] + core[i - 1] + core[i + 1:])  # 가운데 두 글자 자리 바뀜
    if "되" in core:
        out.append(core.replace("되", "돼", 1))
    elif "돼" in core:
        out.append(core.replace("돼", "되", 1))
    if len(core) >= 2:
        out.append(core[:1] + core[0] + core[1:])  # 글자 겹침: 체크 → 체체크
    return [m + tail for m in dict.fromkeys(out) if m != core]


def eligible(word: str) -> bool:
    w = word.lower()
    return bool(_HANGUL.match(word)) and len(re.match(r"[가-힣]+", word).group(0)) >= 2 \
        and not any(p in w for p in _PROTECTED)


def inject(text: str, rate: float, key: str) -> str:
    if not rate:
        return text
    rng = random.Random(f"typo:{key}")
    parts = text.split(" ")
    for i, w in enumerate(parts):
        if eligible(w) and rng.random() < rate:
            cands = _mutations(w)
            if cands:
                parts[i] = rng.choice(cands)
    return " ".join(parts)
