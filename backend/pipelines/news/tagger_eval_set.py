"""코스피 태거 고정 평가 세트 (읽기 전용, 2026-11-18).

    # 1) 만들기: 여러 규칙(커밋 또는 WORKING=지금 작업본)으로 같은 기간을 태깅해 새 연결의 합집합에서 N개를 한 번 뽑는다
    python -m backend.pipelines.news.tagger_eval_set build --since 2026-11-11 --until 2026-11-18 \
        --revs c947c6f,f9e143a,WORKING --n 200 --out eval/news_tagging/eval_set_20261118.csv
    # 2) 사람이 "판정"(O/X/?)과 "근거"를 채운다
    # 3) 채점: 같은 세트로 규칙마다 정밀도(낸 연결 중 맞음)와 놓친 비율(맞는 연결 중 안 낸 것)을 낸다
    python -m backend.pipelines.news.tagger_eval_set score --set eval/news_tagging/eval_set_20261118.csv --revs c947c6f,f9e143a,WORKING

    # 연결 목록으로 만들기 (2026-11-19: timer가 붙인 연결 전부)
    python -m backend.pipelines.news.tagger_eval_set pairs --pairs links.csv --revs 1befe68,WORKING --start 201 \
        --out eval/news_tagging/eval_set_timer_20261119.csv

- 합집합에서 고르게 뽑으므로 규칙마다 그 규칙이 낸 연결은 고르게 뽑힌 표본이다. 애매(?)는 정밀도·놓친 비율 계산에서 뺀다.
- "새 연결" = 그 기사에 아직 없는 (기사, 종목). 기존 태그(4종목 RSS 태거)는 평가하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import random
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from . import stock_tagger as cur_mod

BASELINE_SQL = "SELECT news_id, symbol FROM news_stocks WHERE news_id = ANY(%(ids)s) AND score IS NULL"


def load_rev(rev: str):
    """(stock_tagger 모듈, 설정 dict). WORKING이면 지금 파일."""
    if rev == "WORKING":
        return cur_mod, yaml.safe_load(cur_mod.CONFIG_PATH.read_text(encoding="utf-8"))
    show = lambda p: subprocess.run(["git", "show", f"{rev}:{p}"], capture_output=True, text=True, check=True).stdout  # noqa: E731
    path = Path(tempfile.mkdtemp()) / f"stock_tagger_{rev}.py"
    path.write_text(show("backend/pipelines/news/stock_tagger.py"), encoding="utf-8")
    name = f"backend.pipelines.news.stock_tagger_{rev}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod, yaml.safe_load(show("configs/stock_aliases.yaml"))


def fetch(since=None, until=None, ids=None):
    """(기사 목록, 기존 태그, 종목). ids를 주면 그 기사만."""
    import psycopg

    from ..common.db import get_read_dsn, load_env
    load_env()
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, name FROM stocks")
            stocks = {s.strip(): n for s, n in cur.fetchall()}
            if ids is not None:
                cur.execute("""SELECT a.id, a.title, b.body FROM news_articles a LEFT JOIN news_article_bodies b ON b.news_id = a.id
                               WHERE a.id = ANY(%(ids)s) ORDER BY a.id""", {"ids": list(ids)})
            else:
                cur.execute(cur_mod.ARTICLES_SQL, {"since": since, "until": until})
            arts = cur.fetchall()
            # 기존 태그 = score 없는 태그(4종목 RSS 태거·네이버)만. 코스피 태거가 이미 쓴 연결(score 있음)도 평가 대상이다 (2026-11-19)
            cur.execute(BASELINE_SQL, {"ids": [a[0] for a in arts]})
            existing = defaultdict(set)
            for nid, sym in cur.fetchall():
                existing[nid].add(sym.strip())
        conn.rollback()
    return arts, existing, stocks


def links(rev: str, arts, existing, stocks) -> dict[tuple[int, str], object]:
    mod, cfg = load_rev(rev)
    rules = mod.build_rules(stocks, cfg, cur_mod.listed_names())
    out = {}
    for nid, title, body in arts:
        for h in mod.match_article(title or "", body, rules):
            if h.symbol not in existing[nid]:
                out[(nid, h.symbol)] = h
    return out


def _context(text: str, name: str, width: int = 90) -> str:
    i = (text or "").find(name)
    return "" if i < 0 else (text[max(0, i - width):i] + "[" + name + "]" + text[i + len(name):i + len(name) + width]).replace("\n", " ")


def build(args) -> int:
    from zoneinfo import ZoneInfo
    kst = ZoneInfo("Asia/Seoul")
    since, until = (datetime.fromisoformat(d).replace(tzinfo=kst) for d in (args.since, args.until))
    arts, existing, stocks = fetch(since, until)
    by_rev = {rev: links(rev, arts, existing, stocks) for rev in args.revs}
    union = sorted(set().union(*by_rev.values()))
    random.Random(args.seed).shuffle(union)
    picked = sorted(union[:args.n])
    art = {a[0]: a for a in arts}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["no", "판정(O/X/?)", "근거", "news_id", "종목코드", "이름", "규칙", "낸 규칙", "기사 제목", "문맥"])
        for i, key in enumerate(picked, 1):
            h = next(v[key] for v in by_rev.values() if key in v)
            _, title, body = art[key[0]]
            ctx = _context(title, h.name) if h.rule == "title" else _context(body, h.name)
            w.writerow([i, "", "", key[0], key[1], h.name, h.rule, " ".join(r for r in args.revs if key in by_rev[r]), title, ctx])
    print({"articles": len(arts), **{f"links_{r}": len(v) for r, v in by_rev.items()}, "union": len(union), "picked": len(picked),
           "out": str(args.out)})
    return 0


def pairs(args) -> int:
    """주어진 (news_id, symbol) 목록으로 세트를 만든다 (예: timer가 붙인 연결 전부). 이름·규칙·문맥은 --revs 중 처음 낸 규칙에서."""
    keys = sorted({(int(r["news_id"]), r["symbol"].strip()) for r in csv.DictReader(args.pairs.open(encoding="utf-8-sig"))})
    arts, existing, stocks = fetch(ids={k[0] for k in keys})
    by_rev = {rev: links(rev, arts, existing, stocks) for rev in args.revs}
    art = {a[0]: a for a in arts}
    names = {}
    for n, s in sorted(stocks.items()):
        names.setdefault(s, n)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["no", "판정(O/X/?)", "근거", "news_id", "종목코드", "이름", "규칙", "낸 규칙", "기사 제목", "문맥"])
        for i, key in enumerate(keys, args.start):
            h = next((v[key] for v in by_rev.values() if key in v), None)
            _, title, body = art[key[0]]
            name = h.name if h else stocks.get(key[1], key[1])
            ctx = _context(title, name) if (h and h.rule == "title") else (_context(body, name) or _context(title, name))
            w.writerow([i, "", "", key[0], key[1], name, h.rule if h else "", " ".join(r for r in args.revs if key in by_rev[r]),
                        title, ctx])
    print({"pairs": len(keys), **{f"links_{r}": len(set(keys) & set(v)) for r, v in by_rev.items()}, "out": str(args.out)})
    return 0


def score(args) -> int:
    rows = list(csv.DictReader(args.set.open(encoding="utf-8-sig")))
    judged = {(int(r["news_id"]), r["종목코드"]): r["판정(O/X/?)"].strip().upper() for r in rows}
    arts, existing, stocks = fetch(ids={k[0] for k in judged})
    print(f"세트 {len(judged)}개: O {sum(v == 'O' for v in judged.values())} · X {sum(v == 'X' for v in judged.values())}"
          f" · 애매 {sum(v == '?' for v in judged.values())} · 미판정 {sum(v not in ('O', 'X', '?') for v in judged.values())}")
    true = {k for k, v in judged.items() if v == "O"}
    for rev in args.revs:
        made = set(links(rev, arts, existing, stocks)) & set(judged)
        o = sum(judged[k] == "O" for k in made)
        x = sum(judged[k] == "X" for k in made)
        missed = len(true - made)
        print(f"{rev:>10}: 낸 연결 {len(made)} (O {o} · X {x} · 애매 {len(made) - o - x}) · 정밀도 {o / max(1, o + x):.1%}"
              f" · 맞는 연결 {len(true)}개 중 놓침 {missed} ({missed / max(1, len(true)):.1%})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="코스피 태거 고정 평가 세트")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--since", required=True)
    b.add_argument("--until", required=True)
    b.add_argument("--revs", type=lambda s: s.split(","), required=True)
    b.add_argument("--n", type=int, default=200)
    b.add_argument("--seed", type=int, default=20261118)
    b.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("pairs")
    p.add_argument("--pairs", type=Path, required=True, help="news_id,symbol 열이 있는 csv")
    p.add_argument("--revs", type=lambda s: s.split(","), required=True)
    p.add_argument("--start", type=int, default=1, help="no 시작 번호")
    p.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--set", type=Path, required=True)
    s.add_argument("--revs", type=lambda s: s.split(","), required=True)
    args = ap.parse_args(argv)
    return {"build": build, "pairs": pairs, "score": score}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
