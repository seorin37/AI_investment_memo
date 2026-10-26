"""맥북 전체 흐름 점검 — 임시 Postgres + 목업 Gemini로 서린이 실행할 명령을 처음부터 끝까지 돌리고,
실패 상황(.env 누락, DB 연결 실패, 429, 깨진 JSON, 중간 중단 후 재개, 일일 한도)에서 안내가 맞게 나오는지 본다.

    pip install -r eval/memo_personas/requirements-dev.txt
    python -m eval.memo_personas.devtools.mac_e2e

결과물은 커밋하지 않는 곳에만 쓴다: data/_e2e/, data/evidence_packs_mock/, results/memo_personas/memos_mock/
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

from ..common import REPO_ROOT, read_json, read_jsonl
from . import fake_db

WORK = REPO_ROOT / "data" / "_e2e"
EVIDENCE = "data/evidence_packs_mock"
MEMOS = "results/memo_personas/memos_mock"
SECRET = "e2e-secret-key-value-should-never-print"


def test_config() -> Path:
    cfg = yaml.safe_load((REPO_ROOT / "eval/memo_personas/config.yaml").read_text(encoding="utf-8"))
    cfg["paths"].update(evidence_dir=EVIDENCE, memos_dir=MEMOS)
    cfg["llm"].update(mock=True, requests_per_minute=60000, backoff_base_sec=0.01)
    path = WORK / "config.test.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def run(args: list[str], env: dict) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-m", *args], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    for d in (REPO_ROOT / EVIDENCE, REPO_ROOT / MEMOS):
        if d.exists():
            shutil.rmtree(d)  # 이 스크립트가 만든 목업 결과 폴더만 지운다
    cfg_path = test_config()
    srv, url = fake_db.start(WORK / "pg")
    log, ok_all = ["# 맥북 전체 흐름 점검 결과", "", "| # | 단계 | 기대 | 결과 | 판정 |", "|---|---|---|---|---|"], True
    outputs = []
    try:
        fake_db.migrate(url)
        seeded = fake_db.seed(url)
        base = {k: v for k, v in os.environ.items() if k not in ("MEMO_MOCK_SCENARIO", "LLM_API_KEY", "LLM_MODEL", "DATABASE_URL")}
        base.update(MEMO_CONFIG=str(cfg_path), LLM_API_KEY=SECRET, LLM_MODEL="mock-model", DATABASE_URL=url)

        def step(no, title, args, expect_rc, must=(), env_over=None):
            nonlocal ok_all
            env = dict(base, **(env_over or {}))
            rc, out = run(args, env)
            leaked = SECRET in out or url in out
            passed = rc == expect_rc and all(m in out for m in must) and not leaked
            ok_all &= passed
            log.append(f"| {no} | {title} | 종료코드 {expect_rc}" + (f", 문구 {list(must)}" if must else "") +
                       f" | 종료코드 {rc}{' · 비밀값 노출!' if leaked else ''} | {'✅' if passed else '❌'} |")
            outputs.append(f"### {no}. {title}\n\n```\n{out.strip()[-2500:]}\n```\n")
            return out

        step(1, "preflight: .env LLM_MODEL 누락", ["eval.memo_personas.preflight"], 1,
             ["❌ .env LLM_MODEL", "LLM_MODEL=..."], {"LLM_MODEL": ""})
        step(2, "preflight: DB 연결 실패", ["eval.memo_personas.preflight"], 1, ["❌ DB 연결", "docker compose"],
             {"DATABASE_URL": "postgresql+psycopg://postgres:wrong@127.0.0.1:1/nodb"})
        step(3, "export_evidence: DB 연결 실패", ["eval.memo_personas.export_evidence"], 1, ["DB에 연결하지 못했습니다"],
             {"DATABASE_URL": "postgresql+psycopg://postgres:wrong@127.0.0.1:1/nodb"})
        step(4, "preflight: 정상", ["eval.memo_personas.preflight"], 0, ["다음 명령: python -m eval.memo_personas.export_evidence"])
        step(5, "export_evidence: 정상", ["eval.memo_personas.export_evidence"], 0, ["저장 완료", "generate_memos --pilot"])
        step(6, "generate --pilot: 429·깨진 JSON·검사 실패 후 재생성, 6회 호출 뒤 강제 중단",
             ["eval.memo_personas.generate_memos", "--pilot"], 130,
             ["429", "JSON 파싱 실패", "검사 실패", "중간에 멈췄습니다"],
             {"MEMO_MOCK_SCENARIO": "rate_limit_once,broken_json_once,bad_memo_once,crash_after:6"})
        step(7, "generate --pilot: 재실행하면 이어서 완료", ["eval.memo_personas.generate_memos", "--pilot"], 0,
             ["완료 3명", "파일럿: 완료 10/10명", "summary.txt를 상규에게"])
        step(8, "generate --all: 일일 한도 도달 → 내일 안내", ["eval.memo_personas.generate_memos", "--all"], 2,
             ["내일 같은 명령을 다시 실행하세요"], {"MEMO_MOCK_SCENARIO": "daily_quota_after:15"})
        done = {f.stem for f in (REPO_ROOT / MEMOS / "persons").glob("*.json")}
        victim = next(f"P{i:03d}" for i in range(1, 101) if f"P{i:03d}" not in done)
        step(9, f"generate --all: {victim}만 계속 깨진 JSON → failed.jsonl 기록 후 계속",
             ["eval.memo_personas.generate_memos", "--all"], 0, ["실패 1명", "failed.jsonl"],
             {"MEMO_MOCK_SCENARIO": f"broken_json_always:{victim}"})
        failed_after_9 = [r["persona_id"] for r in read_jsonl(REPO_ROOT / MEMOS / "failed.jsonl")]
        step(10, "generate --all: 재실행하면 실패한 사람만 다시 시도", ["eval.memo_personas.generate_memos", "--all"], 0,
             ["이번에 할 사람 1명", "전체: 완료 100/100명, 실패 0명"])
        step(11, "report", ["eval.memo_personas.report"], 0, ["보고서 저장", "완료 100명 / 메모 1000개"])

        memos = read_jsonl(REPO_ROOT / MEMOS / "memos.jsonl")
        fields = ["memo_id", "persona_id", "slot", "target_company", "companies_mentioned", "sentence_type", "evidence_type",
                  "evidence_ids", "as_of_date", "memo_text", "memo_text_raw", "trigger", "answerability",
                  "expected_decision_draft", "generator_model", "review_status"]
        summary = (REPO_ROOT / MEMOS / "summary.txt").read_text(encoding="utf-8").splitlines()
        design = read_json(REPO_ROOT / MEMOS / "slot_design.json")
        people = {p["persona_id"]: p for p in read_jsonl(REPO_ROOT / "results/memo_personas/personas_100/personas.jsonl")}
        per_company = {}
        for m in memos:
            per_company[m["target_company"]] = per_company.get(m["target_company"], 0) + 1
        checks = [
            ("memos.jsonl 1,000개", len(memos) == 1000),
            ("memo_id 중복 없음", len({m["memo_id"] for m in memos}) == len(memos)),
            ("필드 모두 있음", all(all(f in m for f in fields) for m in memos)),
            ("기업별 250개", per_company == {c: 250 for c in per_company} and len(per_company) == 4),
            ("review_status 모두 pending", all(m["review_status"] == "pending" for m in memos)),
            ("9단계에서 failed.jsonl 기록", failed_after_9 == [victim]),
            ("마지막 failed.jsonl 비어 있음", read_jsonl(REPO_ROOT / MEMOS / "failed.jsonl") == []),
            ("summary.txt 20줄 이하", len(summary) <= 20),
            ("파일럿 10명: 기업 4곳 각 2명 이상·연령대 6개", len(design["pilot"]) == 10
             and min(Counter(people[x]["primary_company"] for x in design["pilot"]).values()) >= 2
             and len(Counter(people[x]["primary_company"] for x in design["pilot"])) == 4
             and len({people[x]["age_bucket"] for x in design["pilot"]}) == 6),
            ("복합 근거 ≥ 30%", design["summary"]["composite_share_of_tracking"] >= 0.30),
        ]
        log += ["", "## 결과물 확인", ""] + [f"- {'✅' if ok else '❌'} {name}" for name, ok in checks]
        ok_all &= all(ok for _, ok in checks)
        log += ["", f"임시 DB에 넣은 가짜 행: {seeded}", ""]
    finally:
        srv.cleanup()
    log += ["", "## 단계별 출력 (끝부분)", ""] + outputs
    (WORK / "e2e_log.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log[: log.index("## 단계별 출력 (끝부분)")]))
    print(f"\n자세한 출력: {WORK / 'e2e_log.md'}")
    print("✅ 전체 흐름 점검 통과" if ok_all else "❌ 전체 흐름 점검 실패")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
