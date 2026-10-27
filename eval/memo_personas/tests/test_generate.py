"""generate_memos 흐름 (목업 Gemini, DB 없이 만든 근거 묶음)."""

import json
from pathlib import Path

import pytest
import yaml

from eval.memo_personas import generate_memos as gm
from eval.memo_personas.common import read_json, read_jsonl


@pytest.fixture
def env(tmp_path, base_cfg, fake_packs, monkeypatch):
    packs, macro = fake_packs
    ev = tmp_path / "evidence"
    ev.mkdir()
    for code, p in packs.items():
        (ev / f"{code}.json").write_text(json.dumps(p, ensure_ascii=False, default=str), encoding="utf-8")
    (ev / "macro.json").write_text(json.dumps(macro, ensure_ascii=False, default=str), encoding="utf-8")
    cfg = {k: v for k, v in base_cfg.items() if k != "_path"}
    cfg["paths"] = dict(cfg["paths"], evidence_dir=str(ev), memos_dir=str(tmp_path / "memos"))
    cfg["llm"] = dict(cfg["llm"], mock=True, requests_per_minute=600000, backoff_base_sec=0.0)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("MEMO_CONFIG", str(path))
    monkeypatch.delenv("MEMO_MOCK_SCENARIO", raising=False)
    return tmp_path / "memos", path


def test_pilot_then_all(env, capsys):
    memos_dir, _ = env
    assert gm.main(["--pilot"]) == 0
    assert len(read_jsonl(memos_dir / "memos.jsonl")) == 100
    assert "summary.txt를 상규에게" in capsys.readouterr().out
    assert gm.main(["--all"]) == 0
    memos = read_jsonl(memos_dir / "memos.jsonl")
    assert len(memos) == 1000 and len({m["memo_id"] for m in memos}) == 1000
    usage = read_jsonl(memos_dir / "usage.jsonl")
    assert len(usage) == 100 and all({"prompt_tokens", "output_tokens", "thinking_tokens"} <= set(u) for u in usage)
    assert all(m["review_status"] == "pending" and m["generator_model"] == "mock-gemini" for m in memos)


def test_resume_after_interrupt(env, monkeypatch, capsys):
    memos_dir, _ = env
    monkeypatch.setenv("MEMO_MOCK_SCENARIO", "crash_after:2")
    assert gm.main(["--pilot"]) == 130
    assert len(list((memos_dir / "persons").glob("*.json"))) == 2
    monkeypatch.delenv("MEMO_MOCK_SCENARIO")
    assert gm.main(["--pilot"]) == 0
    assert "이번에 할 사람 8명" in capsys.readouterr().out


def test_failed_person_recorded_then_retried(env, monkeypatch):
    memos_dir, _ = env
    assert gm.main(["--pilot"]) == 0
    design = read_json(memos_dir / "slot_design.json")
    victim = next(p["persona_id"] for p in design["persons"] if p["persona_id"] not in design["pilot"])
    monkeypatch.setenv("MEMO_MOCK_SCENARIO", f"broken_json_always:{victim}")
    assert gm.main(["--all"]) == 0
    failed = read_jsonl(memos_dir / "failed.jsonl")
    assert [f["persona_id"] for f in failed] == [victim] and failed[0]["attempts"] == 3
    monkeypatch.delenv("MEMO_MOCK_SCENARIO")
    assert gm.main(["--all"]) == 0
    assert read_jsonl(memos_dir / "failed.jsonl") == []


def test_local_daily_budget(env, capsys):
    memos_dir, path = env
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["llm"]["requests_per_day"] = 3
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    assert gm.main(["--pilot"]) == gm.EXIT_PAUSED
    assert "내일 같은 명령을 다시 실행하세요" in capsys.readouterr().out
    assert read_json(memos_dir / "_state" / "requests.json")["count"] == 3


def test_changed_evidence_stops_resume(env, capsys):
    memos_dir, path = env
    assert gm.main(["--pilot"]) == 0
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    f = Path(cfg["paths"]["evidence_dir"]) / "005930.json"
    f.write_text(f.read_text(encoding="utf-8").replace("삼성전자", "삼성전자 ", 1), encoding="utf-8")
    assert gm.main(["--all"]) == 1
    assert "처음 생성할 때와 입력이 달라졌습니다" in capsys.readouterr().out


def test_request_budget_spacing(tmp_path):
    t = {"now": 1000.0}
    slept = []
    b = gm.RequestBudget(tmp_path / "r.json", rpm=6, rpd=10, clock=lambda: t["now"], sleep=lambda s: slept.append(s))
    b.take()
    b.take()
    assert slept and abs(slept[0] - 10.0) < 1e-6
