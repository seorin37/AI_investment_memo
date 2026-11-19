"""대형사 별칭 조사 (읽기 전용, 2026-11-19): 종목명과 기사 표기가 달라 코스피 태거 태그가 적은 곳을 찾는다.

    python -m backend.pipelines.news.alias_survey --since 2026-10-20 --until 2026-11-20 --top 50 --out eval/news_tagging/alias_survey_20261119.csv

- 시가총액 상위 N개(보통주, 종목별 최근 10일 안 마지막 market_cap)마다 기간 안 태그 기사 수(news_stocks 아무 score)와
  후보 표기(CANDIDATES, 종목명 포함)가 제목·본문에 나온 기사 수, 그중 이미 그 종목 태그가 있는 기사 수를 센다.
- 표기마다 바로 뒤에 붙은 글자(최대 6자)를 세어 다른 회사로 헷갈릴 표기("포스코인터내셔널", "신한은행")를 보인다.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# 종목코드 → 종목명 말고 기사에 나올 만한 표기 (조사용 후보. 실제 별칭은 configs/stock_aliases.yaml)
CANDIDATES: dict[str, list[str]] = {
    "005490": ["포스코홀딩스", "포스코", "POSCO", "포스코그룹"],
    "010950": ["에쓰오일", "S-OIL", "에쓰-오일", "S오일", "에스오일", "S-oil"],
    "018260": ["삼성SDS", "삼성 SDS", "삼성에스디에스"],
    "055550": ["신한금융지주", "신한금융", "신한금융그룹", "신한은행", "신한"],
    "086790": ["하나금융", "하나금융그룹", "하나은행"],
    "316140": ["우리금융", "우리금융그룹", "우리은행"],
    "138040": ["메리츠금융", "메리츠"],
    "105560": ["KB금융그룹", "KB국민은행", "국민은행"],
    "010120": ["LS일렉트릭", "LS일렉", "LS 일렉트릭"],
    "009540": ["한국조선해양"],
    "267260": ["현대일렉트릭"],
    "329180": ["현대중공업"],
    "086280": ["글로비스"],
    "015760": ["한전", "한국전력공사"],
    "000270": ["기아자동차", "기아차"],
    "012330": ["모비스"],
    "028050": ["삼성이앤에이", "삼성엔지니어링"],
    "024110": ["IBK기업은행", "IBK"],
    "017670": ["SKT"],
    "096770": ["SK이노"],
    "373220": ["LG엔솔"],
    "000660": ["하이닉스"],
    "207940": ["삼성바이오"],
    "042700": ["한미"],
    "003670": ["포스코퓨처엠"],
}

TOP_SQL = """SELECT DISTINCT ON (p.symbol) p.symbol, s.name, p.market_cap
FROM prices_daily p JOIN stocks s USING (symbol)
WHERE p.trade_date >= %(since_d)s::date - 10 AND p.market_cap IS NOT NULL AND right(p.symbol, 1) = '0'
ORDER BY p.symbol, p.trade_date DESC"""
ARTICLES_SQL = """SELECT a.id, a.title, coalesce(b.body, '') FROM news_articles a
LEFT JOIN news_article_bodies b ON b.news_id = a.id
WHERE a.published_at >= %(since)s AND a.published_at < %(until)s"""
TAGS_SQL = """SELECT ns.news_id, ns.symbol FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
WHERE a.published_at >= %(since)s AND a.published_at < %(until)s"""


def survey(articles, tags: dict[int, set[str]], symbol: str, form: str, k: int = 8) -> dict:
    """한 표기: 제목·본문에 나온 기사 수, 그중 태그 있는 수, 바로 뒤 글자 상위."""
    pat = re.compile(re.escape(form) + r"([가-힣A-Za-z0-9&]{0,6})")
    title_n = title_tagged = body_n = body_tagged = 0
    tails = Counter()
    for nid, title, body in articles:
        in_title, in_body = form in title, form in body
        if not (in_title or in_body):
            continue
        tagged = symbol in tags.get(nid, ())
        if in_title:
            title_n += 1
            title_tagged += tagged
        if in_body:
            body_n += 1
            body_tagged += tagged
        for m in pat.finditer(title + "\n" + body):
            tails[m.group(1)[:6]] += 1
    return {"title": title_n, "title_tagged": title_tagged, "body": body_n, "body_tagged": body_tagged,
            "tails": "; ".join(f"{form}{t or '∅'}:{n}" for t, n in tails.most_common(k))}


def links_diff(conn, old: Path, new: Path, out: Path, k: int = 4, seed: int = 7) -> None:
    """stock_tagger --links-out 두 개(이전 설정·새 설정)의 차이: 새 설정에서만 나오는 연결의 종목별 건수·규칙·예시.
    예시 문맥은 지금 설정(configs/stock_aliases.yaml)으로 그 기사를 다시 맞춰 얻는다."""
    import random

    from .stock_tagger import load_rules, match_article

    read = lambda p: {(int(r["news_id"]), r["symbol"]) for r in csv.DictReader(p.open(encoding="utf-8"))}  # noqa: E731
    added, removed = sorted(read(new) - read(old)), read(old) - read(new)
    rules = load_rules(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, name FROM stocks")
        stock_name = dict(cur.fetchall())
        cur.execute("""SELECT a.id, a.title, b.body FROM news_articles a LEFT JOIN news_article_bodies b ON b.news_id = a.id
                       WHERE a.id = ANY(%s)""", ([nid for nid, _ in added],))
        arts = {nid: (t, b) for nid, t, b in cur.fetchall()}
    rows = []
    for nid, sym in added:
        title, body = arts[nid]
        h = next((h for h in match_article(title, body, rules) if h.symbol == sym), None)
        rows.append({"판정(O/X)": "", "symbol": sym, "stock": stock_name.get(sym, sym), "name": h.name if h else "",
                     "rule": h.rule if h else "", "count": h.count if h else "", "title": title,
                     "context": h.context if h else "", "news_id": nid})
    print(f"새 설정에서만: {len(added)}개 / 이전 설정에서만: {len(removed)}개")
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r["symbol"]].append(r)
    rng = random.Random(seed)
    for sym, rs in sorted(by_sym.items(), key=lambda kv: -len(kv[1])):
        print(f"\n## {rs[0]['stock']}({sym}) {len(rs)}개  규칙 {dict(Counter(r['rule'] for r in rs))}  "
              f"이름 {dict(Counter(r['name'] for r in rs))}")
        for r in rng.sample(rs, min(k, len(rs))):
            print(f"  - [{r['rule']}] {r['title'][:60]}\n      {r['context'][:110]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n→ {out}")


def config_diff(conn, old_config: Path, since, until) -> None:
    """기간 안 모든 기사를 이전 설정·지금 설정으로 맞춰, 지금 설정에서 빠지는 연결(기존 태그 포함)을 보인다."""
    from .stock_tagger import ARTICLES_SQL as ART, CONFIG_PATH, load_rules, match_article

    old, cur_rules = load_rules(conn, old_config), load_rules(conn, CONFIG_PATH)
    with conn.cursor() as cur:
        cur.execute(ART, {"since": since, "until": until})
        arts = cur.fetchall()
    lost, gained = [], Counter()
    for nid, title, body in arts:
        now = {h.symbol for h in match_article(title, body, cur_rules)}
        before = match_article(title, body, old)
        lost += [(nid, h, title) for h in before if h.symbol not in now]
        gained.update(s for s in now - {h.symbol for h in before})
    print(f"기사 {len(arts)}개: 지금 설정에서 새로 나오는 연결 {sum(gained.values())}개, 빠지는 연결 {len(lost)}개")
    for nid, h, title in lost:
        print(f"  - {h.name}({h.symbol}) [{h.rule}] {title[:60]}  | {h.context[:90]}  (news_id {nid})")


def main(argv=None) -> int:
    from ..common.db import get_read_dsn, load_env
    import psycopg
    from zoneinfo import ZoneInfo

    ap = argparse.ArgumentParser(description="대형사 별칭 조사 (읽기 전용)")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--forms", default="", help="쉼표 구분: 이 표기만 바로 뒤 글자 상위 30개를 본다 (종목 표 대신)")
    ap.add_argument("--links-diff", nargs=2, type=Path, metavar=("OLD", "NEW"),
                    help="stock_tagger --links-out 두 개의 차이 (새 설정에서만 나오는 연결 → --out csv)")
    ap.add_argument("--examples", type=int, default=4)
    ap.add_argument("--config-diff", type=Path, metavar="OLD_YAML",
                    help="이전 설정 파일과 지금 설정으로 기간 안 기사를 모두 맞춰 빠지는 연결을 본다 (--since·--until)")
    args = ap.parse_args(argv)
    load_env()
    if args.links_diff:
        with psycopg.connect(get_read_dsn()) as conn:
            conn.read_only = True
            links_diff(conn, *args.links_diff, args.out, k=args.examples)
        return 0
    kst = ZoneInfo("Asia/Seoul")
    p = {"since": datetime.fromisoformat(args.since).replace(tzinfo=kst),
         "until": datetime.fromisoformat(args.until).replace(tzinfo=kst), "since_d": args.until}
    if args.config_diff:
        with psycopg.connect(get_read_dsn()) as conn:
            conn.read_only = True
            config_diff(conn, args.config_diff, p["since"], p["until"])
        return 0
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            top = sorted(cur.execute(TOP_SQL, p).fetchall(), key=lambda r: -r[2])[:args.top]
            articles = cur.execute(ARTICLES_SQL, p).fetchall()
            tags: dict[int, set[str]] = defaultdict(set)
            for nid, sym in cur.execute(TAGS_SQL, p):
                tags[nid].add(sym)
    tag_n = Counter(s for syms in tags.values() for s in syms)
    if args.forms:
        for form in args.forms.split(","):
            r = survey(articles, tags, "", form, k=30)
            print(f"{form}: 제목 {r['title']} 본문 {r['body']}\n  {r['tails']}")
        return 0
    print(f"기사 {len(articles)}개, 상위 {len(top)}종목")
    rows = []
    for rank, (sym, name, mc) in enumerate(top, 1):
        for form in [name] + CANDIDATES.get(sym, []):
            r = survey(articles, tags, sym, form)
            rows.append({"rank": rank, "symbol": sym, "name": name, "cap_tn": round(float(mc) / 1e12, 1), "tagged_articles": tag_n[sym],
                         "form": form, **r})
            print(f"{rank:>2} {name}({sym}) 태그 {tag_n[sym]:>4} | {form:<10} 제목 {r['title']:>4}(태그 {r['title_tagged']:>4}) "
                  f"본문 {r['body']:>5}(태그 {r['body_tagged']:>4}) | {r['tails']}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
