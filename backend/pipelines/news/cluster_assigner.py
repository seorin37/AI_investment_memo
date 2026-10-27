"""뉴스 중복 묶음 배정. 임베딩이 있고 아직 묶음이 없는 기사를 발행 순서대로 하나씩 배정한다.

  python -m backend.pipelines.news.cluster_assigner                 # 미배정 기사 전부 배정
  python -m backend.pipelines.news.cluster_assigner --limit 200     # 200건만
  python -m backend.pipelines.news.cluster_assigner --report 15     # 배정 후 큰 묶음 15개 출력
테스트 DB에서는 scripts/with_test_db.sh 를 앞에 붙여 실행한다.

흐름 (기사 1건마다, 한 트랜잭션)
  1. pgvector로 발행시각 ±window 안의 '이미 배정된' 기사 중 가장 가까운 candidates건을 찾는다.
  2. 그 기사들이 속한 묶음의 소속 기사 전부를 불러 clustering.choose_cluster로 판정한다.
  3. 합류하면 소속을 추가하고 묶음 정보(기사 수·발행 범위·대표)를 갱신, 아니면 새 묶음을 만든다.
한 번 배정한 소속은 바꾸지 않는다. 같은 DB에서 배정이 동시에 돌지 않도록 advisory lock을 잡는다.
"""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from .clustering import (Candidate, ClusterParams, Member, RepresentativeInfo,
                         choose_cluster, is_standalone_title, pick_representative)

log = logging.getLogger("cluster_assigner")

ADVISORY_LOCK_KEY = 0x4E455753434C  # "NEWSCL"
VARIANTS = ("hybrid", "dense")
HNSW_EF_SEARCH = 100   # 후보 검색 시 HNSW가 훑는 폭. candidates보다 넉넉해야 시간 조건으로 걸러져도 후보가 남는다


@dataclass
class AssignStats:
    processed: int = 0
    joined: int = 0
    created: int = 0
    seconds: float = 0.0
    skipped_locked: bool = False

    def as_dict(self) -> dict:
        return {"processed": self.processed, "joined": self.joined, "created": self.created,
                "seconds": round(self.seconds, 1), "skipped_locked": self.skipped_locked}


def _vec(value):
    """pgvector가 돌려준 Vector를 numpy 배열로 바꾼다 (계산 모듈은 숫자 배열만 받는다)."""
    return value.to_numpy() if hasattr(value, "to_numpy") else value


def _variant(variant: str) -> str:
    # 부분 HNSW 인덱스(WHERE variant='hybrid')를 쓰려면 SQL에 문자열로 들어가야 하므로 허용값만 받는다.
    if variant not in VARIANTS:
        raise ValueError(f"variant는 {VARIANTS} 중 하나여야 합니다")
    return variant


def pending_articles(conn, variant: str = "hybrid", limit: int | None = None) -> list[tuple]:
    """(news_id, published_at, dense, title) — 임베딩은 있고 아직 묶음이 없는 기사, 발행 순서대로."""
    sql = f"""
        SELECT a.id, a.published_at, v.dense, a.title
        FROM news_articles a
        JOIN news_embedding_variants v ON v.news_id = a.id AND v.variant = '{_variant(variant)}'
        WHERE NOT EXISTS (SELECT 1 FROM news_cluster_members m WHERE m.news_id = a.id)
        ORDER BY a.published_at, a.id"""
    params: list = []
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def candidate_cluster_ids(conn, member: Member, params: ClusterParams, variant: str = "hybrid") -> list[int]:
    """새 기사와 가장 가까운 '이미 배정된' 기사 candidates건이 속한 묶음 id (중복 제거, 가까운 순)."""
    sql = f"""
        SELECT m.cluster_id
        FROM news_embedding_variants v
        JOIN news_cluster_members m ON m.news_id = v.news_id
        JOIN news_articles a ON a.id = v.news_id
        WHERE v.variant = '{_variant(variant)}'
          AND a.published_at BETWEEN %(lo)s AND %(hi)s
        ORDER BY v.dense <=> %(vec)s
        LIMIT %(k)s"""
    with conn.cursor() as cur:
        cur.execute(sql, {"lo": member.published_at - params.window, "hi": member.published_at + params.window,
                          "vec": member.dense, "k": params.candidates})
        seen: dict[int, None] = {}
        for (cluster_id,) in cur.fetchall():
            seen.setdefault(cluster_id, None)
        return list(seen)


