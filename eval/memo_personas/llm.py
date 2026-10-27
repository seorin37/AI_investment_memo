"""Gemini 호출기 (메모 생성용) + 맥북 점검용 목업.

backend/pipelines/tracking/gemini.py와 같은 방식(REST + x-goog-api-key 헤더)으로 부르되,
메모 생성에 필요한 것만 더했다: JSON 스키마 강제, 429를 '분당 한도'와 '일일 한도'로 구분,
usage_metadata의 thinking 토큰 기록. API 키는 헤더로만 보내고 화면·파일에 남기지 않는다.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 응답 스키마 (Gemini responseSchema, OpenAPI 부분집합)
MEMO_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "memos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"slot": {"type": "INTEGER"}, "memo_text": {"type": "STRING"}},
                "required": ["slot", "memo_text"],
            },
        }
    },
    "required": ["memos"],
}
PING_SCHEMA = {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}, "required": ["ok"]}


class LLMError(RuntimeError):
    """사람이 읽을 안내(guide)를 함께 가진 오류."""

    def __init__(self, message: str, guide: str = ""):
        super().__init__(message)
        self.guide = guide


class RateLimited(LLMError):
    """분당 한도(429) 또는 일시적 서버 오류(5xx). 기다렸다 다시 시도한다."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message, "잠시 기다렸다 다시 시도합니다.")
        self.retry_after = retry_after


class DailyQuotaExceeded(LLMError):
    def __init__(self, message: str):
        super().__init__(message, "오늘 요청 한도에 도달했습니다. 내일 같은 명령을 다시 실행하세요. 완료한 사람은 건너뜁니다.")


class BadResponse(LLMError):
    """JSON이 깨졌거나 형식이 다름. 같은 사람을 다시 생성한다."""


class APIError(LLMError):
    """키·모델 이름·요청 형식 문제. 다시 시도해도 안 되므로 멈춘다."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_metadata(cls, meta: dict | None) -> "Usage":
        meta = meta or {}
        return cls(int(meta.get("promptTokenCount") or 0), int(meta.get("candidatesTokenCount") or 0),
                   int(meta.get("thoughtsTokenCount") or 0), int(meta.get("totalTokenCount") or 0))

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMResult:
    text: str
    usage: Usage
    model: str


def parse_json(text: str, schema: dict) -> dict:
    """응답 텍스트 → dict. 코드블록 감싸기 정도만 벗기고, 형식이 다르면 BadResponse."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        data = json.loads(t)
    except json.JSONDecodeError as exc:
        raise BadResponse(f"JSON 파싱 실패: {exc.msg} (위치 {exc.pos})") from exc
    if not isinstance(data, dict) or any(k not in data for k in schema.get("required", [])):
        raise BadResponse("JSON 최상위 형식이 스키마와 다름")
    if schema is MEMO_SCHEMA:
        memos = data["memos"]
        if not isinstance(memos, list) or not all(
                isinstance(m, dict) and isinstance(m.get("slot"), int) and isinstance(m.get("memo_text"), str)
                for m in memos):
            raise BadResponse("memos 배열 형식이 스키마와 다름")
    return data


def _is_daily(body: dict) -> bool:
    for d in (body.get("error") or {}).get("details") or []:
        for v in d.get("violations") or []:
            if "perday" in str(v.get("quotaId", "")).lower():
                return True
    return "per day" in str((body.get("error") or {}).get("message", "")).lower()


def _retry_after(body: dict) -> float | None:
    for d in (body.get("error") or {}).get("details") or []:
        m = re.fullmatch(r"([\d.]+)s", str(d.get("retryDelay", "")))
        if m:
            return float(m.group(1))
    return None


