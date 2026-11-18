from datetime import datetime, timezone

import pytest

from backend.pipelines.news import same_event_judge as sj
from backend.pipelines.news.clustering import Member

T = datetime(2026, 10, 22, 0, 50, tzinfo=timezone.utc)   # 한국 시간 09:50


def art(i, title, vec=(1.0, 0.0), summary=None):
    return Member(i, T, list(vec), title=title, summary=summary)


def test_parse_verdict():
    assert sj.parse_verdict('{"same": true, "reason": "같은 결정"}') == (True, "같은 결정")
    assert sj.parse_verdict('```json\n{"same": false, "reason": "다른 국가"}\n```') == (False, "다른 국가")
    assert sj.parse_verdict('{"same": "yes"}')[0] is None
    assert sj.parse_verdict("모르겠음")[0] is None


def test_prompt_shows_least_similar_members_first_and_kst_time():
    new = art(9, "[속보] 한은, 기준금리 동결")
    members = [art(i, f"기사{i}", (1.0, i / 10)) for i in range(1, 8)]
    prompt = sj.build_prompt(new, members, lambda x: x.dense[0] / (x.dense[0] ** 2 + x.dense[1] ** 2) ** 0.5)
    assert "(10-22 09:50) [속보] 한은, 기준금리 동결" in prompt
    shown = [f"기사{i}" for i in range(1, 8) if f"기사{i}" in prompt]
    assert shown == ["기사3", "기사4", "기사5", "기사6", "기사7"]           # 덜 비슷한 5건


def test_judge_counts_and_budget():
    answers = iter(['{"same": true, "reason": "a"}', '{"same": false, "reason": "b"}', "깨진 답"])
    judge = sj.SameEventJudge(lambda prompt: next(answers), max_calls=4)
    new, members = art(9, "새 기사"), [art(1, "묶음 기사")]
    assert [judge(new, members) for _ in range(3)] == [True, False, None]

    def boom(prompt):
        raise RuntimeError("HTTP 500")
    judge.call = boom
    assert judge(new, members) is None                                    # 오류도 None (합류 안 함)
    assert judge(new, members) is None                                    # 한도(4회) 넘음 → 묻지 않음
    assert judge.stats.as_dict() == {"calls": 4, "same": 1, "different": 1, "unavailable": 2, "skipped_budget": 1}
    assert judge.last_reason == "호출 한도 초과"


def test_llm_key_comes_only_from_openai_api_key(monkeypatch):
    monkeypatch.setattr("backend.pipelines.common.db.load_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "other-key")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        sj.llm_from_env()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    client = sj.llm_from_env()
    assert client.api_key == "test-key" and client.model == "gpt-test"
    assert "test-key" not in repr(client)                                 # 키는 repr에 안 나옴
