"""OpenAI 구조화 출력 호출 (대본). 키·모델은 환경변수에서만 읽고 출력하지 않는다. studio_lab.llm과 같은 방식."""
from __future__ import annotations

import json
import os

import requests

from .schema import AUDIO_SCHEMA

URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"
_NO_TEMPERATURE: set[str] = set()       # temperature를 기본값만 받는 모델 (한 번 거부되면 기억한다)


def model_name(cfg: dict | None = None) -> str:
    env = ((cfg or {}).get("script") or {}).get("model_env", "STUDIO_AUDIO_MODEL")
    return os.getenv(env) or os.getenv("LLM_MODEL") or DEFAULT_MODEL


def _rejects_temperature(response: requests.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    return error.get("param") == "temperature" or "temperature" in str(error.get("message", ""))


def openai_call(messages: list[dict], cfg: dict | None = None) -> dict:
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("LLM 키가 설정되지 않았어요")
    model = model_name(cfg)
    payload = {"model": model, "messages": messages,
               "response_format": {"type": "json_schema", "json_schema": AUDIO_SCHEMA}}
    if model not in _NO_TEMPERATURE:
        payload["temperature"] = float(((cfg or {}).get("script") or {}).get("temperature", 0.5))
    timeout = float(os.getenv("STUDIO_AUDIO_TIMEOUT", "120"))

    def post(body: dict) -> requests.Response:
        return requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=timeout)

    response = post(payload)
    if "temperature" in payload and _rejects_temperature(response):
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
    answer["_usage"] = {"model": model, "input": usage.get("prompt_tokens"), "output": usage.get("completion_tokens")}
    return answer
