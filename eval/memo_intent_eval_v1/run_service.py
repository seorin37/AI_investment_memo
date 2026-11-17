"""memo_intent_eval_v1을 실제 서비스 순서로 끝까지 돌린다 (2026-11-16).

1) 메모 분석: 서비스와 같은 함수 app.board.analysis.analyze_memo (규칙 판정 → pending 문장만 LLM 1회 → 추적 항목·확인 질문).
2) 그 추적 항목을 experiment 입력 형식(gold jsonl)으로 쓴다. 정답 항목은 쓰지 않는다.
3) 카드 생성: pipelines.updates.experiment (운영 설정 configs/updates.yaml, DB 읽기만, 결과는 파일).
4) 메모별 보고서 report.md: 원문 · 기대 의도 · 분석이 만든 항목·확인 질문 · 카드(또는 카드 없음 이유).

    PYTHONPATH=backend python eval/memo_intent_eval_v1/run_service.py [--config configs/updates.yaml]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).with_name("cases.jsonl")


def price_rows(symbol: str) -> list[tuple]:
    import psycopg

    from pipelines.common.db import get_read_dsn
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        return conn.execute("SELECT trade_date, close FROM prices_daily WHERE symbol = %s ORDER BY trade_date DESC LIMIT 2",
                            (symbol,)).fetchall()


LEX = None
TRACK_KINDS = {"tracking", "price_condition", "comparison"}
ASK_KINDS = {"definition", "causal", "comparison"}  # 추적 아닌 비교 요청도 한 번 답하기 (2026-11-16)


def _owner(text: str, sents: list[str]) -> int | None:
    """기대 의도 문장 → 분석이 나눈 문장 번호 (같은 글이면 그 문장, 아니면 글자가 가장 많이 겹치는 문장)."""
    if not sents:
        return None
    for i, s in enumerate(sents):
        if s.strip() == text.strip() or text.strip() in s or s.strip() in text:
            return i
    return max(range(len(sents)), key=lambda i: len(set(sents[i]) & set(text)))


def score(case: dict, sents: list[str], items: list[dict], questions: list[dict], confirms: list[dict]) -> dict:
    """의도별 채점. ok: 추적이 필요한 의도엔 항목이, 질문 의도엔 ask가 있고 항목이 없을 때, 비추적엔 둘 다 없을 때."""
    rows = []
    for e in case["expected_intents"]:
        i = _owner(e["text"], sents)
        has_item = any(it["sentence_index"] == i for it in items)
        has_ask = any(q["sentence_index"] == i for q in questions)
        has_conf = any(c["sentence_index"] == i for c in confirms)
        kind = e["kind"]
        if e.get("create_tracking"):
            ok = has_item
        elif kind in ASK_KINDS:
            ok = has_ask and not has_item
        elif kind == "clarification":
            ok = has_conf and not has_item
        else:
            ok = not has_item
        rows.append({"kind": kind, "text": e["text"], "sentence": i, "item": has_item, "ask": has_ask, "ok": ok})
    return {"intents": rows, "ok": sum(r["ok"] for r in rows), "total": len(rows), "memo_ok": all(r["ok"] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--out-dir", default="results/intent_service")
    ap.add_argument("--prompt", help="메모 분석 지시문 (예: configs/tracking_judge_prompt_intent.md). 없으면 운영 지시문")
    ap.add_argument("--cases", default=str(CASES), help="테스트 메모 파일 (기본 cases.jsonl, 새 메모는 cases_holdout.jsonl)")
    ap.add_argument("--answer-asks", action="store_true",
                    help="실험: 한 번 답하기(ask) 질문도 같은 근거 검색·카드 생성에 넣는다 (전용 답변 프롬프트는 아직 없음)")
    ap.add_argument("--skip-cards", action="store_true", help="메모 분석과 채점만 (카드 생성 안 함)")
    args = ap.parse_args()
    import os
    if args.prompt:
        os.environ["TRACKING_PROMPT_PATH"] = args.prompt
    sys.path.insert(0, str(ROOT / "backend"))
    from app.board.analysis import AnalysisError, analyze_memo, default_llm
    from pipelines.tracking.judge import judge_memo
    from pipelines.tracking.lexicon import load_lexicon
    global LEX
    LEX = load_lexicon()

    cases = [json.loads(x) for x in Path(args.cases).read_text(encoding="utf-8").splitlines() if x.strip()]
    run_dir = ROOT / args.out_dir / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=False)
    llm = default_llm()
    analysis, gold = [], []
    for n, case in enumerate(cases, 1):
        try:
            res = analyze_memo(n, 1, case["text"], case["symbol"], case["company"], llm, price_rows(case["symbol"]))
            items, confirms, oos, err = res.items, res.confirmations, res.out_of_scope, ""
            questions = getattr(res, "questions", [])
        except AnalysisError as exc:
            items, confirms, oos, err, questions = [], [], False, str(exc), []
        sents = [j.cleaned_text or j.text for j in judge_memo(case["text"], case["symbol"], LEX)]
        analysis.append({"memo_id": case["memo_id"], "items": items, "confirmations": confirms, "questions": questions,
                         "out_of_scope": oos, "error": err, "sentences": sents,
                         "score": score(case, sents, items, questions, confirms)})
        by_sent: dict[int, list] = {}
        for it in items:
            by_sent.setdefault(it["sentence_index"], []).append(it)
        if args.answer_asks:                                 # 실험: ask도 같은 근거 검색·카드 생성으로 답을 만든다
            for q in questions:
                by_sent.setdefault(q["sentence_index"], []).append(
                    {"type": "topic", "description": q["question"], "keywords": [], "category": "ask", "ask": q.get("kind") or "ask"})
        gold.append({"memo_id": case["memo_id"], "symbol": case["symbol"], "text": case["text"],
                     "sentences": [{"sentence_index": i, "text": sents[i] if i < len(sents) else case["text"],
                                    "items": its} for i, its in sorted(by_sent.items())]})
        print(f"{case['memo_id']}: 항목 {len(items)} · 확인 질문 {len(confirms)}{' · 오류 ' + err if err else ''}", flush=True)
    (run_dir / "analysis.jsonl").write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in analysis), encoding="utf-8")
    gold_path = run_dir / "gold_from_analysis.jsonl"
    gold_path.write_text("".join(json.dumps(g, ensure_ascii=False) + "\n" for g in gold), encoding="utf-8")

    symbols = ",".join(sorted({c["symbol"] for c in cases}))
    totals = {"memos": len(cases), "memo_ok": sum(a["score"]["memo_ok"] for a in analysis),
              "intents": sum(a["score"]["total"] for a in analysis), "intents_ok": sum(a["score"]["ok"] for a in analysis),
              "prompt": args.prompt or "configs/tracking_judge_prompt.md"}
    (run_dir / "score.json").write_text(json.dumps(totals, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False))
    cmd = [sys.executable, "-m", "pipelines.updates.experiment", "--llm", "openai", "--save-llm-io", "--config", args.config,
           "--gold", str(gold_path), "--symbols", symbols, "--out-dir", str(run_dir / "cards")]
    if args.skip_cards:
        proc = subprocess.CompletedProcess(cmd, 0, "", "카드 생성 생략 (--skip-cards)")
    else:
      proc = subprocess.run(cmd, cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": "backend"},
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    (run_dir / "experiment.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    card_runs = sorted((run_dir / "cards").glob("run_*"))
    cards, outcomes = {}, {}
    if card_runs:
        cr = card_runs[-1]
        for line in (cr / "cards.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                x = json.loads(line)
                cards[x["item_id"]] = x.get("card") or x
        for line in (cr / "responses.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                x = json.loads(line)
                if x.get("item_id"):
                    outcomes[x["item_id"]] = x

    out = ["# 새 테스트셋 실제 서비스 순서 실행", f"설정 {args.config} · 지시문 {totals['prompt']} · {run_dir.name}", f"메모 {totals['memo_ok']}/{totals['memos']} · 의도 {totals['intents_ok']}/{totals['intents']}", ""]
    for case, a, g in zip(cases, analysis, gold):
        out += [f"## {case['memo_id']} · {case['company']}", "```", case["text"], "```", "**기대 의도**"]
        out += [f"- [{e['kind']}] {e['text']}" + (" → 추적 항목 필요" if e.get("create_tracking") else "")
                for e in case["expected_intents"]]
        out.append("**메모 분석 결과 (규칙 + LLM)**")
        if a["error"]:
            out.append(f"- 분석 오류: {a['error']}")
        if not a["items"]:
            out.append("- 추적 항목 없음")
        for s in g["sentences"]:
            for i, it in enumerate(s["items"]):
                iid = f"{case['memo_id']}:{s['sentence_index']}:{i}"
                label = it["description"] + (f" ({it['price_threshold']:,}원)" if it.get("price_threshold") else "")
                out.append(f"- 💬 한 번 답하기 [{it['ask']}] {label}" if it.get("ask") else f"- 항목 [{it['type']}] {label}")
                c = cards.get(iid)
                if c:
                    out.append(f"  - 🃏 **{c.get('headline')}** (when {c.get('when')})")
                    out += [f"    - {f.get('text') if isinstance(f, dict) else f}" for f in c.get("facts", [])]
                    if c.get("explanation"):
                        out.append(f"    - [설명] {c['explanation']}")
                    for k in c.get("calculations") or []:              # 실험(2026-11-17) 코드 계산값 (calc.py)
                        out.append(f"    - 🧮 계산값: {k['label']} = **{k['result']}** (코드 계산: {k['a']} ÷ {k['b']})" if k.get("ok")
                                   else f"    - 🧮 계산 안 함 ({k.get('reason')}): {k.get('label')} ({k.get('a')} / {k.get('b')})")
                    out.append(f"    - ↳ {c.get('memo_link')}")
                else:
                    o = outcomes.get(iid, {})
                    if o.get("type") == "ask_no_answer":            # 실험(2026-11-17): 질문에 답을 못 만들면 '자료 없음' 답
                        out.append(f"  - 💬 **자료 없음 답**: {o.get('message')}  (내부 이유 {o.get('reason')})")
                    else:
                        out.append(f"  - 카드 없음 ({o.get('type', '-')}: {o.get('reason', '-')})")
        for q in ([] if args.answer_asks else a.get("questions", [])):
            out.append(f"- 💬 한 번 답하기 [{q.get('kind')}] {q.get('question')}  (문장: {q.get('text')})")
        sc = a["score"]
        out.append(f"- 채점: 의도 {sc['ok']}/{sc['total']} " + " ".join(("✅" if r["ok"] else "❌") + r["kind"] for r in sc["intents"]))
        for cf in a["confirmations"]:
            out.append(f"- 확인 질문: {cf['question']}")
        if a["out_of_scope"]:
            out.append("- 메모 전체 범위 밖")
        out += ["**하면 안 되는 것**"] + [f"- {f}" for f in case.get("forbidden") or []] + [""]
    (run_dir / "report.md").write_text("\n".join(out), encoding="utf-8")
    print(run_dir)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
