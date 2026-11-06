"""페르소나 평가 메모(results/memo_personas/memos_direct/memos.jsonl)를
`pipelines.tracking.evaluate_llm`이 읽는 정답 형식(memo_eval_v0과 같은 모양)으로 바꾼다.

    python scripts/convert_memos_direct.py --sample 100 --seed 7
    PYTHONPATH=backend python -m pipelines.tracking.evaluate_llm --gold logs/memos_direct_gold.jsonl

바꾸는 규칙
- 종목: company_primary → 종목코드 (삼성전자 005930, SK하이닉스 000660, NAVER 035420, KB금융 105560)
- 판정: 추적 → normal, 일부 추적 → partial, 추적 안 함 → full_fallback, 확인 필요 → needs_confirmation
- 분류: intended_type을 그대로 category로 쓴다 (A1~A5, B1~B10, C1~C5)
- span: 본문에서 문장 글자 위치를 찾아 채운다 (평가기는 이 위치가 같은 문장끼리 비교한다).
  본문에서 문장을 못 찾는 메모는 통째로 빼고 개수를 알려 준다.

주의: 이 메모 정답에는 추적 항목 문구(items)와 합치기(merge_into)가 없다. 그래서 결과 요약의
`tracked_units_match`, `merge_accuracy`는 의미가 없고, 오류 목록에도 항목 개수 불일치가 섞인다.
`tracking_agreement`, `final_decision_accuracy`, `final_category_accuracy`, `missed_tracking`, `over_tracking`,
`needs_confirmation_rate`만 본다. 오류는 판정(decision)이 다른 것만 걸러서 보는 것을 권한다.
또 규칙 코드의 문장 분리(segment.py)가 정답과 다르게 자르는 문장(pipeline_issues.md의 70건 등)은
평가기가 짝을 못 찾아 점수에서 빠진다. 요약의 `sentences`는 정답 문장 수이고 실제로 점수에 쓰인 수는 아니다.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

SYMBOL = {"삼성전자": "005930", "SK하이닉스": "000660", "NAVER": "035420", "KB금융": "105560"}
DECISION = {"추적": "normal", "일부 추적": "partial", "추적 안 함": "full_fallback", "확인 필요": "needs_confirmation"}


def convert(rec: dict, text_field: str) -> tuple[dict | None, str]:
    """(변환된 메모, 건너뛴 이유). 변환되면 이유는 빈 문자열."""
    symbol = SYMBOL.get(rec.get("company_primary"))
    if not symbol:
        return None, "unknown_company"
    text = rec.get(text_field) or ""
    if not text.strip() or not rec.get("sentences"):
        return None, "empty"
    sentences, cursor = [], 0
    for idx, s in enumerate(rec["sentences"]):
        decision = DECISION.get(s.get("expected_decision"))
        if decision is None:
            return None, "unknown_decision"
        start = text.find(s["text"], cursor)
        if start < 0:
            return None, "sentence_not_in_text"
        end = start + len(s["text"])
        cursor = end
        sentences.append({
            "sentence_index": idx, "span": [start, end], "text": s["text"], "cleaned_text": s["text"], "flags": [],
            "decision": decision, "category": s.get("intended_type") or "-", "reason_code": None,
            "other_symbol": None, "resolved_reference": None, "items": [], "merge_into": None,
            "merge_update": None, "context_note": None, "suggestion": None,
        })
    return {"memo_id": rec["memo_id"], "persona": rec.get("persona_id"), "symbol": symbol, "text": text,
            "sentences": sentences}, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="페르소나 평가 메모 → evaluate_llm 정답 형식")
    ap.add_argument("--src", default="results/memo_personas/memos_direct/memos.jsonl")
    ap.add_argument("--out", default="logs/memos_direct_gold.jsonl")
    ap.add_argument("--text-field", choices=["memo_body_clean", "memo_body"], default="memo_body_clean",
                    help="평가에 넣을 본문. memo_body는 오타가 들어간 원문이라 문장 위치를 못 찾는 메모가 늘 수 있다")
    ap.add_argument("--sample", type=int, default=0, help="무작위로 N개만 (0이면 전부)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    src = Path(args.src)
    records = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    converted, skipped = [], {}
    for rec in records:
        memo, why = convert(rec, args.text_field)
        if memo is None:
            skipped[why] = skipped.get(why, 0) + 1
        else:
            converted.append(memo)
    if args.sample and args.sample < len(converted):
        converted = sorted(random.Random(args.seed).sample(converted, args.sample), key=lambda m: m["memo_id"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in converted), encoding="utf-8")
    print(f"원본 {len(records)}개 → 변환 {len(converted)}개 · 건너뜀 {skipped or 0} · 결과: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())