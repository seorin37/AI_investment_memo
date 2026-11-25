"""메모 저장 시 분석 (2026-11-11): 메모 글 → 추적 항목·확인 질문·메모 전체 범위 밖 여부. DB는 쓰지 않는다 (저장은 tracking.py).

- 문장 판정은 파이프라인과 같다: 규칙 판정(pipelines.tracking.judge.judge_memo) → 규칙이 넘긴 문장만 LLM 1회
  (pipelines.tracking.llm.judge_with_llm). 확인 질문·메모 단위 범위 밖은 pipelines.updates.response.memo_analysis_responses.
- 확인 질문 선택지마다 option_id를 붙인다: 선택지 내용(메모·메모 버전·문장·항목)을 서버 비밀 키로 서명한 값.
  질문을 저장할 칸이 없어서(마이그레이션 없음), 답변 API는 이 서명으로 선택지가 서버가 만든 것인지·지금 메모 버전의 것인지 확인한다.
- 첫 카드는 매일 실행 때 만든다 (2026-11-11 결정 B). next_update_at = 다음 매일 실행 시각 (configs/updates.yaml daily.run_at).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from functools import lru_cache
from typing import Callable
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
TRACKED = ("normal", "partial")
ITEM_TYPES = ("topic", "price_below", "price_above")


class AnalysisError(RuntimeError):
    """분석을 끝내지 못함 (code: llm_unavailable | llm_failed | parse_failed)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class AnalysisResult:
    items: list[dict] = field(default_factory=list)          # {sentence_index, type, description, keywords, price_threshold}
    confirmations: list[dict] = field(default_factory=list)  # {sentence_index, text, question, reason, options[]}
    out_of_scope: bool = False
    llm_calls: int = 0
    # 실험(2026-11-16): 한 번 답하면 끝나는 질문 {sentence_index, text, question, kind}. 추적 항목·요금제 한도와 따로 센다
    questions: list[dict] = field(default_factory=list)


@lru_cache(maxsize=1)
def _lexicon():
    from pipelines.tracking.lexicon import load_lexicon
    return load_lexicon()


def default_llm() -> Callable[[str], str] | None:
    """메모 분석용 LLM 호출 함수 (.env의 LLM_API_KEY). 키가 없으면 None — 규칙만으로 끝나지 않는 메모는 llm_unavailable."""
    try:
        from pipelines.tracking.openai_client import OpenAIClient
        client = OpenAIClient.from_env()
    except Exception:
        return None
    client.response_format = None                          # 메모 분석 프롬프트는 JSON 배열을 돌려준다 (evaluate_long와 같게)
    return client


def _secret() -> bytes:
    secret = os.getenv("MEMO_CONFIRM_SECRET") or os.getenv("AUTH_JWT_SECRET") or ""
    if len(secret.encode()) < 16:
        raise AnalysisError("no_secret", "확인 질문 서명 키(AUTH_JWT_SECRET)가 없습니다")
    return hashlib.sha256(b"memo-confirm:" + secret.encode()).digest()


def sign_option(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def read_option(option_id: str) -> dict | None:
    """서명이 맞으면 선택지 내용, 아니면 None."""
    if not isinstance(option_id, str) or "." not in option_id:
        return None
    try:
        body, sig = option_id.rsplit(".", 1)
        want = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, want):
            return None
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None


def next_update_at(now: datetime | None = None, run_at: str | None = None) -> datetime:
    """다음 매일 실행 시각 (한국 시간). run_at 기본은 설정 daily.run_at (없으면 06:30)."""
    if run_at is None:
        try:
            from pipelines.common.config import load_config
            run_at = str((load_config("configs/updates.yaml").get("daily") or {}).get("run_at") or "06:30")
        except Exception:
            run_at = "06:30"
    hh, mm = (int(x) for x in run_at.split(":"))
    now = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    at = datetime.combine(now.date(), time(hh, mm), SEOUL)
    return at if at > now else at + timedelta(days=1)


def analyze_memo(memo_id: int, revision_no: int, text: str, symbol: str, stock_name: str,
                 llm: Callable[[str], str] | None, price_rows: list[tuple]) -> AnalysisResult:
    """메모 글 → 항목·확인 질문·범위 밖. LLM이 필요한데 없거나 실패하면 AnalysisError (호출자가 메모 저장은 그대로 둔다)."""
    from pipelines.tracking.judge import PENDING, judge_memo
    from pipelines.tracking.llm import judge_with_llm
    from pipelines.updates.response import memo_analysis_responses

    judged = judge_memo(text, symbol, _lexicon())
    calls = 0
    if any(j.decision == PENDING for j in judged):
        if llm is None:
            raise AnalysisError("llm_unavailable", "LLM 키가 없어 규칙만으로 끝나지 않는 문장을 판정할 수 없습니다")
        try:
            judged = judge_with_llm(judged, symbol, stock_name, llm)
            calls = 1
        except Exception as exc:                             # 호출 실패·응답 형식 오류
            raise AnalysisError("llm_failed", f"{type(exc).__name__}: {str(exc)[:160]}") from exc
    items = []
    for j in judged:
        if j.decision not in TRACKED or j.merge_into:
            continue
        for it in j.items:
            if it.get("type") in ITEM_TYPES and (it.get("description") or "").strip():
                items.append({"sentence_index": j.sentence_index, "type": it["type"], "description": it["description"].strip(),
                              "keywords": list(it.get("keywords") or []), "price_threshold": it.get("price_threshold")})
    responses = memo_analysis_responses(str(memo_id), judged, len(items), price_rows)
    confirmations = []
    for r in responses:
        if r.type != "needs_confirmation":
            continue
        options = []
        for o in r.options:
            item = o.get("item") or {}
            option = {k: o.get(k) for k in ("basis", "status", "current") if k in o}
            option["item"] = {"type": item.get("type"), "description": item.get("description"),
                              "price_threshold": item.get("price_threshold")}
            try:
                option["option_id"] = sign_option({"m": memo_id, "r": revision_no, "s": r.sentence_index, "i": option["item"]})
            except AnalysisError:                            # 서명 키가 없으면 선택지는 보여 주되 답변은 받을 수 없다
                logging.getLogger(__name__).warning("확인 질문 서명 키가 없어 option_id 없이 돌려줍니다 (memo=%s)", memo_id)
                option["option_id"] = None
            options.append(option)
        confirmations.append({"sentence_index": r.sentence_index, "text": r.text, "question": r.question,
                              "reason": r.reason, "options": options})
    questions, seen_q = [], set()
    for j in judged:
        for a in (getattr(j, "asks", None) or []):
            key = " ".join(str(a.get("question") or "").split())
            if key and key in seen_q:                        # 2026-11-25: "살까 / 말까 / 고민중"처럼 쪼개진 문장이 같은 질문을 내면 하나만 (답·크레딧 한 번)
                continue
            seen_q.add(key)
            q = {"sentence_index": j.sentence_index, "text": j.cleaned_text or j.text, **a}
            alerts = getattr(j, "ask_alerts", None) or []
            if alerts:                                       # 2026-11-25: 답 카드의 "○○원 넘으면 알려드릴까요?" 제안용
                q["alert"] = {"type": alerts[0]["type"], "price_threshold": alerts[0]["price_threshold"]}
            questions.append(q)
    return AnalysisResult(items, confirmations, any(r.type == "out_of_scope" and r.scope == "memo" for r in responses), calls,
                          questions)
