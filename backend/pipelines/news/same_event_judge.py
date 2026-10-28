"""애매한 묶음의 같은 사건 여부를 LLM(Gemini)에 묻는다. clustering.choose_cluster의 judge로 쓴다.

API 키는 환경변수 `GEMINI_API_KEY`에서만 읽는다 (저장소 루트 .env 또는 수집기 컨테이너 환경변수).
키는 프로그램 안에서만 쓰고 출력·저장하지 않는다. 모델은 `GEMINI_MODEL`(기본 gemini-3.1-flash-lite).
외부 API를 부르므로 배정 명령에 --llm을 붙였을 때만 쓴다.

판정 기준은 "같은 사건(엄격)": 누가·무엇을·언제가 모두 같아야 같은 사건이다.
답을 못 받으면(오류·한도 초과·형식 불량) None을 돌려주고, 배정은 합류하지 않는 쪽으로 간다.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .clustering import KST, Member, cosine_similarity

log = logging.getLogger("same_event_judge")

DEFAULT_MODEL = "gemini-3.1-flash-lite"
MAX_MEMBERS_IN_PROMPT = 5     # 묶음이 커도 이만큼만 보여 준다 (새 기사와 덜 비슷한 기사부터)
SUMMARY_CHARS = 200

PROMPT = """너는 뉴스 중복 묶음 검사기다. [새 기사]가 [묶음 기사들]과 '같은 사건'을 다룬 기사인지 판단하라.

같은 사건 = 누가·무엇을·언제가 모두 같은 하나의 일. 매체나 표현, 속보/종합 여부만 다르면 같은 사건이다.
다른 사건으로 보는 경우:
- 같은 주제라도 다른 일: 결정 전 전망 vs 실제 결정, 사건 발생 vs 후속 조치·반응·분석
- 같은 일에 대한 다른 주체(기관·국가·인물)의 반응이나 대응
- 다른 회사, 다른 지역, 다른 금액·수치의 일
- 같은 틀의 반복 기사(시황, 날씨 특보 등)라도 시점·대상이 다르면 다른 사건
묶음 기사 중 하나라도 새 기사와 다른 사건이면 false다. 확실하지 않으면 false로 답하라.

[새 기사]
{new}

[묶음 기사들]
{members}

JSON으로만 답하라: {{"same": true 또는 false, "reason": "한 문장"}}"""


def _article(m: Member) -> str:
    when = m.published_at.astimezone(KST).strftime("%m-%d %H:%M")
    summary = (m.summary or "").strip().replace("\n", " ")[:SUMMARY_CHARS]
    return f"- ({when}) {m.title}" + (f"\n  요약: {summary}" if summary else "")


def build_prompt(new: Member, members: Sequence[Member], similarity: Callable[[Member], float] | None = None) -> str:
    """members가 많으면 새 기사와 덜 비슷한 기사부터 MAX_MEMBERS_IN_PROMPT건 (complete-link가 깨지는 쪽을 본다)."""
    shown = sorted(members, key=similarity)[:MAX_MEMBERS_IN_PROMPT] if similarity else list(members)[:MAX_MEMBERS_IN_PROMPT]
    shown.sort(key=lambda m: (m.published_at, m.news_id))
    return PROMPT.format(new=_article(new), members="\n".join(_article(m) for m in shown))


def parse_verdict(text: str) -> tuple[bool | None, str]:
    """LLM 답 → (같은 사건 여부, 이유). 형식이 틀리면 (None, 원문 일부)."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, raw[:100]
    if not isinstance(data, dict) or not isinstance(data.get("same"), bool):
        return None, raw[:100]
    return data["same"], str(data.get("reason", ""))[:200]


@dataclass
class JudgeStats:
    calls: int = 0
    same: int = 0
    different: int = 0
    unavailable: int = 0
    skipped_budget: int = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class SameEventJudge:
    """call(prompt) → 답 문자열. max_calls를 넘으면 더 묻지 않고 None (하루 비용·한도 보호)."""
    call: Callable[[str], str] = field(repr=False)
    max_calls: int = 300
    stats: JudgeStats = field(default_factory=JudgeStats)

    def __call__(self, new: Member, members: Sequence[Member]) -> bool | None:
        if self.stats.calls >= self.max_calls:
            self.stats.skipped_budget += 1
            return None
        self.stats.calls += 1
        try:
            text = self.call(build_prompt(new, members, lambda m: cosine_similarity(new.dense, m.dense)))
        except Exception as exc:   # 오류 내용에 키는 없지만 길게 남기지 않는다
            log.warning("LLM 판정 실패 news_id=%s: %s", new.news_id, str(exc)[:120])
            self.stats.unavailable += 1
            return None
        verdict, reason = parse_verdict(text)
        if verdict is None:
            log.warning("LLM 답 형식 오류 news_id=%s: %s", new.news_id, reason)
            self.stats.unavailable += 1
        elif verdict:
            self.stats.same += 1
        else:
            self.stats.different += 1
        log.debug("LLM 판정 news_id=%s same=%s (%s)", new.news_id, verdict, reason)
        return verdict


def gemini_from_env(model: str | None = None) -> Callable[[str], str]:
    """GEMINI_API_KEY로 Gemini 호출기를 만든다 (호출 방식은 tracking.gemini와 같음: REST, JSON 응답, temperature 0)."""
    from ..common.db import load_env
    from ..tracking.gemini import GeminiClient

    load_env()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 없습니다. .env 또는 컨테이너 환경변수에 넣어 주세요.")
    return GeminiClient(api_key=key, model=model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL)


def judge_from_env(max_calls: int = 300, model: str | None = None) -> SameEventJudge:
    return SameEventJudge(gemini_from_env(model), max_calls=max_calls)
