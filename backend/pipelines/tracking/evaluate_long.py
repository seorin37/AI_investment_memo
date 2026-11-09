"""memos_long 메모 분석 평가 (긴 메모 300개, 문장 라벨 비교). 결과는 파일로만, DB는 stocks 이름→코드 조회만 (읽기 전용).

    PYTHONPATH=backend python -m pipelines.tracking.evaluate_long estimate                  # LLM 없이 로직 판정 + 프롬프트 크기
    PYTHONPATH=backend python -m pipelines.tracking.evaluate_long run --max-usd 2.8         # LLM 포함 (메모당 최대 1회)
    PYTHONPATH=backend python -m pipelines.tracking.evaluate_long rescore --from <이전 결과 폴더>   # LLM 없이 다시 채점

2026-11-09: results/tracking_eval/…/long_eval.py(저장소 밖 스크래치)를 옮겼다. 바뀐 점:
- judgments.jsonl: 메모마다 판정한 문장 조각을 '모두' 저장한다 (위치 span·판정·항목·판정 주체).
  전에는 정답 문장마다 가장 많이 겹친 조각 하나만 sentences.jsonl에 남아, 정답을 고친 세트(memos_long_v2)로 다시 채점할 때
  새 정답 문장과 겹치는 다른 조각의 판정이 없었다 (P067-L2 앞 조각).
- sentences.jsonl의 fragments: 정답 문장과 겹치는 조각 전부 (겹친 글자 수 포함). 채점은 전과 같이 가장 많이 겹친 조각으로 한다.
- rescore: judgments.jsonl만으로 다른 정답 세트에 다시 맞춰 채점한다 (LLM·DB 없음).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from ..common.config import REPO_ROOT
from ..updates.eval_e2e import GOLD_DECISION, load_memos, score_analysis, span_mapper

DEFAULT_MEMOS = "results/memo_personas/memos_long_v2"
JUDGMENT_FIELDS = ("sentence_index", "text", "span", "cleaned_text", "decision", "category", "reason_code", "items",
                   "merge_into", "judged_by", "confidence", "sub_sentences", "other_symbol")


def fragment(d: dict) -> SimpleNamespace:
    """저장한 판정 dict → align이 쓰는 모양 (span, sentence_index, to_dict)."""
    return SimpleNamespace(span=tuple(d["span"]), sentence_index=d["sentence_index"], to_dict=lambda d=d: dict(d))


def align_memo(memo: dict, judged: list) -> list[dict]:
    """정답 문장마다: 겹치는 조각 전부(fragments)와 가장 많이 겹친 조각(best), 문장 분리 상태(segmentation).
    정답 문장은 오타를 고친 memo_body_clean에서 찾고 위치를 판정한 원문(memo_body) 위치로 옮긴다."""
    clean, raw = memo.get("memo_body_clean") or memo["memo_body"], memo["memo_body"]
    conv = span_mapper(clean, raw)
    out, cursor = [], 0
    for g in memo["sentences"]:
        s = clean.find(g["text"], cursor)
        if s < 0:
            s = clean.find(g["text"])
        if s < 0:
            out.append({"gold": g, "best": None, "fragments": [], "span": None, "segmentation": "not_found"})
            continue
        cursor = s + len(g["text"])
        a, b = conv(s), conv(cursor)
        frags = []
        for p in judged:
            o = min(b, p.span[1]) - max(a, p.span[0])
            if o > 0:
                frags.append((o, p))
        best = max(frags, key=lambda x: x[0], default=(0, None))
        seg = "ok"
        if best[1] is not None:
            plen, glen = best[1].span[1] - best[1].span[0], b - a
            if best[0] < 0.8 * glen:
                seg = "gold_split"          # 정답 문장 하나가 판정 조각 여러 개로 나뉨
            elif plen > 1.25 * glen + 2:
                seg = "pred_merged"         # 판정 조각 하나가 정답 문장 여러 개를 품음
        out.append({"gold": g, "best": best[1], "span": (a, b), "segmentation": seg,
                    "fragments": [{**{k: p.to_dict().get(k) for k in ("sentence_index", "text", "span", "decision",
                                                                       "category", "judged_by")}, "overlap": o}
                                  for o, p in frags]})
    return out


def sentence_records(memo: dict, symbol: str, judged: list, llm_error: str | None, logic: dict[int, str]) -> list[dict]:
    recs = []
    for a in align_memo(memo, judged):
        g, p = a["gold"], a["best"]
        pd = None if p is None else p.to_dict()
        recs.append({"memo_id": memo["memo_id"], "company": memo.get("company_primary"), "symbol": symbol,
                     "gold_text": g["text"], "gold_type": g["intended_type"], "gold": g["expected_decision"],
                     "gold_code": GOLD_DECISION.get(g["expected_decision"], "needs_confirmation"),
                     "pred": None if pd is None else pd["decision"], "pred_text": None if pd is None else pd["text"],
                     "pred_category": None if pd is None else pd.get("category"),
                     "judged_by": None if pd is None else pd.get("judged_by"),
                     "logic_decision": None if p is None else logic.get(p.sentence_index),
                     "segmentation": a["segmentation"], "fragments": a["fragments"], "llm_error": llm_error,
                     "pred_sentences": len(judged), "gold_sentences": len(memo["sentences"]),
                     "typo": memo["memo_body"] != memo.get("memo_body_clean", memo["memo_body"]),
                     "_pred": pd})
    return recs


def judgment_record(memo: dict, symbol: str, judged: list, logic: dict[int, str], llm_error: str | None) -> dict:
    return {"memo_id": memo["memo_id"], "symbol": symbol, "company": memo.get("company_primary"),
            "memo_body": memo["memo_body"], "llm_error": llm_error,
            "judged": [{**{k: j.to_dict().get(k) for k in JUDGMENT_FIELDS}, "logic_decision": logic.get(j.sentence_index)}
                       for j in judged]}


def write_out(out: Path, recs: list[dict], judgments: list[dict] | None, summary: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "sentences.jsonl").open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps({k: v for k, v in r.items() if k != "_pred"}, ensure_ascii=False) + "\n")
    if judgments is not None:
        with (out / "judgments.jsonl").open("w", encoding="utf-8") as f:
            for j in judgments:
                f.write(json.dumps(j, ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


def score(recs: list[dict]) -> dict:
    return {"score": score_analysis([{"gold": {"expected_decision": r["gold"], "intended_type": r["gold_type"]},
                                      "pred": r["_pred"]} for r in recs]),
            "segmentation": dict(Counter(r["segmentation"] for r in recs)),
            "no_judgment": sum(r["pred"] is None for r in recs)}


def rescore(memos: list[dict], judgments_path: Path) -> tuple[list[dict], dict]:
    """judgments.jsonl(이전 실행)의 조각 판정을 memos의 정답 문장에 다시 맞춘다. 반환: (문장 기록, 빠진 메모 수 등)."""
    saved = {}
    for line in judgments_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            j = json.loads(line)
            saved[j["memo_id"]] = j
    recs, missing, body_changed = [], [], []
    for m in memos:
        j = saved.get(m["memo_id"])
        if j is None:
            missing.append(m["memo_id"])
            continue
        if j["memo_body"] != m["memo_body"]:                    # 원문이 바뀌면 조각 위치가 맞지 않는다: 채점하지 않는다
            body_changed.append(m["memo_id"])
            continue
        frags = [fragment(d) for d in j["judged"]]
        logic = {d["sentence_index"]: d.get("logic_decision") for d in j["judged"]}
        recs += sentence_records(m, j["symbol"], frags, j.get("llm_error"), logic)
    return recs, {"memos_missing": missing, "memo_body_changed": body_changed}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="memos_long 메모 분석 평가 (결과는 파일로만)")
    ap.add_argument("mode", choices=["estimate", "run", "rescore"])
    ap.add_argument("--memos", default=DEFAULT_MEMOS, help="정답 세트 (폴더면 batch_*.jsonl)")
    ap.add_argument("--from", dest="src", help="rescore: 이전 결과 폴더 (judgments.jsonl)")
    ap.add_argument("--out", help="결과 폴더 (기본: results/tracking_eval/<세트>_<시각>)")
    ap.add_argument("--limit", type=int, help="앞에서 N개 메모만 (시험용)")
    ap.add_argument("--max-usd", type=float, default=2.8, help="run: 누적 비용이 이 값을 넘으면 멈춘다")
    args = ap.parse_args(argv)

    memos = load_memos(args.memos)[:args.limit or None]
    out = Path(args.out) if args.out else (REPO_ROOT / "results/tracking_eval"
                                           / f"{Path(args.memos).name}_{args.mode}_{datetime.now():%Y%m%d_%H%M%S}")
    if args.mode == "rescore":
        if not args.src:
            ap.error("rescore에는 --from이 필요합니다")
        recs, info = rescore(memos, Path(args.src) / "judgments.jsonl")
        summary = {"mode": "rescore", "memos": args.memos, "from": args.src, **score(recs), **info}
        write_out(out, recs, None, summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "score"}, ensure_ascii=False))
        print("점수:", json.dumps(summary["score"], ensure_ascii=False))
        print(f"결과: {out}")
        return 0

    import psycopg

    from ..common.db import get_read_dsn
    from ..updates.relevance_compare import PRICES
    from .judge import PENDING, judge_memo
    from .lexicon import load_lexicon
    from .llm import build_prompt, judge_with_llm

    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        by_name = {n.strip(): s.strip() for n, s in conn.execute("SELECT name, symbol FROM stocks")}
    missing = sorted({m["company_primary"] for m in memos if m["company_primary"] not in by_name})
    print(f"메모 {len(memos)}개 · 종목 이름 못 찾음 {missing}")
    lex = load_lexicon()
    client = None
    if args.mode == "run":
        from .openai_client import OpenAIClient, usage_totals
        client = OpenAIClient.from_env()
        client.response_format = None
        if client.model not in PRICES:
            raise SystemExit(f"모델 {client.model}의 가격을 몰라 비용 상한을 지킬 수 없습니다 (relevance_compare.PRICES)")
    recs, judgments, pend_memos, prompt_chars, stopped = [], [], 0, 0, None
    t0 = time.perf_counter()
    for m in memos:
        sym = by_name.get(m["company_primary"], "")
        judged = judge_memo(m["memo_body"], sym, lex)
        if any(j.decision == PENDING for j in judged):
            pend_memos += 1
            prompt_chars += len(build_prompt(sym, m["company_primary"], judged))
        logic = {j.sentence_index: j.decision for j in judged}
        err = None
        if client is not None:
            u = usage_totals(client.calls)
            pin, pout = PRICES[client.model]
            cost = u["prompt_tokens"] * pin / 1e6 + u["output_tokens"] * pout / 1e6
            if cost > args.max_usd:
                stopped = f"비용 한도 ${args.max_usd} 도달 (${cost:.2f}) — {m['memo_id']}에서 멈춤"
                print(stopped)
                break
            try:
                judge_with_llm(judged, sym, m["company_primary"], client)
            except Exception as e:
                err = str(e)[:200]
        judgments.append(judgment_record(m, sym, judged, logic, err))
        recs += sentence_records(m, sym, judged, err, logic)
    summary = {"mode": args.mode, "memos": args.memos, "memos_judged": len(judgments), **score(recs),
               "llm_memos": pend_memos, "prompt_chars": prompt_chars, "stopped": stopped,
               "fragments": sum(len(j["judged"]) for j in judgments)}
    if client is not None:
        summary["llm"] = {**usage_totals(client.calls), "model": client.model,
                          "seconds": round(time.perf_counter() - t0)}
    write_out(out, recs, judgments, summary)
    print(f"메모 {len(judgments)}, LLM 필요 메모 {pend_memos}, 프롬프트 합계 {prompt_chars}자, 정답 문장 {len(recs)},"
          f" 판정 조각 {summary['fragments']} (모두 judgments.jsonl에 저장)")
    print("로직 단계 판정 분포:", dict(Counter(r["logic_decision"] for r in recs)))
    print("점수:", json.dumps(summary["score"], ensure_ascii=False))
    print(f"결과: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
