"""Gemini 호출기 — 문장 판정 LLM 단계용. 호출마다 지연시간·토큰 수를 기록한다.

API 키는 저장소 루트 `.env`의 `LLM_API_KEY`를 프로그램 안에서만 읽고 출력·저장하지 않는다 (D-025).
모델은 `LLM_MODEL`(기본 gemini-3.1-flash-lite). JSON 응답 모드, temperature 0.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

from ..common.config import REPO_ROOT
from ..common.retry import retry_call

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
RETRY_STATUS = {429, 500, 502, 503, 504}


class TransientError(RuntimeError):
    """재시도할 만한 일시 오류 (쿼터 초과·서버 오류·타임아웃)."""


@dataclass
class CallRecord:
    latency_ms: float
    prompt_tokens: int | None
    output_tokens: int | None
    ok: bool


@dataclass
class GeminiClient:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout: float = 60.0
    attempts: int = 4
    session: object = field(default=None, repr=False)
    calls: list[CallRecord] = field(default_factory=list)

    @classmethod
    def from_env(cls, model: str | None = None) -> "GeminiClient":
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
        key = os.getenv("LLM_API_KEY")
        if not key:
            raise RuntimeError(".env에 LLM_API_KEY가 없습니다.")
        return cls(api_key=key, model=model or os.getenv("LLM_MODEL") or DEFAULT_MODEL)

    def _post_once(self, prompt: str) -> dict:
        http = self.session or requests
        try:
            res = http.post(
                URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise TransientError("timeout") from exc
        if res.status_code in RETRY_STATUS:
            raise TransientError(f"HTTP {res.status_code}")
        if res.status_code != 200:
            # 본문에 키가 들어 있지 않지만, 길게 출력하지 않는다
            raise RuntimeError(f"Gemini HTTP {res.status_code}: {res.text[:200]}")
        return res.json()

    def __call__(self, prompt: str) -> str:
        start = time.perf_counter()
        try:
            data = retry_call(lambda: self._post_once(prompt), attempts=self.attempts, base_delay=2.0,
                              retry_on=(TransientError,))
        except Exception:
            self.calls.append(CallRecord((time.perf_counter() - start) * 1000, None, None, False))
            raise
        usage = data.get("usageMetadata", {})
        self.calls.append(CallRecord((time.perf_counter() - start) * 1000, usage.get("promptTokenCount"),
                                     usage.get("candidatesTokenCount"), True))
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