def load_candidates(conn, cluster_ids: list[int], variant: str = "hybrid") -> list[Candidate]:
    if not cluster_ids:
        return []
    sql = f"""
        SELECT m.cluster_id, m.news_id, a.published_at, v.dense, a.title
        FROM news_cluster_members m
        JOIN news_articles a ON a.id = m.news_id
        JOIN news_embedding_variants v ON v.news_id = m.news_id AND v.variant = '{_variant(variant)}'
        WHERE m.cluster_id = ANY(%s)
        ORDER BY m.cluster_id, m.news_id"""
    grouped: dict[int, list[Member]] = {cid: [] for cid in cluster_ids}
    with conn.cursor() as cur:
        cur.execute(sql, (cluster_ids,))
        for cluster_id, news_id, published_at, dense, title in cur.fetchall():
            grouped[cluster_id].append(Member(news_id, published_at, _vec(dense), is_standalone_title(title)))
    return [Candidate(cid, tuple(members)) for cid, members in grouped.items()]


def _representative(cur, cluster_id: int) -> int | None:
    cur.execute("""
        SELECT a.id, a.published_at, s.code, a.summary
        FROM news_cluster_members m
        JOIN news_articles a ON a.id = m.news_id
        LEFT JOIN news_sources s ON s.id = a.source_id
        WHERE m.cluster_id = %s""", (cluster_id,))
    rows = cur.fetchall()
    return pick_representative([RepresentativeInfo(*r) for r in rows]) if rows else None


def _refresh_cluster(cur, cluster_id: int) -> None:
    """소속 기사로부터 기사 수·발행 범위·대표를 다시 계산한다. 소속이 없으면 묶음을 지운다."""
    cur.execute("""
        SELECT count(*), min(a.published_at), max(a.published_at)
        FROM news_cluster_members m JOIN news_articles a ON a.id = m.news_id
        WHERE m.cluster_id = %s""", (cluster_id,))
    count, first, last = cur.fetchone()
    if count == 0:
        cur.execute("DELETE FROM news_clusters WHERE id = %s", (cluster_id,))
        return
    cur.execute("""
        UPDATE news_clusters
        SET article_count = %s, first_published_at = %s, last_published_at = %s,
            representative_news_id = %s, updated_at = now()
        WHERE id = %s""", (count, first, last, _representative(cur, cluster_id), cluster_id))


def assign_one(conn, member: Member, params: ClusterParams, variant: str = "hybrid") -> tuple[int, bool]:
    """기사 1건을 배정하고 (묶음 id, 기존 묶음 합류 여부)를 돌려준다. 호출자가 커밋한다."""
    candidates = load_candidates(conn, candidate_cluster_ids(conn, member, params, variant), variant)
    decision = choose_cluster(member, candidates, params)
    with conn.cursor() as cur:
        if decision.cluster_id is None:
            cur.execute("""
                INSERT INTO news_clusters (representative_news_id, article_count, first_published_at, last_published_at)
                VALUES (%s, 1, %s, %s) RETURNING id""", (member.news_id, member.published_at, member.published_at))
            cluster_id = cur.fetchone()[0]
        else:
            cluster_id = decision.cluster_id
        cur.execute("""
            INSERT INTO news_cluster_members (news_id, cluster_id, similarity, method_version)
            VALUES (%s, %s, %s, %s)""", (member.news_id, cluster_id, decision.min_similarity, params.method_version))
        if decision.cluster_id is not None:
            _refresh_cluster(cur, cluster_id)
    return cluster_id, decision.cluster_id is not None


def repair_clusters(conn) -> int:
    """30일 정리로 소속 기사가 지워진 묶음의 기사 수·대표를 바로잡고, 빈 묶음은 지운다."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.id FROM news_clusters c
            LEFT JOIN (SELECT cluster_id, count(*) n FROM news_cluster_members GROUP BY 1) m ON m.cluster_id = c.id
            WHERE c.representative_news_id IS NULL OR c.article_count <> coalesce(m.n, 0)""")
        stale = [r[0] for r in cur.fetchall()]
        for cluster_id in stale:
            _refresh_cluster(cur, cluster_id)
    return len(stale)


