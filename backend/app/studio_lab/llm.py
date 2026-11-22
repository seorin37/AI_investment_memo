"""OpenAI 구조화 출력 호출. 키와 모델은 환경변수에서만 읽고 출력하지 않는다."""
from __future__ import annotations

import json
import os

import requests

from .schema import LAB_SCHEMA

URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"


def openai_call(messages: list[dict]) -> dict:
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("LLM 키가 설정되지 않았어요")
    response = requests.post(
        URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.getenv("LAB_MODEL") or os.getenv("LLM_MODEL") or DEFAULT_MODEL,
            "messages": messages,
            "temperature": float(os.getenv("LAB_TEMPERATURE", "0.2")),
            "response_format": {"type": "json_schema", "json_schema": LAB_SCHEMA},
        },
        timeout=float(os.getenv("LAB_TIMEOUT", "25")),
    )
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
