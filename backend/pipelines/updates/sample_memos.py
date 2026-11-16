"""검수 표본용 메모 고르기와 메모 분석 결과 → 추적 항목 파일 (2026-11-10, LLM·DB 없음).

1) select: memos_long_v2에서 산업·업황 주제 메모(HBM·D램·메모리 업황·반도체 수요·AI 서버·경쟁사 등)와
   KB금융·NAVER 메모를 먼저 고른다. 정답 문장에 '추적'·'일부 추적'이 있는 메모만 (항목이 나와야 후보를 찾는다).
   결과: <out>/memos.jsonl (원본 메모 그대로) — tracking.evaluate_long run --memos <out>/memos.jsonl 로 메모 분석.
2) items: evaluate_long의 judgments.jsonl → experiment --gold가 읽는 모양(memo_id·symbol·sentences[items])의 items.jsonl.
   추적(normal·partial)이고 다른 문장에 합쳐지지 않은(merge_into 없음) 조각의 항목만.

    PYTHONPATH=backend python -m pipelines.updates.sample_memos select --industry 30 --per-company 13 --out results/updates/memos_sample_1110
    PYTHONPATH=backend python -m pipelines.tracking.evaluate_long run --memos results/updates/memos_sample_1110/memos.jsonl --max-usd 0.5
    PYTHONPATH=backend python -m pipelines.updates.sample_memos items --judgments <evaluate_long 결과>/judgments.jsonl \
        --out results/updates/memos_sample_1110/items.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

INDUSTRY = re.compile(r"HBM|D램|디램|DRAM|메모리|낸드|NAND|업황|반도체\s*(?:수요|경기|사이클|업계|시장)|수요|AI\s*서버|서버|데이터\s*센터|"
                      r"경쟁사|경쟁|파운드리|TSMC|마이크론|CXMT|중국\s*(?:업체|메모리|반도체)|증설|점유율|업계|산업")
PREFER_COMPANIES = ("KB금융", "NAVER")
TRACKED_GOLD = ("추적", "일부 추적")
TRACKED = ("normal", "partial")


def industry_hits(memo: dict) -> int:
    return len(INDUSTRY.findall(memo.get("memo_body_clean") or memo["memo_body"]))


def has_tracked(memo: dict) -> bool:
    return any(s.get("expected_decision") in TRACKED_GOLD for s in memo.get("sentences") or [])


def select(memos: list[dict], n_industry: int = 30, per_company: int = 13, seed: int = 20261110) -> list[dict]:
    """산업 주제 메모(키워드 많은 순, 같은 수면 섞어서) n_industry개 + KB금융·NAVER 메모 각 per_company개 (산업 메모와 겹치지 않게)."""
    rng = random.Random(seed)
    pool = [m for m in memos if has_tracked(m)]
    rng.shuffle(pool)
    ind = sorted((m for m in pool if industry_hits(m)), key=lambda m: -industry_hits(m))[:n_industry]
    picked = {m["memo_id"] for m in ind}
    out = list(ind)
    for company in PREFER_COMPANIES:
        cands = sorted((m for m in pool if m["company_primary"] == company and m["memo_id"] not in picked),
                       key=lambda m: -industry_hits(m))
        out += cands[:per_company]
        picked |= {m["memo_id"] for m in cands[:per_company]}
    return out


def to_items(judgments: list[dict]) -> list[dict]:
    """judgments.jsonl 줄 → experiment.load_items 모양. 항목이 없는 메모는 뺀다."""
    out = []
    for j in judgments:
        sents = []
        for d in j["judged"]:
            if d.get("decision") not in TRACKED or d.get("merge_into") is not None:
                continue
            items = [it for it in d.get("items") or [] if it.get("type") in ("topic", "price_below", "price_above")]
            if items:
                sents.append({"sentence_index": d["sentence_index"], "text": d["text"], "cleaned_text": d.get("cleaned_text"),
                              "category": d.get("category"), "items": items})
        if sents and j.get("symbol"):
            out.append({"memo_id": j["memo_id"], "symbol": j["symbol"], "company": j.get("company"), "sentences": sents})
    return out


def pick_items(items: list[dict], cand_rows: list[dict], floor: dict[str, float], prompt: str, max_usd: float,
               prefer_symbols: tuple[str, ...] = ("105560", "035420"), max_text: int = 800) -> tuple[list[dict], dict]:
    """판정 비용 상한 안에서 항목을 고른다: 산업 주제 항목 → 우선 종목 항목 → 나머지 순으로, 판정할 뉴스가 있는 주제 항목만.
    cand_rows: --llm none 실행의 candidates.csv. 반환: (항목 파일 줄(고른 항목만 남김), 집계)."""
    from . import autolabel
    from .relevance_compare import OUTPUT_TOKENS_PER_CAND, PRICES, TOKENS_PER_CHAR

    over: dict[str, list[dict]] = {}
    for r in cand_rows:
        if r["종류"] in ("news", "news_chunks") and float(r["유사도"]) >= floor.get(r["종류"], floor["news"]):
            over.setdefault(r["item_id"], []).append(r)
    pin, pout = PRICES["gpt-6.1-sol"]

    def usd(rs):
        cands = [{"cid": f"C{i + 1}", "kind": r["종류"], "date": r["날짜"], "title": r["제목"], "text": r["내용(앞부분)"]}
                 for i, r in enumerate(rs)]
        chars = len(autolabel.build_prompt({"symbol": rs[0]["symbol"], "description": rs[0]["항목"], "memo": rs[0]["메모 문장"]},
                                           cands, max_text=max_text, prompt=prompt))
        return chars * TOKENS_PER_CHAR * pin / 1e6 + OUTPUT_TOKENS_PER_CAND * len(rs) * pout / 1e6

    def rank(iid):
        rs = over[iid]
        text = f"{rs[0]['항목']}"
        return (0 if INDUSTRY.search(text) else 1 if rs[0]["symbol"].strip().zfill(6) in prefer_symbols else 2, iid)
    keep, total, groups = set(), 0.0, Counter()
    for iid in sorted(over, key=rank):
        cost = usd(over[iid])
        if total + cost > max_usd:
            continue
        keep.add(iid)
        total += cost
        groups[("industry", "prefer", "other")[rank(iid)[0]]] += 1
    out = []
    for m in items:
        sents = []
        for s in m["sentences"]:
            its = [it for i, it in enumerate(s["items"]) if f"{m['memo_id']}:{s['sentence_index']}:{i}" in keep]
            if its:
                # 항목 번호(item_id)가 바뀌지 않게 고르지 않은 항목은 빈 자리(type none)로 남긴다
                sents.append({**s, "items": [it if f"{m['memo_id']}:{s['sentence_index']}:{i}" in keep else {"type": "none"}
                                             for i, it in enumerate(s["items"])]})
        if sents:
            out.append({**m, "sentences": sents})
    return out, {"items_with_news": len(over), "picked": len(keep), "usd": round(total, 4), "groups": dict(groups)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="검수 표본용 메모 고르기 · 메모 분석 결과 → 항목 파일 (LLM·DB 없음)")
    ap.add_argument("mode", choices=["select", "items", "pick"])
    ap.add_argument("--items", help="pick: items 모드가 만든 항목 파일")
    ap.add_argument("--dry-run", help="pick: --llm none으로 돈 experiment 실행 폴더 (candidates.csv)")
    ap.add_argument("--max-usd", type=float, default=0.55, help="pick: 관련성 판정 예상 비용 상한")
    ap.add_argument("--memos", default="results/memo_personas/memos_long_v2")
    ap.add_argument("--industry", type=int, default=30)
    ap.add_argument("--per-company", type=int, default=13)
    ap.add_argument("--judgments", help="items: evaluate_long 결과의 judgments.jsonl")
    ap.add_argument("--out", required=True, help="select: 결과 폴더 · items: items.jsonl 경로")
    args = ap.parse_args(argv)

    from ..common.config import resolve_path
    from .eval_e2e import load_memos

    if args.mode == "select":
        picked = select(load_memos(args.memos), args.industry, args.per_company)
        out = resolve_path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "memos.jsonl").open("w", encoding="utf-8") as f:
            for m in picked:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"메모 {len(picked)}개 · 회사 {dict(Counter(m['company_primary'] for m in picked))} · "
              f"산업 키워드 있음 {sum(1 for m in picked if industry_hits(m))}개 → {out / 'memos.jsonl'}")
        return 0
    if args.mode == "pick":
        from ..common.config import load_config
        from .autolabel import load_prompt
        from .relevance import config as rel_config
        from .relevance_compare import read_csv
        from .topic import thresholds

        cfg = load_config("configs/updates.yaml")
        floor, _ = thresholds(cfg["topic"])
        items = [json.loads(l) for l in resolve_path(args.items).read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = read_csv(resolve_path(args.dry_run) / "candidates.csv")
        out_items, info = pick_items(items, rows, floor, load_prompt(rel_config(cfg.get("relevance"))["prompt"]), args.max_usd)
        out = resolve_path(args.out)
        with out.open("w", encoding="utf-8") as f:
            for m in out_items:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(json.dumps(info, ensure_ascii=False), f"→ {out}")
        return 0
    if not args.judgments:
        ap.error("items에는 --judgments가 필요합니다")
    lines = [json.loads(l) for l in resolve_path(args.judgments).read_text(encoding="utf-8").splitlines() if l.strip()]
    items = to_items(lines)
    out = resolve_path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for m in items:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    kinds = Counter(it["type"] for m in items for s in m["sentences"] for it in s["items"])
    print(f"메모 {len(lines)}개 중 항목 있는 메모 {len(items)}개 · 항목 {dict(kinds)} · "
          f"LLM 오류 메모 {sum(1 for l in lines if l.get('llm_error'))}개 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