def assign_pending(conn, params: ClusterParams = ClusterParams(), variant: str = "hybrid",
                   limit: int | None = None) -> AssignStats:
    """미배정 기사를 모두 배정한다. 다른 곳에서 배정 중이면 아무것도 하지 않는다.

    conn은 autocommit=False여야 한다. 기사 1건마다 커밋하므로 중간에 멈춰도 다음 실행이 이어서 처리한다.
    """
    from pgvector.psycopg import register_vector
    register_vector(conn)
    stats = AssignStats()
    started = time.monotonic()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        locked = cur.fetchone()[0]
    conn.commit()
    if not locked:
        log.warning("다른 곳에서 묶음 배정이 실행 중입니다. 이번에는 건너뜁니다.")
        stats.skipped_locked = True
        return stats
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH}")
        repaired = repair_clusters(conn)
        conn.commit()
        if repaired:
            log.info("묶음 정리: %d개", repaired)
        for news_id, published_at, dense, title in pending_articles(conn, variant, limit):
            member = Member(news_id, published_at, _vec(dense), is_standalone_title(title))
            try:
                _, joined = assign_one(conn, member, params, variant)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            stats.processed += 1
            stats.joined += joined
            stats.created += not joined
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        conn.commit()
        stats.seconds = time.monotonic() - started
    log.info("묶음 배정 %d건: 기존 묶음 합류 %d, 새 묶음 %d, %.1f초",
             stats.processed, stats.joined, stats.created, stats.seconds)
    return stats


def report(conn, top: int = 10) -> dict:
    """묶음 현황 요약과 큰 묶음 상위 top개 (제목 포함)."""
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*), count(*) FILTER (WHERE article_count > 1),
                              coalesce(sum(article_count) FILTER (WHERE article_count > 1), 0),
                              coalesce(sum(article_count), 0) FROM news_clusters""")
        clusters, multi, in_multi, total = cur.fetchone()
        cur.execute("SELECT article_count, count(*) FROM news_clusters GROUP BY 1 ORDER BY 1")
        sizes = dict(cur.fetchall())
        cur.execute("""
            SELECT c.id, c.article_count, s.name, a.title, m.similarity
            FROM (SELECT id, article_count FROM news_clusters WHERE article_count > 1
                  ORDER BY article_count DESC, id LIMIT %s) c
            JOIN news_cluster_members m ON m.cluster_id = c.id
            JOIN news_articles a ON a.id = m.news_id
            LEFT JOIN news_sources s ON s.id = a.source_id
            ORDER BY c.article_count DESC, c.id, a.published_at""", (top,))
        groups: dict[int, list] = {}
        for cid, _, source, title, sim in cur.fetchall():
            groups.setdefault(cid, []).append((source, title, sim))
    return {"clusters": clusters, "multi_clusters": multi, "articles_in_multi": in_multi,
            "articles": total, "hidden_by_folding": in_multi - multi, "size_counts": sizes, "top": groups}


def main(argv=None) -> int:
    import psycopg
    from ..common.db import get_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 중복 묶음 배정")
    ap.add_argument("--variant", choices=VARIANTS, default="hybrid")
    ap.add_argument("--limit", type=int, help="이번에 배정할 최대 기사 수")
    ap.add_argument("--threshold", type=float, default=ClusterParams.threshold)
    ap.add_argument("--window-hours", type=int, default=48)
    ap.add_argument("--report", type=int, metavar="N", help="배정 후 큰 묶음 N개를 출력")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
    params = ClusterParams(threshold=args.threshold, window=timedelta(hours=args.window_hours))
    with psycopg.connect(dsn) as conn:
        log.info("접속: %s:%s/%s, 규칙 %s", conn.info.host, conn.info.port, conn.info.dbname, params.method_version)
        stats = assign_pending(conn, params, args.variant, args.limit)
        if args.report:
            r = report(conn, args.report)
            print(f"\n묶음 {r['clusters']}개 / 기사 {r['articles']}건 — 2건 이상 묶음 {r['multi_clusters']}개"
                  f"(기사 {r['articles_in_multi']}건), 접기로 줄어드는 기사 {r['hidden_by_folding']}건")
            print("묶음 크기별 개수:", r["size_counts"])
            for cid, rows in r["top"].items():
                print(f"\n[묶음 {cid}] {len(rows)}건")
                for source, title, sim in rows:
                    print(f"  {'첫 기사' if sim is None else f'{sim:.3f}':>8}  {source}  {title}")
    return 1 if stats.skipped_locked else 0


if __name__ == "__main__":
    raise SystemExit(main())
