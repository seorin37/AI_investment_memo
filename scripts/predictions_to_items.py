"""판정 평가 로그(logs/tracking_eval_llm_*.json)의 예측을 updates 실험이 읽는 정답 형식으로 바꾼다.

    python scripts/predictions_to_items.py --log logs/tracking_eval_llm_20261103_163604.json
    PYTHONPATH=backend python -m pipelines.updates.experiment --llm none --gold logs/memos_direct_items.jsonl

흐름: 사용자 메모(memos.jsonl) → 판정 단계(evaluate_llm)가 문장별 판정·추적 항목을 뽑음 → 이 스크립트가
`eval/memo_eval_v0`와 같은 모양(메모마다 sentences[].decision / category / items / merge_into)으로 저장.

- 항목(items)은 GPT가 뽑은 예측이다. 사람이 확인한 정답이 아니므로, 이 파일로 만든 카드는 "판정 단계 출력 기준"이다.
- 메모 단위 필드(persona, symbol)는 --base(기본 logs/memos_direct_gold.jsonl)에서 가져온다. 없으면 문장의 symbols[0]을 쓴다.
- 이 스크립트는 파일만 읽고 쓴다. DB·API 호출이 없다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SENTENCE_KEYS = ("sentence_index", "span", "text", "cleaned_text", "flags", "decision", "category", "reason_code",
                 "other_symbol", "resolved_reference", "items", "merge_into", "merge_update", "context_note",
                 "suggestion")


def convert_sentence(s: dict, idx: int) -> dict:
    out = {k: s.get(k) for k in SENTENCE_KEYS}
    out["sentence_index"] = s.get("sentence_index", idx)
    out["cleaned_text"] = s.get("cleaned_text") or s.get("text")
    out["flags"] = s.get("flags") or []
    out["items"] = s.get("items") or []
    return out


def convert(entry: dict, base: dict | None) -> tuple[dict | None, str]:
    """(변환된 메모, 건너뛴 이유)."""
    sents = entry.get("pred") or []
    if not sents:
        return None, "no_pred"
    symbol = (base or {}).get("symbol")
    if not symbol:
        syms = sents[0].get("symbols") or []
        symbol = syms[0] if syms else None
    if not symbol:
        return None, "no_symbol"
    return {"memo_id": entry["memo_id"], "persona": (base or {}).get("persona"), "symbol": symbol,
            "text": entry.get("text") or (base or {}).get("text", ""),
            "sentences": [convert_sentence(s, i) for i, s in enumerate(sents)]}, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="판정 평가 예측 → updates 실험 입력(정답 형식)")
    ap.add_argument("--log", required=True, help="logs/tracking_eval_llm_*.json")
    ap.add_argument("--base", default="logs/memos_direct_gold.jsonl",
                    help="persona·symbol을 가져올 정답 형식 파일(없으면 문장의 symbols를 씀)")
    ap.add_argument("--out", default="logs/memos_direct_items.jsonl")
    ap.add_argument("--only-with-items", action="store_true", help="추적 항목이 하나라도 있는 메모만")
    args = ap.parse_args(argv)

    log = json.loads(Path(args.log).read_text(encoding="utf-8"))
    preds = log.get("predictions") or []
    base = {}
    base_path = Path(args.base)
    if base_path.exists():
        for line in base_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                base[rec["memo_id"]] = rec

    converted, skipped = [], {}
    for entry in preds:
        memo, why = convert(entry, base.get(entry["memo_id"]))
        if memo is None:
            skipped[why] = skipped.get(why, 0) + 1
        elif args.only_with_items and not any(s["items"] for s in memo["sentences"]):
            skipped["no_items"] = skipped.get("no_items", 0) + 1
        else:
            converted.append(memo)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in converted), encoding="utf-8")
    n_items = sum(len(s["items"]) for m in converted for s in m["sentences"])
    by_type = {}
    for m in converted:
        for s in m["sentences"]:
            for it in s["items"]:
                by_type[it.get("type")] = by_type.get(it.get("type"), 0) + 1
    print(f"예측 {len(preds)}개 → 변환 {len(converted)}개 · 추적 항목 {n_items}개 {by_type} · 건너뜀 {skipped or 0} · 결과: {out}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())