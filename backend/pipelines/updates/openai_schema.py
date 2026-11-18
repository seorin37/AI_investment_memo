"""Structured Outputs(json_schema)를 붙이는 OpenAIClient (미검증, 기본 꺼짐). tracking/openai_client.py는 수정하지 않고 상속해서 확장한다.

judge.py의 RESPONSE_SCHEMA는 대문자 type(OBJECT·STRING…)으로 적혀 있어서 OpenAI용 JSON Schema로 바꿔서 쓴다:
- type을 소문자로, 모든 object에 additionalProperties=false (strict 모드 요건)
- maxItems 등 길이 제한은 뺀다. 길이·형식은 코드(checks.py)가 다시 검사한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tracking.openai_client import OpenAIClient
from .judge import RESPONSE_SCHEMA

_DROP = {"maxItems", "minItems", "maxLength", "minLength"}


def to_json_schema(schema: dict) -> dict:
    """judge.py의 (대문자 type 표기) 스키마 → OpenAI strict JSON Schema."""
    if isinstance(schema, list):
        return [to_json_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key, value in schema.items():
        if key in _DROP:
            continue
        if key == "type" and isinstance(value, str):
            out[key] = value.lower()
        elif key in ("properties",):
            out[key] = {k: to_json_schema(v) for k, v in value.items()}
        elif key in ("items",):
            out[key] = to_json_schema(value)
        else:
            out[key] = value
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out.setdefault("required", list(out.get("properties", {})))
    return out


def response_format(schema: dict = RESPONSE_SCHEMA, name: str = "update_card") -> dict:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": to_json_schema(schema)}}


@dataclass
class SchemaOpenAIClient(OpenAIClient):
    response_format: dict = field(default_factory=response_format)
