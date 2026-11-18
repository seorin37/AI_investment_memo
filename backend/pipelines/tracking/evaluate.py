"""문장 판정 평가: 정답 메모(jsonl)와 로직 판정 결과를 비교한다. DB·GPU·외부 API 없음.

    PYTHONPATH=backend python -m pipelines.tracking.evaluate --gold eval/memo_eval_v0/memo_eval_v0.jsonl

지표
- 문장 분리: 정답과 span이 같은 문장 비율, 메모 전체가 같게 나뉜 비율
- 한 줄 분리: 모든 메모를 줄바꿈·끝 문장부호 없이 한 줄로 이어 붙였을 때도 정답 문장대로 나뉘는 비율
- 한 줄 안전: 그렇게 이어 붙였을 때 로직이 추적 문장(정답 normal·partial)을 버린 수 (0이어야 함)
- 로직 처리 비율: LLM으로 넘기지 않고 로직이 판정한 문장 비율 (LLM 비용 지표)
- 로직 판정 정확도: 로직이 판정한 문장 중 판정(decision)·분류(category)가 정답과 같은 비율
- 추적 의도 놓침: 정답이 normal·partial인데 로직이 full_fallback으로 버린 문장 (0이어야 함)
- 가격 조건: 정답 가격 항목을 같은 유형·같은 가격으로 찾은 비율, 정답에 없는 가격 항목 수
- 정제: 정답 flags·정제본이 같은 비율, 개인정보 가림 재현율
- 다른 종목: 정답 other_symbol을 찾은 비율
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from ..common.config import REPO_ROOT, resolve_path
from .judge import PENDING, judge_memo
from .segment import split_sentences
from .lexicon import DEFAULT_PATH, load_lexicon

TRACKED = {"normal", "partial"}
# 정제 결과로 채점하는 flags. no_domain·spam_suspect 같은 판정 표시는 채점하지 않는다
CLEAN_FLAGS = {"profanity", "vocative", "pii_masked"}


def load_gold(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _price_items(items: list[dict]) -> set[tuple[str, int]]:
    return {(it["type"], it["price_threshold"]) for it in items if it["type"].startswith("price_")}


def flat_segmentation(gold: list[dict], lex) -> tuple[int, int, int, int]:
    """모든 메모를 한 줄로 이어 붙여(줄바꿈 → 공백, 문장 끝 . ? ! 제거) 분리했을 때 정답 문장 수와 일치하는지."""
    memo_ok = sent_ok = sent_total = 0
    for memo in gold:
        expected = [s["text"].rstrip(".?!") for s in memo["sentences"]]
        got = [seg.text for seg in split_sentences(" ".join(expected), lex)]
        memo_ok += got == expected
        sent_ok += len(set(got) & set(expected))
        sent_total += len(expected)
    return memo_ok, len(gold), sent_ok, sent_total


def flat_safety(gold: list[dict], lex) -> tuple[int, int]:
    """한 줄로 이어 붙인 메모에서, 추적 문장이 들어 있는 조각을 로직이 완전 폴백으로 버린 수."""
    lost = total = 0
    for memo in gold:
        flat = " ".join(s["text"].rstrip(".?!") for s in memo["sentences"])
        judged = judge_memo(flat, memo["symbol"], lex)
        for g in memo["sentences"]:
            if g["decision"] not in TRACKED:
                continue
            total += 1
            key = g["text"].rstrip(".?!")
            owners = [j for j in judged if key in j.text or j.text in key]
            lost += all(j.decision == "full_fallback" for j in owners)
    return lost, total


def evaluate(gold: list[dict], lex) -> dict:
    c = {k: 0 for k in (
        "sentences", "seg_match", "memos_seg_exact", "rule_judged", "rule_decision_ok", "rule_category_scored",
        "rule_category_ok", "missed_tracking", "over_tracking", "gold_price", "price_found", "price_extra",
        "flag_gold", "flag_ok", "cleaned_ok", "pii_gold", "pii_found", "flag_false", "other_gold", "other_found",
    )}
    errors: list[dict] = []
    for memo in gold:
        preds = judge_memo(memo["text"], memo["symbol"], lex)
        by_span = {tuple(p.span): p for p in preds}
        gold_spans = [tuple(s["span"]) for s in memo["sentences"]]
        if gold_spans == [tuple(p.span) for p in preds]:
            c["memos_seg_exact"] += 1
        for g in memo["sentences"]:
            c["sentences"] += 1
            p = by_span.get(tuple(g["span"]))
            if p is None:
                errors.append({"memo_id": memo["memo_id"], "sentence_index": g["sentence_index"], "text": g["text"],
                               "kind": "segmentation", "gold": g["span"], "pred": None})
                continue
            c["seg_match"] += 1

            # 정제
            pred_flags = sorted(f for f in p.flags if f in CLEAN_FLAGS)
            if g["flags"]:
                c["flag_gold"] += 1
                c["flag_ok"] += sorted(g["flags"]) == pred_flags
                c["cleaned_ok"] += g["cleaned_text"] == p.cleaned_text
            elif pred_flags:
                c["flag_false"] += 1
                errors.append({"memo_id": memo["memo_id"], "sentence_index": g["sentence_index"], "text": g["text"],
                               "kind": "false_flag", "gold": [], "pred": pred_flags})
            if "pii_masked" in g["flags"]:
                c["pii_gold"] += 1
                c["pii_found"] += "pii_masked" in p.flags

            # 다른 종목
            if g["other_symbol"]:
                c["other_gold"] += 1
                c["other_found"] += p.other_symbol == g["other_symbol"]

            # 가격 조건 (로직 담당)
            gold_price = _price_items(g["items"])
            pred_price = _price_items(p.items)
            c["gold_price"] += len(gold_price)
            c["price_found"] += len(gold_price & pred_price)
            c["price_extra"] += len(pred_price - gold_price)

            # 로직 판정
            if p.decision == PENDING:
                continue
            c["rule_judged"] += 1
            ok = p.decision == g["decision"]
            c["rule_decision_ok"] += ok
            if g["category"] != "-" and p.category is not None:
                c["rule_category_scored"] += 1
                c["rule_category_ok"] += p.category == g["category"]
            if g["decision"] in TRACKED and p.decision == "full_fallback":
                c["missed_tracking"] += 1
            if g["decision"] == "full_fallback" and p.decision in TRACKED:
                c["over_tracking"] += 1
            if not ok or (gold_price != pred_price):
                errors.append({"memo_id": memo["memo_id"], "sentence_index": g["sentence_index"], "text": g["text"],
                               "kind": "rule_judgment",
                               "gold": {"decision": g["decision"], "category": g["category"], "price": sorted(gold_price)},
                               "pred": {"decision": p.decision, "category": p.category, "price": sorted(pred_price)}})
    flat_memo_ok, flat_memos, flat_sent_ok, flat_sents = flat_segmentation(gold, lex)
    flat_lost, flat_tracked = flat_safety(gold, lex)
    summary = {
        "memos": len(gold),
        "sentences": c["sentences"],
        "segmentation_sentence_match": _ratio(c["seg_match"], c["sentences"]),
        "segmentation_memo_exact": _ratio(c["memos_seg_exact"], len(gold)),
        "flat_segmentation_sentence_match": _ratio(flat_sent_ok, flat_sents),
        "flat_segmentation_memo_exact": _ratio(flat_memo_ok, flat_memos),
        "flat_missed_tracking": flat_lost,
        "flat_tracked_sentences": flat_tracked,
        "rule_coverage": _ratio(c["rule_judged"], c["seg_match"]),
        "rule_decision_accuracy": _ratio(c["rule_decision_ok"], c["rule_judged"]),
        "rule_category_accuracy": _ratio(c["rule_category_ok"], c["rule_category_scored"]),
        "missed_tracking": c["missed_tracking"],
        "over_tracking": c["over_tracking"],
        "price_recall": _ratio(c["price_found"], c["gold_price"]),
        "price_extra": c["price_extra"],
        "clean_flags_accuracy": _ratio(c["flag_ok"], c["flag_gold"]),
        "clean_text_accuracy": _ratio(c["cleaned_ok"], c["flag_gold"]),
        "pii_recall": _ratio(c["pii_found"], c["pii_gold"]),
        "false_flags": c["flag_false"],
        "other_symbol_recall": _ratio(c["other_found"], c["other_gold"]),
        "pending_llm": c["seg_match"] - c["rule_judged"],
    }
    return {"summary": summary, "counts": c, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="메모 문장 판정 평가 (로직 단계)")
    ap.add_argument("--gold", default="eval/memo_eval_v0/memo_eval_v0.jsonl")
    ap.add_argument("--lexicon", default=DEFAULT_PATH)
    ap.add_argument("--out", default=None, help="결과 JSON 경로 (기본: logs/tracking_eval_<시각>.json)")
    args = ap.parse_args(argv)

    result = evaluate(load_gold(resolve_path(args.gold)), load_lexicon(args.lexicon))
    result["gold"] = args.gold
    out = Path(args.out) if args.out else REPO_ROOT / "logs" / f"tracking_eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    print(f"오류 {len(result['errors'])}건 · 결과: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
