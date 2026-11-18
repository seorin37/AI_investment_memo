"""BGE-M3 임베딩 적재. 지정한 기간(발행시각 기준)의 기사 중 아직 임베딩이 없는 것만 처리한다.

기본은 종목이 태깅된 기사만, include_untagged=True면 전체 기사(hourly --embed와 daily --include-untagged).

variant
  hybrid : dense + sparse 저장 (한 번의 forward로 둘 다 나온다)
  dense  : dense만 저장
임베딩 입력 = 제목 + 요약. 요약이 없거나 40자 미만이면 리드(news_article_leads, 최대 300자)로 보충한다.
리드 보충을 기다리는 기사(status='pending')는 임베딩을 미룬다. 제목만으로 먼저 임베딩되면 그 상태로
묶음에 배정되고, 배정은 바꾸지 않으므로 나중에 리드가 와도 고칠 수 없기 때문이다.
결과는 news_embedding_variants (alembic/versions/0006_news_embedding_variants.py)에 저장한다.

이미 제목만으로 임베딩된 기사에 리드가 생기면 한 번 다시 임베딩한다 (묶음 배정을 켜기 전에):
  python -m backend.pipelines.news.embedder --reembed-leads
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Callable

log = logging.getLogger("embedder")

MODEL_NAME = "BAAI/bge-m3"
BATCH = 16
SUMMARY_MIN_CHARS = 40   # 이보다 짧은 요약은 리드로 보충한다 (lead_fetcher와 같은 기준)
# encode(texts) -> list[(dense_vector, sparse_dict_or_None)]
Encoder = Callable[[list[str]], list[tuple[list[float], dict[str, float] | None]]]


def _patch_dtype_compat() -> None:
    """transformers 4.x에서 FlagEmbedding이 넘기는 dtype 인자를 torch_dtype으로 바꿔 준다.

    scripts/test_bge.py에서 팀이 쓰는 방식과 같다. transformers 5.x에서는 필요 없다.
    """
    from transformers import AutoModel
    if getattr(AutoModel.from_pretrained, "_dtype_compat", False):
        return
    original = AutoModel.from_pretrained

    def compatible(*args, **kwargs):
        if "dtype" in kwargs:
            kwargs["torch_dtype"] = kwargs.pop("dtype")
        return original(*args, **kwargs)

    compatible._dtype_compat = True
    AutoModel.from_pretrained = compatible


def make_bge_m3_encoder(variant: str, use_fp16: bool = False) -> Encoder:
    from FlagEmbedding import BGEM3FlagModel  # 무거워서 실제 실행할 때만 import
    _patch_dtype_compat()
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=use_fp16)
    want_sparse = variant == "hybrid"

    def encode(texts: list[str]):
        out = model.encode(texts, batch_size=BATCH, max_length=512,
                           return_dense=True, return_sparse=want_sparse, return_colbert_vecs=False)
        dense = out["dense_vecs"]
        sparse = out["lexical_weights"] if want_sparse else [None] * len(texts)
        # hybrid의 sparse는 NULL이면 안 되므로, 단어가 하나도 없는 결과는 None이 아니라 빈 사전으로 둔다.
        return [([float(x) for x in d], ({str(k): float(v) for k, v in s.items()} if s is not None else None))
                for d, s in zip(dense, sparse)]

    return encode


def to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8g}" for x in vec) + "]"


def summary_is_enough(summary: str | None) -> bool:
    return bool(summary and len(summary.strip()) >= SUMMARY_MIN_CHARS)


def embedding_text(title: str, summary: str | None, lead: str | None = None) -> str:
    """제목 + 요약. 요약이 부족하면 리드, 리드도 없으면 있는 요약 그대로, 둘 다 없으면 제목만."""
    body = summary if summary_is_enough(summary) else (lead or summary)
    return f"{title}\n{body}" if body else title


def _has_leads_table(conn) -> bool:
    # 0008 마이그레이션 전 DB에서도 지금처럼 동작하도록, 리드 테이블이 있을 때만 리드를 쓴다.
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('news_article_leads') IS NOT NULL")
        return bool(cur.fetchone()[0])


def pending_articles(conn, variant: str, since: datetime, until: datetime, limit: int | None = None,
                     include_untagged: bool = False):
    """임베딩할 기사 (id, 제목, 요약, 리드). 기본은 종목이 연결된 기사만, include_untagged면 전체 기사.

    리드 보충을 기다리는 기사(status='pending')는 빼고, 다음 주기에 다시 본다.
    """
    tagged = "" if include_untagged else "AND EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)"
    if _has_leads_table(conn):
        lead_col = "l.lead_text"
        lead_join = "LEFT JOIN news_article_leads l ON l.news_id = a.id AND l.status = 'ok'"
        lead_wait = "AND NOT EXISTS (SELECT 1 FROM news_article_leads w WHERE w.news_id = a.id AND w.status = 'pending')"
    else:
        lead_col, lead_join, lead_wait = "NULL", "", ""
    sql = f"""
        SELECT a.id, a.title, a.summary, {lead_col} FROM news_articles a
        {lead_join}
        WHERE a.published_at >= %s AND a.published_at < %s
          {tagged}
          {lead_wait}
          AND NOT EXISTS (SELECT 1 FROM news_embedding_variants v WHERE v.news_id = a.id AND v.variant = %s)
        ORDER BY a.id"""
    params: list = [since, until, variant]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _encode_safely(encode: Encoder, chunk: list) -> list:
    """묶음 전체가 실패하면 한 건씩 다시 시도해서, 문제 있는 기사만 건너뛴다.

    [(행, (dense, sparse) 또는 None)]을 돌려준다. 한 기사 때문에 나머지가 계속 막히는 일을 막는다.
    """
    try:
        return list(zip(chunk, encode([embedding_text(*row[1:]) for row in chunk])))
    except Exception as exc:
        log.warning("묶음 임베딩 실패(%s: %s). 한 건씩 다시 시도합니다.", type(exc).__name__, exc)
    out = []
    for row in chunk:
        try:
            out.append((row, encode([embedding_text(*row[1:])])[0]))
        except Exception as exc:
            log.error("임베딩 실패, 건너뜀: news_id=%s (%s: %s)", row[0], type(exc).__name__, exc)
            out.append((row, None))
    return out


def embed_window(conn, variant: str, encode: Encoder, since: datetime, until: datetime,
                 limit: int | None = None, include_untagged: bool = False) -> int:
    """새로 임베딩한 기사 수. 이미 해당 variant가 있는 기사는 건너뛴다(재실행 안전).

    실패한 기사는 저장하지 않으므로 다음 실행에서 다시 대상이 된다.
    처리 대상 수, 성공, 실패, 걸린 시간을 로그로 남긴다.
    """
    started = time.monotonic()
    rows = pending_articles(conn, variant, since, until, limit, include_untagged)
    done, failed = _encode_and_save(conn, variant, encode, rows, replace=False)
    if rows:
        log.info("임베딩 대상 %d건: 성공 %d, 실패 %d(다음 주기에 재시도), %.1f초",
                 len(rows), done, failed, time.monotonic() - started)
    return done


_INSERT_SQL = """INSERT INTO news_embedding_variants (news_id, variant, dense, sparse, model)
                 VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"""
_UPSERT_SQL = """INSERT INTO news_embedding_variants (news_id, variant, dense, sparse, model)
                 VALUES (%s, %s, %s, %s, %s)
                 ON CONFLICT (news_id, variant) DO UPDATE
                 SET dense = EXCLUDED.dense, sparse = EXCLUDED.sparse, model = EXCLUDED.model, embedded_at = now()"""


def _encode_and_save(conn, variant: str, encode: Encoder, rows: list, replace: bool) -> tuple[int, int]:
    """(저장 건수, 실패 건수). replace=True면 기존 임베딩을 덮어쓴다 (리드 재임베딩용)."""
    done = failed = 0
    for i in range(0, len(rows), BATCH):
        with conn.cursor() as cur:
            for row, result in _encode_safely(encode, rows[i:i + BATCH]):
                if result is None:
                    failed += 1
                    continue
                dense, sparse = result
                if variant == "hybrid" and sparse is None:
                    sparse = {}
                cur.execute(_UPSERT_SQL if replace else _INSERT_SQL,
                            (row[0], variant, to_vector_literal(dense),
                             json.dumps(sparse) if sparse is not None else None, MODEL_NAME))
                done += cur.rowcount
    return done, failed


def articles_to_reembed(conn, variant: str, limit: int | None = None) -> list:
    """리드가 생기기 전에 제목(또는 짧은 요약)만으로 임베딩된 기사 (id, 제목, 요약, 리드)."""
    if not _has_leads_table(conn):
        return []
    sql = f"""
        SELECT a.id, a.title, a.summary, l.lead_text
        FROM news_articles a
        JOIN news_article_leads l ON l.news_id = a.id AND l.status = 'ok'
        JOIN news_embedding_variants v ON v.news_id = a.id AND v.variant = %s
        WHERE (a.summary IS NULL OR char_length(btrim(a.summary)) < {SUMMARY_MIN_CHARS})
          AND v.embedded_at < coalesce(l.fetched_at, l.updated_at)
        ORDER BY a.id"""
    params: list = [variant]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def reembed_with_leads(conn, variant: str, encode: Encoder, limit: int | None = None) -> int:
    """리드로 보충된 기사를 다시 임베딩해 덮어쓴다. 다시 실행해도 이미 처리한 기사는 대상이 아니다.

    이미 묶음에 배정된 기사는 소속이 바뀌지 않으므로, 묶음 배정을 켜기 전에 실행해야 한다.
    """
    started = time.monotonic()
    rows = articles_to_reembed(conn, variant, limit)
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('news_cluster_members') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("SELECT count(*) FROM news_cluster_members WHERE news_id = ANY(%s)", ([r[0] for r in rows],))
            assigned = cur.fetchone()[0]
            if assigned:
                log.warning("재임베딩 대상 중 %d건은 이미 묶음에 배정돼 있어 소속은 바뀌지 않습니다.", assigned)
    done, failed = _encode_and_save(conn, variant, encode, rows, replace=True)
    log.info("리드 재임베딩 대상 %d건: 성공 %d, 실패 %d, %.1f초", len(rows), done, failed, time.monotonic() - started)
    return done


def main(argv=None) -> int:
    import argparse

    import psycopg
    from ..common.db import get_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 임베딩 보조 명령")
    ap.add_argument("--reembed-leads", action="store_true", required=True,
                    help="리드가 생기기 전에 임베딩된 기사를 리드를 넣어 다시 임베딩한다")
    ap.add_argument("--variant", choices=["dense", "hybrid"], default="hybrid")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
    with psycopg.connect(dsn, autocommit=True) as conn:
        if not articles_to_reembed(conn, args.variant, 1):
            log.info("다시 임베딩할 기사가 없습니다.")
            return 0
        reembed_with_leads(conn, args.variant, make_bge_m3_encoder(args.variant), args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
