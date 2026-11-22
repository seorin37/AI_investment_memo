"""투자 실험실: LLM 답 검사·재시도·대체와 API의 크레딧 처리 (DB·LLM 없이)."""
from __future__ import annotations

import json
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.db import get_read_db
from app.studio_lab import routes
from app.studio_lab.lab import THEORY_BASE, run_lab
from app.studio_lab.prompt import FEWSHOT_ANSWER, FEWSHOT_CHANGED, SYSTEM, StockCtx, build_user, messages
from app.studio_lab.rules import GENERAL, FINANCIAL, VARS, fallback
from app.studio_lab.schema import LAB_SCHEMA, check

STOCK = StockCtx("005930", "삼성전자", overview="메모리 반도체·스마트폰·가전을 만드는 전자 기업")
DIRS = ["유지", "상승", "유지", "하락"]
CHANGED = [("국제유가(WTI)", "상승"), ("미국 10년물 국채금리", "하락")]
LEAF = {"t": "전력·소재 원가 부담 증가", "why": "유가가 오르면 전력과 화학 소재 값이 오르기 쉬워요. 공장 가동 비용이 커질 수 있어요.",
        "note": "제품 가격 전가에 따라 달라요.", "check": "원재료 비용 비중", "check_why": "사업보고서 원재료 항목"}
GOOD = {"paths": [{"var": "국제유가(WTI)", "dir": "상승", "leaves": [LEAF]},
                  {"var": "미국 10년물 국채금리", "dir": "하락", "leaves": [{**LEAF, "t": "자금 조달 부담 완화"}]}]}


def fake(*answers):
    calls = []

    def llm(msgs):
        calls.append(msgs)
        answer = answers[min(len(calls), len(answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return json.loads(json.dumps(answer))
    llm.calls = calls
    return llm


def changed_answer(**leaf):
    answer = json.loads(json.dumps(GOOD))
    answer["paths"][0]["leaves"][0].update(leaf)
    return answer


def test_fewshot_passes_rules():
    assert check(FEWSHOT_ANSWER, FEWSHOT_CHANGED, []) == []


def test_good_answer_maps_to_screen_groups():
    llm = fake(GOOD)
    result = run_lab(STOCK, DIRS, llm)
    assert result["source"] == "llm" and len(llm.calls) == 1
    assert [(g["i"], g["d"]) for g in result["groups"]] == [(1, "상승"), (3, "하락")]
    leaf = result["groups"][0]["leaves"][0]
    assert leaf["ev"] is False and leaf["base"] == THEORY_BASE
    assert set(leaf) == {"t", "why", "note", "check", "check_why", "ev", "base"}


def test_banned_word_retries_with_feedback():
    llm = fake(changed_answer(why="금리가 내리면 주가가 오를 가능성이 커요. 호재로 볼 수 있어요."), GOOD)
    result = run_lab(STOCK, DIRS, llm)
    assert result["source"] == "llm" and result["_meta"]["tries"] == 2
    assert "호재" in llm.calls[1][-1]["content"]


def test_uncertain_word_is_not_banned():
    assert check(changed_answer(note="계약 조건이 불확실하면 효과가 달라요."), CHANGED, []) == []


def test_number_must_come_from_input():
    bad = changed_answer(why="해외 매출 비중이 85%라서 환율 영향이 클 수 있어요.")
    assert any("숫자" in error for error in check(bad, CHANGED, []))
    assert not any("숫자" in error for error in check(bad, CHANGED, ["해외 비중 85%"]))
    quoted = changed_answer(why="유가가 지금 71.4달러에서 오르면 원가 부담이 커질 수 있어요.")
    assert run_lab(STOCK, DIRS, fake(quoted), macro=[("국제유가(WTI)", "71.4달러")])["source"] == "llm"


def test_wrong_order_and_leaf_count_rejected():
    assert any("입력" in error for error in check({"paths": GOOD["paths"][::-1]}, CHANGED, []))
    too_many = json.loads(json.dumps(GOOD))
    too_many["paths"][0]["leaves"] = [LEAF, LEAF, LEAF]
    assert any("1~2개" in error for error in check(too_many, CHANGED, []))


def test_bond_direction_must_match_rate_direction():
    changed = [("미국 10년물 국채금리", "하락")]
    wrong = {"paths": [{"var": changed[0][0], "dir": "하락", "leaves": [{**LEAF, "t": "해외 채권 평가 손실 가능성"}]}]}
    right = {"paths": [{"var": changed[0][0], "dir": "하락", "leaves": [{**LEAF, "t": "보유 채권 평가 이익"}]}]}
    assert any("반대" in error for error in check(wrong, changed, []))
    assert check(right, changed, []) == []


def test_two_failures_use_general_paths():
    result = run_lab(STOCK, DIRS, fake(TimeoutError("timeout"), {"paths": []}))
    assert result["source"] == "rules"
    assert [len(g["leaves"]) for g in result["groups"]] == [1, 2]


def test_every_fallback_passes_rules():
    for financial in (False, True):
        for var in VARS:
            for direction in ("상승", "하락"):
                assert check(fallback(financial, [(var, direction)]), [(var, direction)], []) == []
    assert set(FINANCIAL) <= set(GENERAL)


def test_prompt_has_only_changed_vars():
    user = build_user(STOCK, CHANGED)
    assert "유지" not in user and "var=국제유가(WTI) / dir=상승" in user
    assert messages(STOCK, CHANGED)[0]["content"] == SYSTEM


def test_schema_is_strict():
    root = LAB_SCHEMA["schema"]
    path = root["properties"]["paths"]["items"]
    leaf = path["properties"]["leaves"]["items"]
    assert LAB_SCHEMA["strict"] and not root["additionalProperties"]
    assert not path["additionalProperties"] and not leaf["additionalProperties"]


def client(monkeypatch, answer, balance=30):
    spent = []

    @contextmanager
    def session():
        yield object()

    class Read:
        def rollback(self):
            pass

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 7}
    app.dependency_overrides[get_read_db] = lambda: Read()
    monkeypatch.setattr(routes, "_stock", lambda _db, code: STOCK if code == "005930" else None)
    monkeypatch.setattr(routes, "_macro", lambda _db: ([], ""))
    monkeypatch.setattr(routes, "get_session", session)
    monkeypatch.setattr(routes, "openai_call", fake(answer))
    monkeypatch.setattr(routes.ledger, "cost", lambda _reason: 3)
    monkeypatch.setattr(routes.ledger, "refresh", lambda _db, _user: None)
    monkeypatch.setattr(routes.ledger, "balance", lambda _db, _user: balance)
    monkeypatch.setattr(routes.ledger, "spend", lambda _db, user, amount, reason: spent.append((user, amount, reason)) or amount)
    return TestClient(app), spent


def test_api_charges_only_llm_result(monkeypatch):
    api, spent = client(monkeypatch, GOOD)
    response = api.post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS})
    assert response.status_code == 200 and response.json()["credits_used"] == 3
    assert "_meta" not in response.json() and spent == [(7, 3, "lab")]


