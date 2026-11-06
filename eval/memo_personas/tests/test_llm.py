import json

import pytest

from eval.memo_personas import llm


class FakeRes:
    def __init__(self, status, body, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.text = json.dumps(body) if isinstance(body, dict) else str(body)

    def json(self):
        if isinstance(self._body, dict):
            return self._body
        raise ValueError


class FakeSession:
    def __init__(self, res):
        self.res, self.calls = (list(res) if isinstance(res, list) else [res]), []

    def post(self, url, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.res.pop(0) if len(self.res) > 1 else self.res[0]


def client(res):
    s = FakeSession(res)
    return llm.OpenAIClient("SECRET-KEY", "gpt-test", {"temperature": 0.5}, session=s), s


def ok_body(text, finish="stop", usage=None):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": usage or {"prompt_tokens": 100, "completion_tokens": 27, "total_tokens": 127,
                               "completion_tokens_details": {"reasoning_tokens": 7}}}


def test_success_parses_usage_and_sends_schema():
    c, s = client(FakeRes(200, ok_body('{"memos": []}')))
    r = c.generate("p", llm.MEMO_SCHEMA)
    assert r.text == '{"memos": []}'
    # output = completion - reasoning, 그래서 입력 + 출력 + thinking = 합계
    assert r.usage.as_dict() == {"prompt_tokens": 100, "output_tokens": 20, "thinking_tokens": 7, "total_tokens": 127}
    sent = s.calls[0]
    assert sent["headers"] == {"Authorization": "Bearer SECRET-KEY"} and "SECRET-KEY" not in sent["url"]
    assert sent["json"]["model"] == "gpt-test" and sent["json"]["temperature"] == 0.5
    fmt = sent["json"]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] is llm.MEMO_SCHEMA
    assert sent["json"]["max_completion_tokens"] == 8192


def test_temperature_is_dropped_when_model_rejects_it():
    reject = FakeRes(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0.5 with this model."}})
    c, s = client([reject, FakeRes(200, ok_body('{"memos": []}'))])
    assert c.generate("p", llm.MEMO_SCHEMA).text == '{"memos": []}'
    assert "temperature" in s.calls[0]["json"] and "temperature" not in s.calls[1]["json"]
    c.generate("p", llm.MEMO_SCHEMA)            # 한 번 알게 되면 다음 호출부터는 처음부터 빼고 보낸다
    assert "temperature" not in s.calls[2]["json"]


def test_429_per_minute_vs_daily_vs_out_of_credit():
    minute = {"error": {"code": "rate_limit_exceeded", "message": "Rate limit reached for requests per min (RPM). Please try again in 1.5s."}}
    daily = {"error": {"code": "rate_limit_exceeded", "message": "Rate limit reached for requests per day (RPD)."}}
    credit = {"error": {"code": "insufficient_quota", "type": "insufficient_quota", "message": "You exceeded your current quota"}}
    with pytest.raises(llm.RateLimited) as e:
        client(FakeRes(429, minute))[0].generate("p", llm.MEMO_SCHEMA)
    assert e.value.retry_after == 1.5
    with pytest.raises(llm.RateLimited) as e:
        client(FakeRes(429, minute, {"retry-after": "12"}))[0].generate("p", llm.MEMO_SCHEMA)
    assert e.value.retry_after == 12
    with pytest.raises(llm.DailyQuotaExceeded):
        client(FakeRes(429, daily))[0].generate("p", llm.MEMO_SCHEMA)
    with pytest.raises(llm.APIError) as e:                     # 크레딧 소진은 기다려도 안 풀린다 → 재시도 없이 멈춤
        client(FakeRes(429, credit))[0].generate("p", llm.MEMO_SCHEMA)
    assert "크레딧" in str(e.value)


@pytest.mark.parametrize("status,exc", [(401, llm.APIError), (404, llm.APIError), (503, llm.RateLimited),
                                        (400, llm.APIError)])
def test_error_classes(status, exc):
    with pytest.raises(exc):
        client(FakeRes(status, {"error": {"message": "x"}}))[0].generate("p", llm.MEMO_SCHEMA)


def test_truncated_response_is_bad_response():
    with pytest.raises(llm.BadResponse):
        client(FakeRes(200, ok_body('{"memos": [', finish="length")))[0].generate("p", llm.MEMO_SCHEMA)


def test_refusal_is_bad_response():
    body = {"choices": [{"message": {"content": None, "refusal": "죄송합니다"}, "finish_reason": "stop"}], "usage": {}}
    with pytest.raises(llm.BadResponse):
        client(FakeRes(200, body))[0].generate("p", llm.MEMO_SCHEMA)


def test_schemas_follow_strict_mode_rules():
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                check(v)

    check(llm.MEMO_SCHEMA)
    check(llm.PING_SCHEMA)


def test_parse_json():
    assert llm.parse_json('```json\n{"memos": [{"slot": 1, "memo_text": "a"}]}\n```', llm.MEMO_SCHEMA)["memos"][0]["slot"] == 1
    with pytest.raises(llm.BadResponse):
        llm.parse_json('{"memos": [{"slot": "1", "memo_text": "a"}]}', llm.MEMO_SCHEMA)
    with pytest.raises(llm.BadResponse):
        llm.parse_json('{"memos": [', llm.MEMO_SCHEMA)
