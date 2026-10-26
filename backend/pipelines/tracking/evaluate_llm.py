"""문장 판정 LLM 단계 평가: 로직 판정 → 남은 문장을 메모당 1회 LLM 판정 → 최종 결과를 정답과 비교.

    PYTHONPATH=backend python -m pipelines.tracking.evaluate_llm --limit 3      # 메모 3개만 (호출 3회 이하)
    PYTHONPATH=backend python -m pipelines.tracking.evaluate_llm                # 35개 전체

외부 API(Gemini)를 호출한다. 실행 전에 사용자 승인을 받는다. API 키는 출력하지 않는다.

지표 (최종 판정 기준)
- 추적 여부 일치(추적/안 함/확인 필요 3분류, normal·partial은 같은 "추적"), 판정·분류 정확도, 추적 의도 놓침(정답 normal·partial → 최종 full_fallback), 과잉 추적, 확인 필요 비율
- 추적 단위 수 일치: 정답 문장의 항목 수(합치기면 0)와 최종 항목 수가 같은 비율
- 합치기: 정답이 앞 문장에 합치는 문장을 같은 문장에 합친 비율
- 비용·속도: LLM 호출 수, 호출당 지연시간(평균·p50·p95), 입력·출력 토큰(평균·합계)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, median

from ..common.config import REPO_ROOT, resolve_path
from .evaluate import TRACKED, load_gold
from .judge import judge_memo
from .lexicon import DEFAULT_PATH, load_lexicon
from .llm import judge_with_llm


def _ratio(num, den):
    return round(num / den, 4) if den else None


def _p95(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))] if ordered else None


def _bucket(decision: str) -> str:
    return "tracked" if decision in TRACKED else decision


def _units(sentence: dict) -> int:
    return 0 if sentence.get("merge_into") else len(sentence.get("items") or [])


def evaluate_llm(gold: list[dict], lex, call, sleep: float = 0.0) -> dict:
    c = {k: 0 for k in ("sentences", "aligned", "tracking_ok", "decision_ok", "category_scored", "category_ok", "missed", "over",
                        "confirm", "tracked_gold", "units_ok", "merge_gold", "merge_ok", "llm_judged", "memos_called")}
    rows, errors = [], []
    for memo in gold:
        judged = judge_memo(memo["text"], memo["symbol"], lex)
        pending_before = sum(j.decision == "pending_llm" for j in judged)
        if pending_before and call is not None:
            c["memos_called"] += 1
            judge_with_llm(judged, memo["symbol"], lex.stock_names.get(memo["symbol"], memo["symbol"]), call)
            if sleep:
                time.sleep(sleep)
        by_span = {tuple(j.span): j for j in judged}
        rows.append({"memo_id": memo["memo_id"], "text": memo["text"], "pred": [j.to_dict() for j in judged]})
        for g in memo["sentences"]:
            c["sentences"] += 1
            p = by_span.get(tuple(g["span"]))
            if p is None:
                continue
            c["aligned"] += 1
            c["llm_judged"] += p.judged_by == "llm"
            ok = p.decision == g["decision"]
            c["decision_ok"] += ok
            c["tracking_ok"] += _bucket(p.decision) == _bucket(g["decision"])
            if g["category"] != "-" and p.category:
                c["category_scored"] += 1
                c["category_ok"] += p.category == g["category"]
            c["missed"] += g["decision"] in TRACKED and p.decision == "full_fallback"
            c["over"] += g["decision"] == "full_fallback" and p.decision in TRACKED
            c["confirm"] += p.decision == "needs_confirmation"
            pred_units = 0 if p.merge_into else len(p.items)
            if g["decision"] in TRACKED:
                c["tracked_gold"] += 1
                c["units_ok"] += pred_units == _units(g)
            if g.get("merge_into"):
                c["merge_gold"] += 1
                c["merge_ok"] += bool(p.merge_into) and p.merge_into["sentence_index"] == g["merge_into"]["sentence_index"]
            if not ok or (g["decision"] in TRACKED and pred_units != _units(g)):
                errors.append({
                    "memo_id": memo["memo_id"], "sentence_index": g["sentence_index"], "text": g["text"],
                    "gold": {"decision": g["decision"], "category": g["category"],
                             "items": [it["description"] for it in g["items"]], "merge_into": g.get("merge_into")},
                    "pred": {"decision": p.decision, "category": p.category, "judged_by": p.judged_by,
                             "items": [it["description"] for it in p.items], "merge_into": p.merge_into,
                             "confidence": p.confidence},
                })
    summary = {
        "memos": len(gold), "sentences": c["sentences"], "llm_called_memos": c["memos_called"],
        "llm_judged_sentences": c["llm_judged"],
        "tracking_agreement": _ratio(c["tracking_ok"], c["aligned"]),
        "final_decision_accuracy": _ratio(c["decision_ok"], c["aligned"]),
        "final_category_accuracy": _ratio(c["category_ok"], c["category_scored"]),
        "missed_tracking": c["missed"], "over_tracking": c["over"],
        "needs_confirmation_rate": _ratio(c["confirm"], c["aligned"]),
        "tracked_units_match": _ratio(c["units_ok"], c["tracked_gold"]),
        "merge_accuracy": _ratio(c["merge_ok"], c["merge_gold"]),
    }
    return {"summary": summary, "counts": c, "errors": errors, "predictions": rows}


def call_stats(calls) -> dict:
    ok = [r for r in calls if r.ok]
    lat = [r.latency_ms for r in ok]
    pin = [r.prompt_tokens for r in ok if r.prompt_tokens is not None]
    pout = [r.output_tokens for r in ok if r.output_tokens is not None]
    return {
        "calls": len(calls), "failed": len(calls) - len(ok),
        "latency_ms_mean": round(mean(lat), 1) if lat else None,
        "latency_ms_p50": round(median(lat), 1) if lat else None,
        "latency_ms_p95": round(_p95(lat), 1) if lat else None,
        "prompt_tokens_mean": round(mean(pin), 1) if pin else None,
        "output_tokens_mean": round(mean(pout), 1) if pout else None,
        "prompt_tokens_total": sum(pin), "output_tokens_total": sum(pout),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="메모 문장 판정 LLM 단계 평가 (Gemini 실호출)")
    ap.add_argument("--gold", default="eval/memo_eval_v0/memo_eval_v0.jsonl")
    ap.add_argument("--lexicon", default=DEFAULT_PATH)
    ap.add_argument("--model", default=None, help="기본: .env LLM_MODEL")
    ap.add_argument("--limit", type=int, default=None, help="앞에서부터 메모 N개만")
    ap.add_argument("--memos", default=None, help="이 메모만 (쉼표 구분, 예: M08,M09)")
    ap.add_argument("--sleep", type=float, default=1.0, help="호출 사이 대기(초), 무료 쿼터 보호")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from .gemini import GeminiClient

    gold = load_gold(resolve_path(args.gold))[: args.limit]
    if args.memos:
        wanted = set(args.memos.split(","))
        gold = [m for m in gold if m["memo_id"] in wanted]
    client = GeminiClient.from_env(args.model)
    print(f"모델 {client.model} · 메모 {len(gold)}개", file=sys.stderr)
    result = evaluate_llm(gold, load_lexicon(args.lexicon), client, sleep=args.sleep)
    result["calls"] = call_stats(client.calls)
    result["model"] = client.model
    out = Path(args.out) if args.out else REPO_ROOT / "logs" / f"tracking_eval_llm_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({**result["summary"], **result["calls"]}, ensure_ascii=False, indent=1))
    print(f"오류 {len(result['errors'])}건 · 결과: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
