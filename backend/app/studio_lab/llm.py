"""OpenAI 구조화 출력 호출. 키와 모델은 환경변수에서만 읽고 출력하지 않는다."""
from __future__ import annotations

import json
import os

import requests

from .schema import LAB_SCHEMA

URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"

# temperature 를 기본값(1)만 받는 모델 (예: 팀 .env 의 gpt-6.1-sol). 한 번 거부되면 기억하고 다음부터 빼고 보낸다
_NO_TEMPERATURE: set[str] = set()


def _rejects_temperature(response: requests.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    return error.get("param") == "temperature" or "temperature" in str(error.get("message", ""))


def openai_call(messages: list[dict]) -> dict:
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("LLM 키가 설정되지 않았어요")
    model = os.getenv("LAB_MODEL") or os.getenv("LLM_MODEL") or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_schema", "json_schema": LAB_SCHEMA},
    }
    if model not in _NO_TEMPERATURE:
        payload["temperature"] = float(os.getenv("LAB_TEMPERATURE", "0.2"))
    timeout = float(os.getenv("LAB_TIMEOUT", "60"))

    def post(body: dict) -> requests.Response:
        return requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=timeout)

    response = post(payload)
    if "temperature" in payload and _rejects_temperature(response):
        # 2026-11-22: gpt-6.1-sol 은 temperature 0.2 를 400 으로 거부 → 빼고 한 번 더 (실험실 재시도 횟수에는 안 셈)
        _NO_TEMPERATURE.add(model)
        payload.pop("temperature")
        response = post(payload)
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {response.status_code}")
    data = response.json()
    message = data["choices"][0]["message"]
    if message.get("refusal"):
        raise RuntimeError("LLM이 답을 거절했어요")
    answer = json.loads(message["content"])
    usage = data.get("usage") or {}
    answer["_usage"] = {"input": usage.get("prompt_tokens"), "output": usage.get("completion_tokens")}
    return answer
