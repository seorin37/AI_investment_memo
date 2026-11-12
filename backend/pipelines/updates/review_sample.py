"""사람 검수용 뉴스 후보 표본 만들기 (2026-11-09: chunks 모드 40건 준비). DB는 읽기만, 결과는 실행 폴더에 csv로만.

experiment 실행 폴더의 candidates.csv에서 뉴스 후보를 항목이 한쪽에 몰리지 않게(항목마다 한 건씩 돌아가며) 뽑는다.
- chunks 모드 폴더면 기본으로 원문 청크로 매칭된 후보(종류 news_chunks)만 쓴다. --include-headline이면 원문이 없어
  제목+요약 벡터로 보충된 후보(종류 news)도 넣는다.
- 내용 칸: candidates.csv는 500자에서 자르므로, 원문 청크 후보는 DB(news_chunks)에서 매칭된 청크 전문을 찾아 넣는다
  (같은 기사의 청크 중 csv 내용으로 시작하는 것. 못 찾으면 csv 내용 그대로, 정답 파일에 표시).
- 검수 파일에는 제목·링크·매체·내용을 보이고, 유사도·라벨러 판정·필터 결과는 정답 파일(review_key_*.csv)에만 둔다.
- 이미 사람이 본 후보는 뺀다: --exclude에 준 검수 파일들의 ref (기본: run_20261109_133043/review_key.csv).

    PYTHONPATH=backend python -m pipelines.updates.review_sample --run results/updates/run_<chunks 실행> --n 40 \\
        --name news2_chunks
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

# 내용 칸 이름은 autolabel·relevance_compare가 읽는 '내용(앞부분)' 그대로 (값은 매칭된 청크 전문)
SHOW = ["item_id", "symbol", "항목", "메모 문장", "종류", "ref", "날짜", "매체", "제목", "링크", "내용(앞부분)"]
# 이미 사람이 본 검수: 1차 32건, 뉴스 40건(article), 뉴스 42건(chunks)
DEFAULT_EXCLUDE = ["results/updates/run_20261109_133043/review_key.csv",
                   "results/updates/run_20261109_170506/review_key_news2.csv",
                   "results/updates/run_20261109_173514/review_key_news2_chunks.csv",
                   "results/updates/run_20261110_154307/review_key_news3_chunks.csv"]   # 2026-11-10 25건
CHUNK_SQL = "SELECT chunk_index, chunk_text FROM news_chunks WHERE news_id = %(n)s ORDER BY chunk_index"


def balanced_sample(rows: list[dict], n: int, seed: int = 20261109) -> list[dict]:
    """항목마다 한 건씩 돌아가며 n건. 같은 기사(ref)는 한 번만. 결과 순서는 섞는다."""
    rng = random.Random(seed)
    by_item: dict[str, list[dict]] = {}
    for r in rows:
        by_item.setdefault(r["item_id"], []).append(r)
    for v in by_item.values():
        rng.shuffle(v)
    order = sorted(by_item)
    rng.shuffle(order)
    picked, seen = [], set()
    while len(picked) < n and any(by_item.values()):
        for item in order:
            while by_item[item] and by_item[item][0]["ref"] in seen:
                by_item[item].pop(0)
            if by_item[item] and len(picked) < n:
                r = by_item[item].pop(0)
                picked.append(r)
                seen.add(r["ref"])
    rng.shuffle(picked)
    return picked


INDUSTRY_WORDS = ("업황", "수요", "가격", "경쟁", "산업", "업계", "시장", "공급", "증설", "단가")


def is_industry(r: dict) -> bool:
    """산업·업황 항목: 관련성 판정 범위(판정범위 열)가 industry이거나, 판정이 없으면 항목 설명의 낱말로."""
    scope = (r.get("판정범위") or "").strip()
    return scope == "industry" if scope else any(w in (r.get("항목") or "") for w in INDUSTRY_WORDS)


def prioritized_sample(rows: list[dict], n: int, prefer_symbols: set[str], seed: int = 20261109) -> list[dict]:
    """산업·업황 항목이나 prefer_symbols 종목의 후보를 먼저(항목마다 돌아가며), 모자라면 나머지에서 채운다."""
    first = [r for r in rows if is_industry(r) or r["symbol"].strip().zfill(6) in prefer_symbols]
    picked = balanced_sample(first, n, seed)
    if len(picked) < n:
        seen = {r["ref"] for r in picked}
        picked += balanced_sample([r for r in rows if r not in first and r["ref"] not in seen], n - len(picked), seed)
    random.Random(seed).shuffle(picked)
    return picked


def quota_sample(rows: list[dict], n: int, prefer_symbols: set[str], min_industry: int, min_prefer: int,
                 seed: int = 20261109) -> list[dict]:
    """산업 항목 후보 min_industry건, prefer_symbols 종목 후보 min_prefer건을 먼저 채우고(항목마다 돌아가며) 나머지는 전체에서.
    두 조건에 다 맞는 후보는 양쪽에 센다. 모자라면 있는 만큼만."""
    sym = lambda r: r["symbol"].strip().zfill(6)
    picked = balanced_sample([r for r in rows if is_industry(r)], min(min_industry, n), seed)
    seen = {r["ref"] for r in picked}
    have = sum(1 for r in picked if sym(r) in prefer_symbols)
    if have < min_prefer:
        more = [r for r in rows if sym(r) in prefer_symbols and r["ref"] not in seen]
        add = balanced_sample(more, min(min_prefer - have, n - len(picked)), seed)
        picked += add
        seen |= {r["ref"] for r in add}
    if len(picked) < n:
        picked += balanced_sample([r for r in rows if r["ref"] not in seen], n - len(picked), seed)
    random.Random(seed).shuffle(picked)
    return picked


def full_chunk(chunks: list[tuple[int, str]], shown: str) -> tuple[int | None, str]:
    """csv에 잘려 들어간 내용(shown)으로 시작하는 청크 (chunk_index, 전문). 못 찾으면 (None, shown)."""
    head = (shown or "").strip()[:120]
    if not head:
        return None, shown
    for idx, text in chunks:
        if (text or "").replace("\n", " ").strip().startswith(head):
            return idx, text
    return None, shown


def candidate_pool(rows: list[dict], exclude_refs: set[str], include_headline: bool) -> list[dict]:
    kinds = {"news_chunks", "news"} if include_headline else {"news_chunks"}
    if not any(r["종류"] == "news_chunks" for r in rows):
        kinds = {"news"}                                       # article 모드 폴더
    return [r for r in rows if r["종류"] in kinds and r["ref"] not in exclude_refs]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사람 검수용 뉴스 후보 표본 (DB 읽기 전용)")
    ap.add_argument("--run", required=True, help="experiment 실행 폴더 (candidates.csv, refs.json)")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--name", default="news2_chunks", help="파일 이름: review_human_<name>.csv / review_key_<name>.csv")
    ap.add_argument("--exclude", nargs="*", default=DEFAULT_EXCLUDE, help="이미 본 검수의 key·human csv (ref 열)")
    ap.add_argument("--include-headline", action="store_true", help="원문 없이 제목+요약으로 보충된 후보도 넣는다")
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--prefer-symbols", default="",
                    help="먼저 뽑을 종목코드(쉼표). 산업·업황 항목(판정범위 industry 또는 항목 낱말)과 함께 먼저 뽑는다")
    ap.add_argument("--min-industry", type=int, default=0, help="산업·업황 항목 후보를 이만큼 먼저 (모자라면 있는 만큼)")
    ap.add_argument("--min-prefer", type=int, default=0, help="--prefer-symbols 종목 후보를 이만큼 먼저")
    ap.add_argument("--judged-only", action="store_true",
                    help="관련성 판정을 받은 후보(판정(O/X) 열이 있는 것)만 (판정 결과를 사람 판정과 맞춰 보려고)")
    args = ap.parse_args(argv)

    import json

    import psycopg

    from ..common.config import load_config, resolve_path
    from ..common.db import get_read_dsn
    from .candidates import company_terms, drop_news_without_company, load_symbol_aliases
    from .models import Candidate
    from .relevance_compare import read_csv

    run = resolve_path(args.run)
    rows = read_csv(run / "candidates.csv")
    refs = json.loads((run / "refs.json").read_text(encoding="utf-8")) if (run / "refs.json").is_file() else {}
    exclude = {r["ref"] for p in args.exclude if resolve_path(p).is_file() for r in read_csv(resolve_path(p))}
    pool = candidate_pool(rows, exclude, args.include_headline)
    if args.judged_only:
        pool = [r for r in pool if (r.get("판정(O/X)") or "").strip()]
    prefer = {s.strip().zfill(6) for s in args.prefer_symbols.split(",") if s.strip()}
    if args.min_industry or args.min_prefer:
        picked = quota_sample(pool, args.n, prefer, args.min_industry, args.min_prefer, args.seed)
    else:
        picked = prioritized_sample(pool, args.n, prefer, args.seed)   # 우선 대상이 없으면 balanced_sample과 같다
    rcfg = load_config(args.config).get("recent", {})
    aliases = load_symbol_aliases()
    out_rows, key_rows = [], []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        names = {s.strip(): n for s, n in conn.execute("SELECT symbol, name FROM stocks WHERE symbol = ANY(%s)",
                                                        (sorted({r["symbol"] for r in picked}),))}
        for k, r in enumerate(picked, 1):
            ref = refs.get(r["ref"], {})
            idx, text = None, r["내용(앞부분)"]
            if r["종류"] == "news_chunks":
                chunks = conn.execute(CHUNK_SQL, {"n": int(r["ref"].split(":", 1)[1])}).fetchall()
                idx, text = full_chunk(chunks, r["내용(앞부분)"])
            rid = f"C{k:02d}"
            out_rows.append({"review_id": rid, **{c: r.get(c, "") for c in SHOW[:7]}, "매체": ref.get("source", ""),
                             "제목": r["제목"], "링크": ref.get("url", ""), "내용(앞부분)": (text or "").replace("\n", " ")})
            c = Candidate(ref=r["ref"], kind="news", symbol=r["symbol"], date=r["날짜"], title=r["제목"], text="",
                          url="", source="", similarity=0.0)
            title_kept = bool(drop_news_without_company([c], company_terms(names.get(r["symbol"], ""), r["symbol"],
                                                                           rcfg, aliases), 0)[0])
            key_rows.append({"review_id": rid, "item_id": r["item_id"], "ref": r["ref"], "종류": r["종류"],
                             "유사도": r["유사도"], "청크번호": "" if idx is None else idx,
                             "청크전문": "예" if idx is not None else ("해당 없음" if r["종류"] != "news_chunks" else "못 찾음"),
                             "제목만_종목명_필터": "남음" if title_kept else "빠짐", "sol": "",
                             # 파이프라인 관련성 판정 (relevance.py, candidates.csv에 있을 때). 사람 판정과 맞춰 볼 값
                             "판정": r.get("판정(O/X)", ""), "판정코드": r.get("판정코드", ""), "판정범위": r.get("판정범위", ""),
                             "산업항목": "예" if is_industry(r) else ""})
    human_path, key_path = run / f"review_human_{args.name}.csv", run / f"review_key_{args.name}.csv"
    with human_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["review_id"] + SHOW + ["관련(O/X)", "메모(선택)"])
        for r in out_rows:
            w.writerow([r["review_id"]] + [r[c] for c in SHOW] + ["", ""])
    with key_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(key_rows[0]) if key_rows else ["review_id"])
        w.writeheader()
        w.writerows(key_rows)
    from collections import Counter

    print(f"후보 {len(pool)}건(이미 본 ref {len(exclude)}개 제외) 중 {len(picked)}건 · 항목별 {dict(Counter(Counter(r['item_id'] for r in picked).values()))}"
          f" · 종목 {dict(Counter(r['symbol'] for r in picked))} · 청크 전문 {sum(k['청크전문'] == '예' for k in key_rows)}건")
    print(f"결과: {human_path} / {key_path} — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
