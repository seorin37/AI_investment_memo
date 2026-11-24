"""memo_intent_eval_v1을 현재 메모 분석 코드로 실행한다.

검색·카드 생성·DB 쓰기는 하지 않는다. 규칙 판정 후 pending 문장만 기존 LLM 판정기로 보낸다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pipelines.tracking.judge import PENDING, judge_memo
from pipelines.tracking.lexicon import load_lexicon
from pipelines.tracking.llm import judge_with_llm
from pipelines.tracking.openai_client import OpenAIClient, usage_totals


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = Path(__file__).with_name("cases.jsonl")


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def owner(expected: dict, predictions: list[dict]) -> dict | None:
    exact = next((p for p in predictions if p["text"].strip() == expected["text"].strip()), None)
    if exact:
        return exact
    return max(predictions, key=lambda p: len(set(p["text"]) & set(expected["text"])), default=None)


def is_tracking(pred: dict | None) -> bool:
    return bool(pred and pred["decision"] in ("normal", "partial") and (pred["items"] or pred["merge_into"]))


def score_case(case: dict, predictions: list[dict]) -> tuple[list[dict], dict]:
    rows = []
    counts = {"intents": 0, "tracking_expected": 0, "tracking_correct": 0, "over_tracking": 0,
              "missed_tracking": 0, "type_checked": 0, "type_correct": 0, "price_checked": 0, "price_correct": 0}
    for expected in case["expected_intents"]:
        pred = owner(expected, predictions)
        want = bool(expected["create_tracking"])
        got = is_tracking(pred)
        counts["intents"] += 1
        counts["tracking_expected"] += want
        counts["tracking_correct"] += want == got
        counts["over_tracking"] += not want and got
        counts["missed_tracking"] += want and not got
        tracking = expected.get("tracking") or {}
        predicted_items = (pred or {}).get("items") or []
        if want and tracking.get("type"):
            counts["type_checked"] += 1
            counts["type_correct"] += any(i.get("type") == tracking["type"] for i in predicted_items)
        if want and tracking.get("price_threshold") is not None:
            counts["price_checked"] += 1
            counts["price_correct"] += any(i.get("price_threshold") == tracking["price_threshold"] for i in predicted_items)
        rows.append({"expected": expected, "prediction": pred, "tracking_expected": want, "tracking_predicted": got})
    return rows, counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(DEFAULT_CASES))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model")
    ap.add_argument("--out-dir", default="results/tracking_intent_eval")
    args = ap.parse_args()

    cases = load_cases(Path(args.cases))
    if args.limit:
        cases = cases[:args.limit]
    lex = load_lexicon()
    client = OpenAIClient.from_env(args.model)
    client.response_format = None
    raw_responses: list[str] = []

    def call(prompt: str) -> str:
        raw = client(prompt)
        raw_responses.append(raw)
        return raw

    totals = {"memos": len(cases), "llm_memos": 0, "intents": 0, "tracking_expected": 0,
              "tracking_correct": 0, "over_tracking": 0, "missed_tracking": 0,
              "type_checked": 0, "type_correct": 0, "price_checked": 0, "price_correct": 0}
    outputs = []
    for case in cases:
        judged = judge_memo(case["text"], case["symbol"], lex)
        pending = any(j.decision == PENDING for j in judged)
        if pending:
            totals["llm_memos"] += 1
            judge_with_llm(judged, case["symbol"], case["company"], call)
        predictions = [j.to_dict() for j in judged]
        intent_rows, counts = score_case(case, predictions)
        for key, value in counts.items():
            totals[key] += value
        outputs.append({"memo_id": case["memo_id"], "symbol": case["symbol"], "text": case["text"],
                        "intents": intent_rows, "predictions": predictions,
                        "forbidden": case.get("forbidden") or [], "merge_policy": case.get("merge_policy") or {}})

    totals["tracking_accuracy"] = round(totals["tracking_correct"] / totals["intents"], 4) if totals["intents"] else None
    totals["type_accuracy"] = round(totals["type_correct"] / totals["type_checked"], 4) if totals["type_checked"] else None
    totals["price_accuracy"] = round(totals["price_correct"] / totals["price_checked"], 4) if totals["price_checked"] else None
    totals.update({"model": client.model, **usage_totals(client.calls)})

    run_dir = ROOT / args.out_dir / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(totals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False))
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