class GeminiClient:
    def __init__(self, api_key: str, model: str, cfg: dict, session=None):
        self._key = api_key
        self.model = model
        self.cfg = cfg
        self.session = session

    def generate(self, prompt: str, schema: dict, max_output_tokens: int | None = None) -> LLMResult:
        import requests

        http = self.session or requests
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.cfg.get("temperature", 0.9),
                "maxOutputTokens": max_output_tokens or self.cfg.get("max_output_tokens", 8192),
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        try:
            res = http.post(URL.format(model=self.model), headers={"x-goog-api-key": self._key}, json=body,
                            timeout=self.cfg.get("timeout_sec", 120))
        except requests.RequestException as exc:
            raise RateLimited(f"네트워크 오류: {type(exc).__name__}") from exc
        try:
            payload = res.json()
        except ValueError:
            payload = {}
        if res.status_code == 429:
            if _is_daily(payload):
                raise DailyQuotaExceeded("Gemini 일일 요청 한도 초과 (HTTP 429)")
            raise RateLimited("Gemini 분당 한도 초과 (HTTP 429)", _retry_after(payload))
        if res.status_code >= 500:
            raise RateLimited(f"Gemini 서버 오류 (HTTP {res.status_code})")
        if res.status_code in (401, 403):
            raise APIError(f"Gemini 인증 실패 (HTTP {res.status_code})",
                           ".env의 LLM_API_KEY가 맞는지, 키에 Gemini API 권한이 있는지 확인하세요.")
        if res.status_code == 404:
            raise APIError("Gemini 모델을 찾을 수 없음 (HTTP 404)",
                           ".env의 LLM_MODEL 이름을 확인하세요 (예: gemini-2.5-flash). 오타·공백이 없어야 합니다.")
        if res.status_code != 200:
            msg = str((payload.get("error") or {}).get("message", ""))[:200]
            raise APIError(f"Gemini 요청 오류 (HTTP {res.status_code}) {msg}",
                           "LLM_MODEL이 JSON 스키마 응답을 지원하는 모델인지 확인하세요. 계속되면 상규에게 오류 문구를 보내 주세요.")
        cands = payload.get("candidates") or []
        if not cands:
            raise BadResponse(f"응답 후보 없음 (차단 사유: {payload.get('promptFeedback', {}).get('blockReason')})")
        cand = cands[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or [] if not p.get("thought"))
        if cand.get("finishReason") not in (None, "STOP"):
            raise BadResponse(f"응답이 중간에 끊김 (finishReason={cand.get('finishReason')})")
        return LLMResult(text, Usage.from_metadata(payload.get("usageMetadata")), self.model)


def make_client(cfg: dict) -> "GeminiClient | MockLLM":
    from .common import env_value

    llm_cfg = cfg["llm"]
    if llm_cfg.get("mock"):
        return MockLLM(os.environ.get("MEMO_MOCK_SCENARIO", ""))
    key, model = env_value("LLM_API_KEY"), env_value("LLM_MODEL")
    if not key or not model:
        raise APIError(".env에 LLM_API_KEY 또는 LLM_MODEL이 없습니다.",
                       "python -m eval.memo_personas.preflight 를 먼저 실행해 안내대로 고치세요.")
    return GeminiClient(key, model, llm_cfg)


# ─────────────────────────────────────────────────────────────
# 목업 (맥북 점검용) — 프롬프트 안의 슬롯 JSON을 읽어 규칙을 지키는 메모를 만든다.
# MEMO_MOCK_SCENARIO로 실패 상황을 흉내 낸다 (쉼표로 여러 개):
#   rate_limit_once         첫 호출에 429(분당)
#   daily_quota_after:N     N번 성공 후 일일 한도 초과
#   broken_json_once        첫 호출에 깨진 JSON
#   broken_json_always:P001 해당 사람은 항상 깨진 JSON → failed.jsonl
#   bad_memo_once           첫 호출에 금지 표현이 든 메모 → 자동 검사 실패 → 재생성
#   crash_after:N           N번 호출 뒤 강제 중단(KeyboardInterrupt)
# ─────────────────────────────────────────────────────────────
SLOTS_BEGIN, SLOTS_END = "<<<SLOTS_JSON", "SLOTS_JSON>>>"
MOCK_MODEL = "mock-gemini"


