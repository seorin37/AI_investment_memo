"""OpenAI 호출기 — 문장 판정·업데이트 카드 등 LLM 단계용. 호출마다 지연시간·토큰 수를 기록한다.

API 키는 저장소 루트 `.env`의 `LLM_API_KEY`를 프로그램 안에서만 읽고 출력·저장하지 않는다 (D-025).
모델은 `LLM_MODEL`(기본 gpt-4.1-mini). Chat Completions REST, JSON 응답 모드, temperature 0.

- JSON 모드(`response_format=json_object`)는 메시지에 "JSON"이라는 말이 있어야 하므로 system 메시지를 항상 붙인다.
- 일부 모델(추론 계열)은 temperature를 받지 않는다. 그런 400 오류가 오면 temperature 없이 한 번 다시 보낸다.
- 429 중 `insufficient_quota`(크레딧 소진)는 다시 시도해도 소용없으므로 재시도하지 않고 바로 오류로 올린다.
- 추론 강도: 환경변수 `LLM_REASONING_EFFORT`가 있을 때만 요청에 `reasoning_effort`를 넣는다 (없으면 모델 기본값).
- 토큰: `output_tokens`는 usage.completion_tokens(추론 토큰 포함, 과금 기준). 그중 추론 토큰은
  usage.completion_tokens_details.reasoning_tokens를 `reasoning_tokens`에 따로 적는다 (없으면 None).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

from ..common.config import REPO_ROOT
from ..common.retry import retry_call

URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"
RETRY_STATUS = {429, 500, 502, 503, 504}
SYSTEM_MESSAGE = "Respond with a single valid JSON value and nothing else."
JSON_OBJECT_FORMAT = {"type": "json_object"}


class TransientError(RuntimeError):
    """재시도할 만한 일시 오류 (속도 제한·서버 오류·타임아웃)."""


@dataclass
class CallRecord:
    latency_ms: float
    prompt_tokens: int | None
    output_tokens: int | None
    ok: bool
    reasoning_tokens: int | None = None         # output_tokens에 이미 포함된 추론 토큰 (따로 더하지 않는다)


def _error_info(res) -> tuple[str, str]:
    """응답 본문의 error.code / error.message (없으면 빈 문자열)."""
    try:
        err = (res.json() or {}).get("error") or {}
    except (ValueError, AttributeError):
        return "", ""
    return str(err.get("code") or err.get("type") or ""), str(err.get("message") or "")


def usage_totals(calls: list[CallRecord]) -> dict:
    """호출 기록 합계. reasoning_tokens는 output_tokens의 일부다."""
    return {"llm_calls": len(calls), "prompt_tokens": sum(c.prompt_tokens or 0 for c in calls),
            "output_tokens": sum(c.output_tokens or 0 for c in calls),
            "reasoning_tokens": sum(c.reasoning_tokens or 0 for c in calls)}


@dataclass
class OpenAIClient:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout: float = 60.0
    attempts: int = 4
    session: object = field(default=None, repr=False)
    calls: list[CallRecord] = field(default_factory=list)
    temperature: float | None = 0.0
    response_format: dict = field(default_factory=lambda: dict(JSON_OBJECT_FORMAT))
    reasoning_effort: str | None = field(default_factory=lambda: os.getenv("LLM_REASONING_EFFORT") or None)

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAIClient":
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
        key = os.getenv("LLM_API_KEY")
        if not key:
            raise RuntimeError(".env에 LLM_API_KEY가 없습니다.")
        return cls(api_key=key, model=model or os.getenv("LLM_MODEL") or DEFAULT_MODEL)

    def _body(self, prompt: str) -> dict:
        body = {"model": self.model,
                "messages": [{"role": "system", "content": SYSTEM_MESSAGE}, {"role": "user", "content": prompt}],
                "response_format": self.response_format}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _send(self, prompt: str):
        http = self.session or requests
        try:
            return http.post(URL, headers={"Authorization": f"Bearer {self.api_key}"}, json=self._body(prompt),
                             timeout=self.timeout)
        except requests.Timeout as exc:
            raise TransientError("timeout") from exc

    def _post_once(self, prompt: str) -> dict:
        sent_temperature = self.temperature        # 보낼 때의 값 (동시에 부른 다른 호출이 None으로 바꿔도 이 호출은 다시 보낸다)
        res = self._send(prompt)
        if res.status_code == 400 and sent_temperature is not None and "temperature" in _error_info(res)[1].lower():
            self.temperature = None  # 이 모델은 temperature를 받지 않는다 — 빼고 다시 보낸다
            res = self._send(prompt)
        if res.status_code == 429 and _error_info(res)[0] == "insufficient_quota":
            raise RuntimeError("OpenAI 크레딧(쿼터)이 부족합니다 (HTTP 429 insufficient_quota)")
        if res.status_code in RETRY_STATUS:
            raise TransientError(f"HTTP {res.status_code}")
        if res.status_code != 200:
            # 본문에 키가 들어 있지 않지만, 길게 출력하지 않는다
            raise RuntimeError(f"OpenAI HTTP {res.status_code}: {res.text[:200]}")
        return res.json()

    def __call__(self, prompt: str) -> str:
        start = time.perf_counter()
        try:
            data = retry_call(lambda: self._post_once(prompt), attempts=self.attempts, base_delay=2.0,
                              retry_on=(TransientError,))
        except Exception:
            self.calls.append(CallRecord((time.perf_counter() - start) * 1000, None, None, False))
            raise
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        self.calls.append(CallRecord((time.perf_counter() - start) * 1000, usage.get("prompt_tokens"),
                                     usage.get("completion_tokens"), True, details.get("reasoning_tokens")))
        choices = data.get("choices") or []
        return ((choices[0].get("message") or {}).get("content") or "") if choices else ""
