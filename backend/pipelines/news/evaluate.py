"""dense / hybrid 가중치 비교 평가 (Recall@k, MRR, nDCG@k).

같은 기사 풀에서 질의마다 dense 점수와 sparse 점수를 한 번만 계산하고,
가중치와 정규화 방식을 바꿔 가며 순위를 다시 매겨 비교한다. (임베딩을 다시 만들 필요 없다.)
dense만 쓰는 것은 가중치 1:0, sparse만 쓰는 것은 0:1이다.

정답 파일(CSV, UTF-8): 헤더 query_id,query,relevant_urls
    relevant_urls 는 정답 기사 URL을 | 로 이어 쓴다. (DB마다 기사 id가 달라서 URL로 적는다.)

사용 예:
    # 1) 라벨링용 후보 기사 목록 내보내기
    python -m backend.pipelines.news.evaluate --export-pool pool.csv --date-from 2026-10-21 --date-to 2026-10-21
    # 2) 평가 (기본: 전체 기사에서 검색. --only-tagged: 종목이 연결된 기사만 검색)
    python -m backend.pipelines.news.evaluate --queries queries.csv --date-from 2026-10-21 --date-to 2026-10-23
    python -m backend.pipelines.news.evaluate --queries queries.csv --date-from 2026-10-21 --date-to 2026-10-23 --only-tagged
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .rss import KST, UTC, normalize_url
from .scoring import dense_score, sparse_score

DEFAULT_WEIGHTS = ["1:0", "0.9:0.1", "0.7:0.3", "0.5:0.5", "0.3:0.7", "0:1"]
NORMS = ("none", "sparse-minmax", "minmax")


@dataclass
class Doc:
    id: int
    url: str
    title: str
    dense: list[float]
    sparse: dict[str, float]


# ---------------------------------------------------------------- 점수·정규화

def parse_weight(text: str) -> tuple[float, float]:
    d, s = text.split(":")
    return float(d), float(s)


def minmax(values: list[float]) -> list[float]:
    """질의 하나에 대한 점수들을 0~1로 맞춘다. 모두 같으면 0."""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def combine(dense: list[float], sparse: list[float], w: tuple[float, float], norm: str) -> list[float]:
    """질의 하나의 dense/sparse 점수 목록을 정규화하고 가중합한다."""
    if norm == "minmax":
        dense, sparse = minmax(dense), minmax(sparse)
    elif norm == "sparse-minmax":
        sparse = minmax(sparse)
    elif norm != "none":
        raise ValueError(f"알 수 없는 정규화 방식: {norm}")
    return [w[0] * d + w[1] * s for d, s in zip(dense, sparse)]


def rank(scores: list[float]) -> list[int]:
    """점수가 높은 순서의 인덱스. 동점이면 앞 인덱스가 먼저."""
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


# ---------------------------------------------------------------- 지표

def recall_at_k(ranked_urls: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked_urls[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked_urls: list[str], relevant: set[str]) -> float:
    for pos, url in enumerate(ranked_urls, start=1):
        if url in relevant:
            return 1.0 / pos
    return 0.0


def ndcg_at_k(ranked_urls: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(pos + 1) for pos, url in enumerate(ranked_urls[:k], start=1) if url in relevant)
    ideal = sum(1.0 / math.log2(pos + 1) for pos in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def evaluate(queries: list[dict], docs: list[Doc], encoded: list[tuple[list[float], dict[str, float]]],
             weights: list[tuple[float, float]], norms: list[str], ks: list[int]) -> list[dict]:
    """queries[i]에 encoded[i](질의의 dense, sparse)가 대응한다. 가중치·정규화 조합별 평균 지표를 돌려준다."""
    urls = [d.url for d in docs]
    per_query = []
    for q, (qd, qs) in zip(queries, encoded):
        # 정답은 질문마다 정해 둔 전체를 쓴다. 검색 풀에 없는 정답(예: 태그가 없어 --only-tagged에서 빠진 기사)은
        # 지우지 않고 찾지 못한 것으로 계산해야 검색 방식끼리 공정하게 비교된다.
        relevant = set(q["relevant"])
        if not relevant:
            continue  # 정답이 하나도 적혀 있지 않은 질문만 뺀다
        per_query.append((relevant, [dense_score(qd, d.dense) for d in docs],
                          [sparse_score(qs, d.sparse) for d in docs]))
    rows = []
    for norm in norms:
        for w in weights:
            acc = {f"Recall@{k}": 0.0 for k in ks}
            acc.update({f"nDCG@{k}": 0.0 for k in ks})
            acc["MRR"] = 0.0
            for relevant, dsc, ssc in per_query:
                ranked = [urls[i] for i in rank(combine(dsc, ssc, w, norm))]
                for k in ks:
                    acc[f"Recall@{k}"] += recall_at_k(ranked, relevant, k)
                    acc[f"nDCG@{k}"] += ndcg_at_k(ranked, relevant, k)
                acc["MRR"] += reciprocal_rank(ranked, relevant)
            n = len(per_query) or 1
            rows.append({"norm": norm, "weight": f"{w[0]:g}:{w[1]:g}", "queries": len(per_query),
                         **{k: v / n for k, v in acc.items()}})
    return rows


# ---------------------------------------------------------------- 입출력

def kst_range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=KST).astimezone(UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=KST).astimezone(UTC)
    return start, end


def load_pool(conn, since: datetime, until: datetime, only_tagged: bool = False) -> list[Doc]:
    """검색 대상 기사 풀. only_tagged면 종목이 연결된 기사만(종목 필터 있는 검색)."""
    tagged = "AND EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)" if only_tagged else ""
    with conn.cursor() as cur:
        cur.execute(f"""SELECT a.id, a.url, a.title, v.dense::text, v.sparse
                       FROM news_embedding_variants v JOIN news_articles a ON a.id = v.news_id
                       WHERE v.variant = 'hybrid' AND a.published_at >= %s AND a.published_at < %s
                       {tagged}
                       ORDER BY a.id""", (since, until))
        return [Doc(i, u, t, json.loads(d), s or {}) for i, u, t, d, s in cur.fetchall()]


def labeled_urls_missing_in_db(conn, queries: list[dict]) -> set[str]:
    """정답으로 적었지만 DB에 아예 없는 URL (오타, 삭제된 기사). 어떤 검색으로도 찾을 수 없다."""
    labeled = sorted({u for q in queries for u in q["relevant"]})
    if not labeled:
        return set()
    with conn.cursor() as cur:
        cur.execute("SELECT url FROM news_articles WHERE url = ANY(%s)", (labeled,))
        return set(labeled) - {r[0] for r in cur.fetchall()}


def pool_coverage(queries: list[dict], docs: list[Doc]) -> list[tuple[str, int, int]]:
    """질문별로 (query_id, 정답 수, 이 검색 풀에 들어 있는 정답 수). 풀에 없는 정답은 실패로 계산된다."""
    in_pool = {d.url for d in docs}
    return [(q["id"], len(q["relevant"]), len(q["relevant"] & in_pool)) for q in queries]


def load_queries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{"id": r["query_id"], "query": r["query"],
                 "relevant": {normalize_url(u) for u in r["relevant_urls"].split("|") if u.strip()}}
                for r in csv.DictReader(f)]


def export_pool(conn, since: datetime, until: datetime, out: Path) -> int:
    with conn.cursor() as cur:
        cur.execute("""SELECT a.id, a.url, a.title, coalesce(a.summary, ''), a.published_at,
                              coalesce((SELECT string_agg(s.symbol, '|' ORDER BY s.symbol)
                                        FROM news_stocks s WHERE s.news_id = a.id), '')
                       FROM news_articles a
                       WHERE a.published_at >= %s AND a.published_at < %s ORDER BY a.published_at""", (since, until))
        rows = cur.fetchall()
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "url", "title", "summary", "published_at", "symbols"])
        w.writerows(rows)
    return len(rows)


def print_table(rows: list[dict]) -> None:
    cols = [c for c in rows[0] if c not in ("norm", "weight", "queries")]
    print(f"질의 {rows[0]['queries']}개")
    print("norm".ljust(14), "dense:sparse".ljust(13), *(c.rjust(10) for c in cols))
    for r in rows:
        print(r["norm"].ljust(14), r["weight"].ljust(13), *(f"{r[c]:.4f}".rjust(10) for c in cols))


def main(argv=None) -> int:
    from ..common.db import get_read_dsn, load_env
    ap = argparse.ArgumentParser(description="dense/hybrid 가중치 비교 평가")
    ap.add_argument("--queries", type=Path, help="정답 CSV (query_id,query,relevant_urls)")
    ap.add_argument("--export-pool", type=Path, help="라벨링용 기사 목록을 이 CSV로 내보내고 끝낸다")
    today = datetime.now(KST).date()
    ap.add_argument("--date-from", type=date.fromisoformat, default=today)
    ap.add_argument("--date-to", type=date.fromisoformat, default=today)
    ap.add_argument("--weights", nargs="+", default=DEFAULT_WEIGHTS, help='예: 1:0 0.7:0.3 0:1')
    ap.add_argument("--norms", nargs="+", default=list(NORMS), choices=NORMS)
    ap.add_argument("--ks", nargs="+", type=int, default=[3, 5, 10])
    ap.add_argument("--only-tagged", action="store_true",
                    help="종목이 연결된 기사만 검색 대상으로 한다 (없으면 전체 기사). 두 방식을 따로 돌려 비교한다")
    ap.add_argument("--csv", type=Path, help="결과 표를 CSV로도 저장")
    args = ap.parse_args(argv)

    import psycopg
    load_env()
    dsn = get_read_dsn()
    if not dsn:
        print("DB 접속 정보가 없습니다.", file=sys.stderr)
        return 1
    since, until = kst_range(args.date_from, args.date_to)
    with psycopg.connect(dsn) as conn:
        if args.export_pool:
            print(f"기사 {export_pool(conn, since, until, args.export_pool)}건을 {args.export_pool}에 저장했습니다.")
            return 0
        if not args.queries:
            print("--queries 또는 --export-pool 이 필요합니다.", file=sys.stderr)
            return 1
        docs = load_pool(conn, since, until, args.only_tagged)
        queries = load_queries(args.queries)
        missing = labeled_urls_missing_in_db(conn, queries)
    if not docs:
        print("해당 기간에 hybrid 임베딩된 기사가 없습니다.", file=sys.stderr)
        return 1
    if missing:
        # DB에 없는 URL은 어떤 검색 방식으로도 못 찾으므로 정답에서 빼되, 오타나 삭제를 고치도록 알린다.
        print(f"경고: DB에 없는 정답 URL {len(missing)}건을 정답에서 뺍니다 (오타나 삭제된 기사인지 확인하세요):",
              file=sys.stderr)
        for u in sorted(missing):
            print("  ", u, file=sys.stderr)
        for q in queries:
            q["relevant"] -= missing
    lost = [(qid, n, k) for qid, n, k in pool_coverage(queries, docs) if k < n]
    if lost:
        print(f"참고: 정답 중 이 검색 풀에 없는 것이 있는 질문 {len(lost)}개. 못 찾은 것으로 계산됩니다 "
              "(기간 밖이거나 임베딩이 없거나 --only-tagged에서 빠진 기사).", file=sys.stderr)
        for qid, n, k in lost[:10]:
            print(f"   {qid}: 정답 {n}건 중 풀에 {k}건", file=sys.stderr)
    from .embedder import make_bge_m3_encoder
    encode = make_bge_m3_encoder("hybrid")
    encoded = [(d, s or {}) for d, s in encode([q["query"] for q in queries])]
    rows = evaluate(queries, docs, encoded, [parse_weight(w) for w in args.weights], args.norms, args.ks)
    if not rows or rows[0]["queries"] == 0:
        print("정답 기사가 풀에 있는 질의가 없습니다. 기간과 URL을 확인하세요.", file=sys.stderr)
        return 1
    print(f"기사 풀 {len(docs)}건 ({'종목 연결 기사만' if args.only_tagged else '전체 기사'})")
    print_table(rows)
    if args.csv:
        with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