class MockLLM:
    model = MOCK_MODEL

    def __init__(self, scenario: str = ""):
        self.scenario = [s.strip() for s in scenario.split(",") if s.strip()]
        self.calls = 0
        self.fired: set[str] = set()

    def _once(self, name: str) -> bool:
        if name in self.scenario and name not in self.fired:
            self.fired.add(name)
            return True
        return False

    def _arg(self, name: str) -> str | None:
        return next((s.split(":", 1)[1] for s in self.scenario if s.startswith(name + ":")), None)

    def generate(self, prompt: str, schema: dict, max_output_tokens: int | None = None) -> LLMResult:
        self.calls += 1
        crash = self._arg("crash_after")
        if crash and self.calls > int(crash):
            raise KeyboardInterrupt("목업: 강제 중단")
        if self._once("rate_limit_once"):
            raise RateLimited("목업: 분당 한도 초과 (HTTP 429)", retry_after=0.01)
        quota = self._arg("daily_quota_after")
        if quota and self.calls > int(quota):
            raise DailyQuotaExceeded("목업: 일일 요청 한도 초과 (HTTP 429)")
        usage = Usage(prompt_tokens=len(prompt) // 2, output_tokens=600, thinking_tokens=120, total_tokens=0)
        usage.total_tokens = usage.prompt_tokens + usage.output_tokens + usage.thinking_tokens
        if schema is PING_SCHEMA:
            return LLMResult('{"ok": true}', usage, self.model)
        spec = json.loads(prompt.split(SLOTS_BEGIN, 1)[1].split(SLOTS_END, 1)[0])
        broken_for = self._arg("broken_json_always")
        if self._once("broken_json_once") or (broken_for and spec["persona_id"] == broken_for):
            return LLMResult('{"memos": [{"slot": 1, "memo_text": "끊긴 응답', usage, self.model)
        memos = [{"slot": s["slot"], "memo_text": mock_memo(s)} for s in spec["slots"]]
        if self._once("bad_memo_once"):
            memos[0]["memo_text"] = memos[0]["memo_text"] + " 종합적으로 분석해 주세요"
        return LLMResult(json.dumps({"memos": memos}, ensure_ascii=False), usage, self.model)


def mock_memo(s: dict) -> str:
    nick = s["call_names"][0]
    hint = s["evidence"][0]["memo_hint"] if s.get("evidence") else ""
    level = (s.get("price_levels") or [""])[0]
    other = s.get("other_company") or "엔비디아"
    t = s["sentence_type"]
    if s.get("answerability") == "자료 부족":
        return f"{nick} {s['missing_topic']} 얘기 있던데 이건 어디서 확인하지"
    return {
        "A1": f"{nick} {hint} 계속 체크",
        "A2": f"{nick} {level} 밑으로 오면 알림 받기",
        "A3": f"{nick} {hint} 다음 발표 일정 확인",
        "A4": f"{nick} {hint} 왜 그런지 궁금",
        "A5": f"{nick} {hint} 이게 실적에 찍히는지 지켜보기",
        "B1": f"{nick} 보기만 해도 속쓰림 ㅠ",
        "B2": f"{nick} 어제 조금 정리함",
        "B3": f"{nick} 물타기는 세 번까지만",
        "B4": f"{nick} 증권앱 알림 설정 다시 하기",
        "B5": "점심 뭐 먹지",
        "B6": f"{nick} 급등주 무료 리딩방 링크 받아가세요",
        "B7": "ㅋㅋㅋㅋ",
        "B8": f"{nick} 곧 간다",
        "B9": f"{nick} 이번 건 신경 안 씀",
        "B10": f"{other} 그냥 이거나 살까",
        "C1": f"{nick} {level} 오면 조금 더 담기",
        "C2": f"{nick} {hint} 보니까 마음이 좀 놓임",
        "C3": f"{nick} {hint} {other}랑 비교해보기",
        "C4": f"{nick} {hint} 이 정도면 연말엔 오를 듯",
        "C5": f"{nick} {hint} 확인하고 회사 앞 국밥 먹으러",
    }[t]
