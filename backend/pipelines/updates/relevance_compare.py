"""사람 검수 뉴스 40건(review_human_news2.csv)으로 후보 거르기·관련성 판정 방식을 비교한다 (2026-11-09 준비, 검수 뒤 실행).

비교하는 것 (모두 사람 판정 기준 정밀도·재현율. 모집단은 검수한 후보 전체 = 현재 기본 설정이 보여 주는 후보):
  (1) 현재 기본          : 검수 후보 전부를 보여 준다 → 정밀도 = 사람 O 비율, 재현율 = 100% (정의상)
  (2) 제목 모드          : recent.filters.news_require_company: title (제목에 종목명·별칭, 하닉 반영)이 남기는 후보
  (2') sol 기존 프롬프트  : review_key_news2.csv의 sol 열 (autolabel 기본 PROMPT, 이미 있는 판정 · 비용 0)
  (3) 관련성 판정 프롬프트 : configs/candidate_relevance_prompt.md를 모델별로 (기본 sol·terra). --run-llm일 때만 호출
  (3+2) 프롬프트 O이면서 제목 모드에도 남는 후보

    # 비용 예상만 (LLM 없음, DB는 stocks 이름만 읽음)
    PYTHONPATH=backend python -m pipelines.updates.relevance_compare --run results/updates/run_20261109_170506
    # 실제 실행 (OpenAI 호출: 모델마다 항목 수만큼)
    PYTHONPATH=backend python -m pipelines.updates.relevance_compare --run results/updates/run_20261109_170506 --run-llm
    # chunks 모드 표본(review_sample --name news2_chunks)으로
    PYTHONPATH=backend python -m pipelines.updates.relevance_compare --run results/updates/run_<chunks 실행> \
        --review review_human_news2_chunks.csv --key review_key_news2_chunks.csv --run-llm

- 사람 판정 열('관련(O/X)')이 하나라도 비어 있으면 멈춘다.
- 프롬프트 예시가 검수 세트(32건·40건)의 제목·내용과 겹치면 멈춘다 (평가 세트로 프롬프트를 맞추면 점수가 부풀어 오른다).
- 단가는 공식 페이지가 아닌 제3자 자료 기준(2026-11-09 확인): sol 입력 $2·출력 $10, terra 입력 $1·출력 $5 (1M 토큰당).
- 결과: <run>/relevance_compare_<시각>/ (rows.csv, summary.json, report.md, 모델별 라벨 csv). DB에는 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

from . import autolabel
from .calibrate import LABEL_COL, LLM_COL

PRICES = {"gpt-6.1-sol": (2.0, 10.0), "gpt-6.1-terra": (1.0, 5.0)}   # 1M 토큰당 (입력, 출력) USD
TOKENS_PER_CHAR = 0.59          # 2026-11-09 memos_long 실측 (sol 프롬프트 글자당 입력 토큰)
OUTPUT_TOKENS_PER_CAND = 40     # 후보당 출력 (코드 포함, 추론 토큰 여유)
PROMPT_PATH = "configs/candidate_relevance_prompt.md"
OLD_REVIEW = "results/updates/run_20261109_133043/review_human.csv"


def read_csv(path: Path) -> list[dict]:
    """엑셀에서 저장해 cp949가 된 파일도 읽는다 (autolabel._read와 같은 순서)."""
    header, rows = autolabel._read(Path(path))
    return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows if any(c.strip() for c in r)]


def human_labels(rows: list[dict]) -> dict[str, bool]:
    """review_id → 사람 O(True)/X(False). 빈 칸이나 O/X 아닌 값이 있으면 ValueError."""
    bad = [r["review_id"] for r in rows if r.get(LABEL_COL, "").strip().upper() not in ("O", "X")]
    if bad:
        raise ValueError(f"사람 판정('{LABEL_COL}')이 비어 있거나 O/X가 아닌 행: {bad}")
    return {r["review_id"]: r[LABEL_COL].strip().upper() == "O" for r in rows}


def prompt_examples(prompt: str) -> list[str]:
    """프롬프트의 따옴표 안 예시 문장 (6자 이상)."""
    return [m.strip() for m in re.findall(r"[\"“]([^\"”]{6,})[\"”]", prompt)]


def example_overlaps(prompt: str, review_rows: list[dict]) -> list[tuple[str, str]]:
    """(예시, 겹친 review_id). 예시가 검수 후보의 제목·내용에 들어 있거나, 검수 제목이 프롬프트에 들어 있으면 겹침."""
    out = []
    for r in review_rows:
        hay = f"{r.get('제목', '')} {r.get('내용(앞부분)', '')}"
        out += [(ex, r["review_id"]) for ex in prompt_examples(prompt) if ex in hay]
        title = (r.get("제목") or "").strip()
        if len(title) >= 10 and title in prompt:
            out.append((title, r["review_id"]))
    return out


def metrics(pred: dict[str, bool], human: dict[str, bool]) -> dict:
    """pred: review_id → 보여 줌(True)/뺌(False). 정밀도 = 보여 준 것 중 사람 O, 재현율 = 사람 O 중 보여 준 것."""
    tp = sum(pred[i] and human[i] for i in human)
    fp = sum(pred[i] and not human[i] for i in human)
    fn = sum(not pred[i] and human[i] for i in human)
    tn = sum(not pred[i] and not human[i] for i in human)
    return {"shown": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "agreement": round((tp + tn) / len(human), 4) if human else None}


def title_mode(rows: list[dict], names: dict[str, str], rcfg: dict, symbol_aliases: dict) -> dict[str, bool]:
    """제목 모드(news_require_company: title)가 남기는지. names: 종목코드 → stocks 이름."""
    from .candidates import company_terms, drop_news_without_company
    from .models import Candidate

    out = {}
    for r in rows:
        sym = r["symbol"].strip().zfill(6)
        c = Candidate(ref=r["ref"], kind="news", symbol=sym, date=r["날짜"], title=r["제목"], text=r["내용(앞부분)"],
                      url="", source="", similarity=0.0)
        kept, _ = drop_news_without_company([c], company_terms(names.get(sym, ""), sym, rcfg, symbol_aliases), 0)
        out[r["review_id"]] = bool(kept)
    return out


def estimate(rows: list[dict], prompt: str, models: list[str], max_text: int = autolabel.MAX_TEXT) -> dict[str, dict]:
    """모델별 예상 호출 수·토큰·비용 (항목당 1회)."""
    by_item: dict[str, list[dict]] = {}
    for r in rows:
        by_item.setdefault(r["item_id"], []).append(r)
    chars = 0
    for item_id, rs in by_item.items():
        cands = [{"cid": f"C{k + 1}", "kind": r["종류"], "date": r["날짜"], "title": r["제목"], "text": r["내용(앞부분)"]}
                 for k, r in enumerate(rs)]
        chars += len(autolabel.build_prompt({"symbol": rs[0]["symbol"], "description": rs[0]["항목"],
                                             "memo": rs[0]["메모 문장"]}, cands, max_text=max_text, prompt=prompt))
    tin, tout = int(chars * TOKENS_PER_CHAR), OUTPUT_TOKENS_PER_CAND * len(rows)
    out = {}
    for m in models:
        pin, pout = PRICES.get(m, (None, None))
        out[m] = {"calls": len(by_item), "input_tokens": tin, "output_tokens": tout,
                  "usd": round(tin * pin / 1e6 + tout * pout / 1e6, 4) if pin is not None else None}
    return out


def cost(model: str, usage: dict) -> float | None:
    pin, pout = PRICES.get(model, (None, None))
    return None if pin is None else round(usage["prompt_tokens"] * pin / 1e6 + usage["output_tokens"] * pout / 1e6, 4)


def report(summary: dict) -> str:
    lines = ["# 관련성 판정 비교 (사람 검수 뉴스 기준)", "",
             f"- 검수: `{summary['review']}` {summary['n']}건 (사람 O {summary['human_o']}, X {summary['n'] - summary['human_o']})",
             f"- 프롬프트: `{summary['prompt']}` · 예시 겹침 검사 통과", "",
             "| 방식 | 보여 줌 | 정밀도 | 재현율 | 일치 | 호출 | 입력/출력 토큰 | 비용 |", "|---|---|---|---|---|---|---|---|"]
    pct = lambda v: "-" if v is None else f"{v:.0%}"
    for name, r in summary["conditions"].items():
        m, u = r["metrics"], r.get("usage") or {}
        lines.append(f"| {name} | {m['shown']} | {pct(m['precision'])} ({m['tp']}/{m['shown']}) | {pct(m['recall'])} | "
                     f"{pct(m['agreement'])} | {u.get('llm_calls', 0)} | {u.get('prompt_tokens', 0)}/{u.get('output_tokens', 0)} | "
                     f"{'-' if r.get('usd') is None else '$' + str(r['usd'])} |")
    lines += ["", "- (1)은 검수 후보 전체를 보여 주는 기준선이라 재현율이 정의상 100%다. 나머지 재현율은 이 40건 안에서의 값이다.",
              "- (2') sol 기존 프롬프트는 검수 전에 붙여 둔 판정(정답 파일의 sol 열)이다. sol 열이 비어 있으면 뺀다."]
    if summary.get("codes"):
        lines += ["", "## 이유 코드 (프롬프트 판정)", ""]
        for m, codes in summary["codes"].items():
            lines.append(f"- {m}: {json.dumps(codes, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사람 검수 뉴스로 후보 거르기·관련성 판정 비교 (DB 읽기 전용)")
    ap.add_argument("--run", required=True, help="review_human_news2.csv가 있는 실행 폴더")
    ap.add_argument("--review", default="review_human_news2.csv")
    ap.add_argument("--key", default="review_key_news2.csv")
    ap.add_argument("--prompt", default=PROMPT_PATH)
    ap.add_argument("--models", default="gpt-6.1-sol,gpt-6.1-terra")
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--run-llm", action="store_true", help="관련성 판정 프롬프트를 실제로 호출한다 (없으면 예상 비용만)")
    ap.add_argument("--max-usd", type=float, default=1.0, help="예상 비용이 이보다 크면 멈춘다")
    ap.add_argument("--max-text", type=int, default=autolabel.MAX_TEXT, help="후보 내용 최대 글자 수 (청크 전문이 들어가게)")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.config import load_config, resolve_path
    from ..common.db import get_read_dsn
    from .candidates import load_symbol_aliases

    run = resolve_path(args.run)
    rows = read_csv(run / args.review)
    key = {r["review_id"]: r for r in read_csv(run / args.key)}
    prompt = autolabel.load_prompt(args.prompt)
    old = read_csv(resolve_path(OLD_REVIEW)) if resolve_path(OLD_REVIEW).is_file() else []
    overlaps = example_overlaps(prompt, rows + old)
    if overlaps:
        raise SystemExit(f"프롬프트 예시가 검수 세트와 겹칩니다 (바꾼 뒤 다시 실행): {overlaps}")
    models = [m for m in args.models.split(",") if m]
    est = estimate(rows, prompt, models, args.max_text)
    total = sum(e["usd"] or 0 for e in est.values())
    print("예상:", json.dumps(est, ensure_ascii=False), f"· 합계 약 ${total:.3f}")
    human = human_labels(rows)                                  # 검수 전이면 여기서 멈춘다

    cfg = load_config(args.config)
    rcfg = cfg.get("recent", {})
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        syms = sorted({r["symbol"].strip().zfill(6) for r in rows})
        names = {s.strip(): n for s, n in conn.execute("SELECT symbol, name FROM stocks WHERE symbol = ANY(%s)", (syms,))}
    title = title_mode(rows, names, rcfg, load_symbol_aliases())
    conds = {"(1) 현재 기본": {"metrics": metrics({i: True for i in human}, human)},
             "(2) 제목 모드": {"metrics": metrics(title, human)}}
    if all(key[i].get("sol", "").strip().upper() in ("O", "X") for i in human):     # chunks 표본처럼 sol 판정이 없으면 건너뛴다
        sol_old = {i: key[i]["sol"].strip().upper() == "O" for i in human}
        conds["(2') sol 기존 프롬프트"] = {"metrics": metrics(sol_old, human)}
    if all(key[i].get("판정", "").strip().upper() in ("O", "X") for i in human):   # 파이프라인이 실행 중에 한 판정 (relevance.py, 비용 0)
        conds["(4) 파이프라인 판정 (실행 때)"] = {"metrics": metrics({i: key[i]["판정"].strip().upper() == "O" for i in human}, human)}
        for scope in ("company", "industry"):
            ids = {i for i in human if key[i].get("판정범위") == scope}
            if ids:
                conds[f"(4) 파이프라인 판정 · {scope}"] = {"metrics": metrics(
                    {i: key[i]["판정"].strip().upper() == "O" for i in ids}, {i: human[i] for i in ids})}
    per_row = {r["review_id"]: {"review_id": r["review_id"], "item_id": r["item_id"], "ref": r["ref"], "제목": r["제목"],
                                "사람": "O" if human[r["review_id"]] else "X", "제목모드": "남음" if title[r["review_id"]] else "빠짐",
                                "sol_기존": key[r["review_id"]].get("sol", "")} for r in rows}
    out_dir = run / f"relevance_compare_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir()
    codes_summary = {}
    if args.run_llm:
        if total > args.max_usd:
            raise SystemExit(f"예상 비용 ${total:.3f}가 --max-usd {args.max_usd}보다 큽니다")
        from ..tracking.openai_client import OpenAIClient, usage_totals

        for m in models:
            client = OpenAIClient.from_env()
            client.model = m
            dst = out_dir / f"labels_{m}.csv"
            stats = autolabel.label_csv(run / args.review, dst, client, prompt=prompt, with_codes=True,
                                        max_text=args.max_text)
            got = {r["review_id"]: r for r in read_csv(dst)}
            pred = {i: got[i][LLM_COL] == "O" for i in human}
            if stats["failed_items"]:
                print(f"{m}: 실패 항목 {stats['failed_items']}개 (그 후보는 X로 셈)")
            u = usage_totals(client.calls)
            conds[f"(3) 프롬프트 {m}"] = {"metrics": metrics(pred, human), "usage": u, "usd": cost(m, u),
                                         "failed_items": stats["failed_items"]}
            conds[f"(3+2) 프롬프트 {m} + 제목 모드"] = {"metrics": metrics({i: pred[i] and title[i] for i in human}, human)}
            codes_summary[m] = dict(sorted({c: sum(1 for i in human if got[i].get(autolabel.CODE_COL) == c)
                                            for c in {got[i].get(autolabel.CODE_COL, "") for i in human}}.items()))
            for i in human:
                per_row[i][f"{m}"] = got[i][LLM_COL]
                per_row[i][f"{m}_코드"] = got[i].get(autolabel.CODE_COL, "")
    summary = {"review": str(run / args.review), "n": len(human), "human_o": sum(human.values()), "prompt": args.prompt,
               "max_text": args.max_text,
               "estimate": est, "conditions": conds, "codes": codes_summary, "run_llm": args.run_llm}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "report.md").write_text(report(summary), encoding="utf-8")
    fields = list(dict.fromkeys(k for r in per_row.values() for k in r))
    with (out_dir / "rows.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(per_row.values())
    print(report(summary))
    print(f"결과: {out_dir} — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
