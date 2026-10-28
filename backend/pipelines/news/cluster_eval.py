"""중복 묶음 기준값(threshold) 정하기: 경계 구간 기사 쌍을 뽑아 사람이 체크하고, 기준값별 정확도를 계산한다.

  python -m backend.pipelines.news.cluster_eval export eval/news_dedup/boundary_pairs_v2.csv   # 쌍 뽑기
  (엑셀로 열어 label 칸에 same / different / unsure 를 적는다)
  python -m backend.pipelines.news.cluster_eval score eval/news_dedup/boundary_pairs_v2.csv    # 기준값별 결과

뽑는 방법: 기사마다 48시간 안에서 가장 가까운 기사 몇 건을 찾고, dense 유사도가 0.60~0.95인 쌍만 남겨
유사도 구간(0.05 단위)마다 같은 수를 고른다. 기준이 '같은 사건(엄격)'이라 0.80 이상에도 다른 사건이
섞일 수 있어 높은 구간까지 본다. 고정 꼭지 제목(clustering.is_standalone_title)은 뺀다.
sparse_score는 BGE-M3 sparse(단어 겹침) 점수로, 나중에 dense+sparse 혼합을 비교할 때 쓴다.
쌍 단위 결과라 실제 묶음(묶음의 모든 기사와 비교)과는 조금 다를 수 있다. 기준값을 고르는 참고로 쓴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import random
from pathlib import Path

from .clustering import is_standalone_title

log = logging.getLogger("cluster_eval")

LOW, HIGH, STEP = 0.60, 0.95, 0.05     # 내보낼 유사도 범위와 구간 폭
SCORE_RANGE = (0.55, 0.95)             # score가 계산할 기준값 범위 (0.01 단위)
LABELS = {"same", "different", "unsure"}
MAX_FALSE_MERGE = 0.05      # 묶인 쌍 중 다른 사건 비율이 이 이하인 가장 낮은 기준을 추천한다
FIELDS = ["pair_id", "similarity", "sparse_score", "bucket", "same_cluster_now",
          "a_id", "a_source", "a_published", "a_title", "a_summary",
          "b_id", "b_source", "b_published", "b_title", "b_summary", "label", "note"]

PAIRS_SQL = """
SELECT a.id, b.id, b.sim, va.sparse, b.sparse
FROM news_articles a
JOIN news_embedding_variants va ON va.news_id = a.id AND va.variant = 'hybrid'
CROSS JOIN LATERAL (
    SELECT x.id, 1 - (vx.dense <=> va.dense) AS sim, vx.sparse
    FROM news_embedding_variants vx
    JOIN news_articles x ON x.id = vx.news_id
    WHERE vx.variant = 'hybrid' AND x.id <> a.id
      AND x.published_at BETWEEN a.published_at - interval '48 hours' AND a.published_at + interval '48 hours'
    ORDER BY vx.dense <=> va.dense
    LIMIT %(k)s
) b
WHERE b.sim >= %(low)s AND b.sim < %(high)s
"""

ARTICLE_SQL = """
SELECT a.id, s.name, a.published_at, a.title, a.summary, m.cluster_id
FROM news_articles a
LEFT JOIN news_sources s ON s.id = a.source_id
LEFT JOIN news_cluster_members m ON m.news_id = a.id
WHERE a.id = ANY(%s)
"""


def sparse_score(a, b) -> float:
    """BGE-M3 lexical 점수: 두 기사에 함께 나온 토큰 가중치의 곱의 합."""
    a = json.loads(a) if isinstance(a, str) else (a or {})
    b = json.loads(b) if isinstance(b, str) else (b or {})
    return float(sum(w * b[t] for t, w in a.items() if t in b))


def bucket_of(similarity: float) -> str:
    lo = math.floor(similarity / STEP + 1e-9) * STEP
    return f"{lo:.2f}-{lo + STEP:.2f}"


def sample_pairs(rows, per_bucket: int, seed: int = 20261028) -> list[tuple]:
    """(a, b, sim, sparse_a, sparse_b) 후보에서 중복 쌍을 없애고 구간마다 per_bucket개를 고른다."""
    unique = {}
    for a, b, sim, sa, sb in rows:
        key = (min(a, b), max(a, b))
        if key not in unique:
            unique[key] = (key[0], key[1], float(sim), sa if a == key[0] else sb, sb if a == key[0] else sa)
    by_bucket: dict[str, list[tuple]] = {}
    for row in sorted(unique.values()):
        by_bucket.setdefault(bucket_of(row[2]), []).append(row)
    rng = random.Random(seed)
    picked = []
    for bucket in sorted(by_bucket):
        rows_in = by_bucket[bucket]
        picked.extend(rng.sample(rows_in, min(per_bucket, len(rows_in))))
    return sorted(picked, key=lambda r: r[2])


def export_pairs(conn, path: Path, per_bucket: int = 15, k: int = 5, low: float = LOW, high: float = HIGH) -> dict:
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100")
        cur.execute(PAIRS_SQL, {"k": k, "low": low, "high": high})
        candidates = cur.fetchall()
        ids = sorted({i for r in candidates for i in r[:2]})
        cur.execute(ARTICLE_SQL, (ids,))
        info = {r[0]: r[1:] for r in cur.fetchall()}
    candidates = [r for r in candidates
                  if not is_standalone_title(info[r[0]][2]) and not is_standalone_title(info[r[1]][2])]
    picked = sample_pairs(candidates, per_bucket)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for n, (a, b, sim, sa, sb) in enumerate(picked, 1):
            ia, ib = info[a], info[b]
            same_now = ia[4] is not None and ia[4] == ib[4]
            w.writerow({
                "pair_id": n, "similarity": f"{sim:.4f}", "sparse_score": f"{sparse_score(sa, sb):.4f}",
                "bucket": bucket_of(sim), "same_cluster_now": "yes" if same_now else "no",
                "a_id": a, "a_source": ia[0], "a_published": ia[1].isoformat(timespec="minutes"),
                "a_title": ia[2], "a_summary": (ia[3] or "")[:120],
                "b_id": b, "b_source": ib[0], "b_published": ib[1].isoformat(timespec="minutes"),
                "b_title": ib[2], "b_summary": (ib[3] or "")[:120], "label": "", "note": "",
            })
    counts: dict[str, int] = {}
    for row in picked:
        counts[bucket_of(row[2])] = counts.get(bucket_of(row[2]), 0) + 1
    return {"candidates": len(candidates), "picked": len(picked), "by_bucket": counts, "path": str(path)}


def load_labels(path: Path) -> list[tuple[float, str]]:
    """(similarity, label). unsure와 빈칸은 뺀다. 알 수 없는 값은 오류."""
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            label = (row.get("label") or "").strip().lower()
            if not label or label == "unsure":
                continue
            if label not in LABELS:
                raise ValueError(f"pair_id={row.get('pair_id')}: label은 same / different / unsure 중 하나여야 합니다 ({label})")
            out.append((float(row["similarity"]), label))
    return out


def score(labels: list[tuple[float, str]], thresholds=None) -> list[dict]:
    """기준값마다: 묶이는 쌍(유사도 ≥ 기준) 중 다른 사건 비율(잘못 묶음), 같은 사건 중 놓친 비율."""
    lo, hi = SCORE_RANGE
    thresholds = thresholds or [round(lo + i * 0.01, 2) for i in range(round((hi - lo) / 0.01) + 1)]
    same_total = sum(1 for _, l in labels if l == "same")
    out = []
    for t in thresholds:
        merged = [l for s, l in labels if s >= t]
        wrong = sum(1 for l in merged if l == "different")
        caught = sum(1 for l in merged if l == "same")
        out.append({"threshold": t, "merged": len(merged), "false_merge": wrong / len(merged) if merged else 0.0,
                    "missed": 1 - caught / same_total if same_total else 0.0})
    return out


def recommend(results: list[dict], max_false_merge: float = MAX_FALSE_MERGE) -> float | None:
    return next((r["threshold"] for r in results if r["merged"] and r["false_merge"] <= max_false_merge), None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="중복 묶음 기준값 평가")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="경계 구간 기사 쌍을 CSV로 뽑는다 (DB 읽기만)")
    ex.add_argument("path", type=Path)
    ex.add_argument("--per-bucket", type=int, default=15, help="유사도 구간(0.05)마다 뽑을 쌍 수 (기본 15 → 7구간 105쌍)")
    ex.add_argument("--low", type=float, default=LOW)
    ex.add_argument("--high", type=float, default=HIGH)
    sc = sub.add_parser("score", help="사람이 체크한 CSV로 기준값별 결과 계산 (DB 없음)")
    sc.add_argument("path", type=Path)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "score":
        labels = load_labels(args.path)
        same = sum(1 for _, l in labels if l == "same")
        print(f"체크된 쌍 {len(labels)}개 (같은 사건 {same}, 다른 사건 {len(labels) - same})")
        print("기준값  묶이는 쌍  잘못 묶음  놓친 같은 사건")
        results = score(labels)
        for r in results:
            print(f" {r['threshold']:.2f}     {r['merged']:>3}      {r['false_merge']:6.1%}     {r['missed']:6.1%}")
        best = recommend(results)
        print(f"\n추천 기준값: {best:.2f} (잘못 묶음 {MAX_FALSE_MERGE:.0%} 이하 중 가장 낮은 값)" if best is not None
              else "\n잘못 묶음 5% 이하를 만족하는 기준값이 없습니다.")
        return 0

    import psycopg
    from ..common.db import get_dsn, load_env
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다.")
        return 1
    with psycopg.connect(dsn, options="-c default_transaction_read_only=on") as conn:
        log.info("접속: %s:%s/%s (읽기 전용)", conn.info.host, conn.info.port, conn.info.dbname)
        print(export_pairs(conn, args.path, args.per_bucket, low=args.low, high=args.high))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