def test_api_does_not_charge_fallback(monkeypatch):
    api, spent = client(monkeypatch, TimeoutError("timeout"))
    response = api.post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS})
    assert response.status_code == 200 and response.json()["source"] == "rules"
    assert response.json()["credits_used"] == 0 and spent == []


def test_api_rejects_low_credit_hold_only_and_unknown_stock(monkeypatch):
    api, spent = client(monkeypatch, GOOD, balance=2)
    assert api.post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS}).status_code == 402
    assert api.post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": ["유지"] * 4}).status_code == 422
    assert api.post("/api/v1/studio/lab", json={"stock_code": "000000", "dirs": DIRS}).status_code == 404
    assert spent == []


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.content = b"x"

    def json(self):
        return self._body


def test_openai_call_drops_temperature_when_model_rejects_it(monkeypatch):
    """2026-11-22: 팀 .env 모델(gpt-6.1-sol)은 temperature 0.2 를 400 으로 거부 → 빼고 다시, 다음부터는 처음부터 뺌"""
    from app.studio_lab import llm

    sent = []
    ok = {"choices": [{"message": {"content": "{\"groups\": []}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

    def post(url, headers, json, timeout):
        sent.append(dict(json))
        if "temperature" in json:
            return _Resp(400, {"error": {"param": "temperature", "message": "Unsupported value: 'temperature'"}})
        return _Resp(200, ok)

    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm, "_NO_TEMPERATURE", set())
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("LLM_MODEL", "sol-like")
    monkeypatch.delenv("LAB_MODEL", raising=False)
    assert llm.openai_call([{"role": "user", "content": "x"}])["groups"] == []
    assert ["temperature" in b for b in sent] == [True, False]
    llm.openai_call([{"role": "user", "content": "x"}])
    assert ["temperature" in b for b in sent] == [True, False, False]          # 기억해서 바로 뺌
    assert {b["model"] for b in sent} == {"sol-like"}
