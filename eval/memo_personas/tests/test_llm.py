import json

import pytest

from eval.memo_personas import llm


class FakeRes:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = json.dumps(body) if isinstance(body, dict) else str(body)

    def json(self):
        if isinstance(self._body, dict):
            return self._body
        raise ValueError


class FakeSession:
    def __init__(self, res):
        self.res, self.calls = res, []

    def post(self, url, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.res


def client(res):
    s = FakeSession(res)
    return llm.GeminiClient("SECRET-KEY", "gemini-test", {"temperature": 0.5}, session=s), s


def test_success_parses_usage_and_sends_schema():
    body = {"candidates": [{"content": {"parts": [{"text": "생각", "thought": True}, {"text": '{"memos": []}'}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 7,
                              "totalTokenCount": 127}}
    c, s = client(FakeRes(200, body))
    r = c.generate("p", llm.MEMO_SCHEMA)
    assert r.text == '{"memos": []}'
    assert r.usage.as_dict() == {"prompt_tokens": 100, "output_tokens": 20, "thinking_tokens": 7, "total_tokens": 127}
    sent = s.calls[0]
    assert sent["headers"] == {"x-goog-api-key": "SECRET-KEY"} and "SECRET-KEY" not in sent["url"]
    assert sent["json"]["generationConfig"]["responseSchema"] is llm.MEMO_SCHEMA
    assert sent["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_429_per_minute_vs_daily():
    minute = {"error": {"code": 429, "details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel"}]},
                                                 {"retryDelay": "12s"}]}}
    daily = {"error": {"code": 429, "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}
    with pytest.raises(llm.RateLimited) as e:
        client(FakeRes(429, minute))[0].generate("p", llm.MEMO_SCHEMA)
    assert e.value.retry_after == 12
    with pytest.raises(llm.DailyQuotaExceeded):
        client(FakeRes(429, daily))[0].generate("p", llm.MEMO_SCHEMA)


@pytest.mark.parametrize("status,exc", [(401, llm.APIError), (404, llm.APIError), (503, llm.RateLimited),
                                        (400, llm.APIError)])
def test_error_classes(status, exc):
    with pytest.raises(exc):
        client(FakeRes(status, {"error": {"message": "x"}}))[0].generate("p", llm.MEMO_SCHEMA)


def test_truncated_response_is_bad_response():
    body = {"candidates": [{"content": {"parts": [{"text": '{"memos": ['}]}, "finishReason": "MAX_TOKENS"}]}
    with pytest.raises(llm.BadResponse):
        client(FakeRes(200, body))[0].generate("p", llm.MEMO_SCHEMA)


def test_parse_json():
    assert llm.parse_json('```json\n{"memos": [{"slot": 1, "memo_text": "a"}]}\n```', llm.MEMO_SCHEMA)["memos"][0]["slot"] == 1
    with pytest.raises(llm.BadResponse):
        llm.parse_json('{"memos": [{"slot": "1", "memo_text": "a"}]}', llm.MEMO_SCHEMA)
    with pytest.raises(llm.BadResponse):
        llm.parse_json('{"memos": [', llm.MEMO_SCHEMA)
