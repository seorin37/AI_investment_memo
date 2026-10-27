"""responseSchema를 붙이는 GeminiClient (미검증, 기본 꺼짐). tracking/gemini.py는 수정하지 않고 상속해서 확장한다."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..tracking.gemini import RETRY_STATUS, URL, GeminiClient, TransientError
from .judge import RESPONSE_SCHEMA


@dataclass
class SchemaGeminiClient(GeminiClient):
    def _post_once(self, prompt: str) -> dict:
        http = self.session or requests
        try:
            res = http.post(
                URL.format(model=self.model), headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                           "responseSchema": RESPONSE_SCHEMA}},
                timeout=self.timeout)
        except requests.Timeout as exc:
            raise TransientError("timeout") from exc
        if res.status_code in RETRY_STATUS:
            raise TransientError(f"HTTP {res.status_code}")
        if res.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {res.status_code}: {res.text[:200]}")
        return res.json()
