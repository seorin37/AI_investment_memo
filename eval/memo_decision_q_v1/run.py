"""매수·예측 질문 평가 (2026-11-22, docs/memo-decision-question-design.md).

메모 한 줄씩 서비스와 같은 분석 함수(app.board.analysis.analyze_memo)로 판정만 한다. DB 쓰기 없음, 카드 생성 없음.
결과: ask(한 번 답하기) · track(추적 항목) · confirm(확인 질문) · drop(아무것도 안 함)

    PYTHONPATH=backend python eval/memo_decision_q_v1/run.py --prompt configs/tracking_judge_prompt_intent.md --out results/base.json
    PYTHONPATH=backend python eval/memo_decision_q_v1/run.py --prompt configs/tracking_judge_prompt_intent_v2.md --out results/v2.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"


def outcome(res) -> str:
    if res.questions:
        return "ask"
    if res.items:
        return "track"
    if res.confirmations:
        return "confirm"
    return "drop"


def passed(expect: str, got: str) -> bool:
    if expect == "ask":
        return got == "ask"
    if expect == "track":
        return got in ("track", "confirm")      # 가격 조건 확인 질문도 추적으로 가는 길
    return got == "drop"


def run_one(case: dict, llm) -> dict:
    from app.board.analysis import analyze_memo
    try:
        res = analyze_memo(0, 1, case["text"], case["symbol"], case["company"], llm, [])
    except Exception as exc:                     # LLM 실패는 결과에 남긴다
        return {**case, "got": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    got = outcome(res)
    return {**case, "got": got, "ok": passed(case["expect"], got),
            "asks": [q.get("question") for q in res.questions],
            "items": [i.get("description") for i in res.items],
            "confirm": [c.get("question") for c in res.confirmations]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cases", default=str(CASES), help="평가 세트 (기본 cases.jsonl, 예시와 다르게 쓴 문장은 cases_holdout.jsonl)")
    args = ap.parse_args()
    os.environ["TRACKING_PROMPT_PATH"] = args.prompt
    from app.board.analysis import default_llm
    llm = default_llm()
    if llm is None:
        raise SystemExit("LLM 키가 없습니다")
    cases = [json.loads(l) for l in Path(args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda c: run_one(c, llm), cases))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"prompt": args.prompt, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    by = Counter()
    for r in rows:
        by[(r["group"], r["ok"])] += 1
    groups = sorted({r["group"] for r in rows})
    print(f"prompt={args.prompt}  통과 {sum(r['ok'] for r in rows)}/{len(rows)}")
    for g in groups:
        print(f"  {g:8s} {by[(g, True)]}/{by[(g, True)] + by[(g, False)]}")


if __name__ == "__main__":
    main()
