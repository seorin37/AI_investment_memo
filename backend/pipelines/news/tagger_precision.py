"""코스피 태거(stock_tagger) 정밀도 표본: 이전 커밋 규칙과 지금 규칙을 같은 기사로 돌려 새 연결을 고르게 뽑는다 (읽기 전용).

    python -m backend.pipelines.news.tagger_precision --since 2026-11-11 --until 2026-11-18 --old-rev c947c6f --n 100 \
        --out-dir ~/projects/_dryrun_20261118/tagger_precision

- 기사·기존 태그는 DB에서 한 번만 읽고, 두 규칙(옛 stock_tagger.py + 옛 설정 / 지금 코드 + 지금 설정)으로 각각 새 연결을 만든다.
- 표본: 새 연결 전체에서 기사당 1개씩 seed로 고르게 N개. csv에 문맥(앞뒤 80자)을 넣어 사람이 O/X를 매긴다.
- 지금 규칙에서 빠진 연결(옛 규칙에만 있는 것)과 새로 생긴 연결도 센다.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import random
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from . import stock_tagger as new_mod


def _old_module(rev: str):
    src = subprocess.run(["git", "show", f"{rev}:backend/pipelines/news/stock_tagger.py"], capture_output=True, text=True,
                         check=True).stdout
    cfg = subprocess.run(["git", "show", f"{rev}:configs/stock_aliases.yaml"], capture_output=True, text=True, check=True).stdout
    path = Path(tempfile.mkdtemp()) / "stock_tagger_old.py"
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("backend.pipelines.news.stock_tagger_old", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod, yaml.safe_load(cfg)


def _context(text: str, name: str, width: int = 80) -> str:
    i = (text or "").find(name)
    return "" if i < 0 else (text[max(0, i - width):i] + "[" + name + "]" + text[i + len(name):i + len(name) + width]).replace("\n", " ")


def links(mod, rules, arts, existing):
    out = []
    for nid, title, body in arts:
        for h in mod.match_article(title or "", body, rules):
            if h.symbol not in existing[nid]:
                out.append((nid, title or "", body or "", h))
    return out


def sample(new, n: int, seed: int):
    pool, seen, picked = list(new), set(), []
    random.Random(seed).shuffle(pool)
    for row in pool:
        if row[0] not in seen:
            seen.add(row[0])
            picked.append(row)
        if len(picked) >= n:
            break
    return picked


def write_csv(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["no", "맞음(O/X/?)", "판정 근거", "종목코드", "이름", "규칙", "본문 횟수", "기사 제목", "문맥", "news_id"])
        for i, (nid, title, body, h) in enumerate(rows, 1):
            ctx = _context(title, h.name) if h.rule == "title" else _context(body, h.name)
            w.writerow([i, "", "", h.symbol, h.name, h.rule, h.count, title, ctx, nid])


def main(argv=None) -> int:
    from zoneinfo import ZoneInfo

    import psycopg

    from ..common.db import get_read_dsn, load_env
    ap = argparse.ArgumentParser(description="코스피 태거 정밀도 표본 (읽기 전용)")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--old-rev", required=True, help="비교할 이전 커밋 (stock_tagger.py·stock_aliases.yaml)")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--memo-symbols", default="", help="쉼표 구분: 메모가 있는 종목의 새·기존 연결 수를 따로 센다")
    args = ap.parse_args(argv)
    load_env()
    kst = ZoneInfo("Asia/Seoul")
    since, until = (datetime.fromisoformat(d).replace(tzinfo=kst) for d in (args.since, args.until))
    old_mod, old_cfg = _old_module(args.old_rev)
    new_cfg = yaml.safe_load(new_mod.CONFIG_PATH.read_text(encoding="utf-8"))
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, name FROM stocks")
            stocks = {s.strip(): n for s, n in cur.fetchall()}
            cur.execute(new_mod.ARTICLES_SQL, {"since": since, "until": until})
            arts = cur.fetchall()
            cur.execute(new_mod.EXISTING_SQL, {"ids": [a[0] for a in arts]})
            existing = defaultdict(set)
            for nid, sym in cur.fetchall():
                existing[nid].add(sym.strip())
        conn.rollback()
    dart = new_mod.listed_names()
    old_new = links(old_mod, old_mod.build_rules(stocks, old_cfg, dart), arts, existing)
    cur_new = links(new_mod, new_mod.build_rules(stocks, new_cfg, dart), arts, existing)
    key = lambda rows: {(n, h.symbol) for n, _, _, h in rows}          # noqa: E731
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "before.csv", sample(old_new, args.n, args.seed))
    write_csv(args.out_dir / "after.csv", sample(cur_new, args.n, args.seed))
    removed = [r for r in old_new if (r[0], r[3].symbol) not in key(cur_new)]
    write_csv(args.out_dir / "removed.csv", removed)
    names = Counter(r[3].name for r in removed)
    # 종목별 새 연결 수 (06:30 뉴스 후보 어림용): 지금 규칙 기준, 기간 일수로 나눈 하루 평균
    days = max(1, (until - since).days)
    per_sym = Counter(h.symbol for *_, h in cur_new)
    counts = sorted(per_sym.values(), reverse=True)
    pick = lambda q: counts[min(len(counts) - 1, int(q * (len(counts) - 1)))] if counts else 0   # noqa: E731
    memo = [s.strip() for s in (args.memo_symbols or "").split(",") if s.strip()]
    print({"days": days, "symbols_with_new_links": len(per_sym),
           "per_symbol_links_per_day": {"top1": round(pick(0) / days, 2), "p10": round(pick(0.1) / days, 2),
                                        "median": round(pick(0.5) / days, 2), "p90": round(pick(0.9) / days, 2)},
           "memo_symbols_new_links_per_day": {s: round(per_sym.get(s, 0) / days, 2) for s in memo},
           "memo_symbols_existing_links_per_day": {s: round(sum(s in existing[a[0]] for a in arts) / days, 2) for s in memo}})
    print({"articles": len(arts), "before_links": len(old_new), "after_links": len(cur_new),
           "removed": len(removed), "added": len(key(cur_new) - key(old_new)),
           "before_symbols": len({h.symbol for *_, h in old_new}), "after_symbols": len({h.symbol for *_, h in cur_new}),
           "removed_top": names.most_common(12)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
