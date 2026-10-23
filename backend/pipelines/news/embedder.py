"""BGE-M3 임베딩 적재. 지정한 기간(발행시각 기준)의 기사 중 아직 임베딩이 없는 것만 처리한다.

기본은 종목이 태깅된 기사만, include_untagged=True면 전체 기사(hourly --embed와 daily --include-untagged).

variant
  hybrid : dense + sparse 저장 (한 번의 forward로 둘 다 나온다)
  dense  : dense만 저장
임베딩 입력 = 제목 + 요약. 결과는 news_embedding_variants (alembic/versions/0006_news_embedding_variants.py)에 저장한다.
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


def embedding_text(title: str, summary: str | None) -> str:
    return f"{title}\n{summary}" if summary else title


def pending_articles(conn, variant: str, since: datetime, until: datetime, limit: int | None = None,
                     include_untagged: bool = False):
    """임베딩할 기사. 기본은 종목이 연결된 기사만, include_untagged면 전체 기사."""
    tagged = "" if include_untagged else "AND EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)"
    sql = f"""
        SELECT a.id, a.title, a.summary FROM news_articles a
        WHERE a.published_at >= %s AND a.published_at < %s
          {tagged}
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
        return list(zip(chunk, encode([embedding_text(t, s) for _, t, s in chunk])))
    except Exception as exc:
        log.warning("묶음 임베딩 실패(%s: %s). 한 건씩 다시 시도합니다.", type(exc).__name__, exc)
    out = []
    for row in chunk:
        try:
            out.append((row, encode([embedding_text(row[1], row[2])])[0]))
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
    done = failed = 0
    for i in range(0, len(rows), BATCH):
        with conn.cursor() as cur:
            for (news_id, _, _), result in _encode_safely(encode, rows[i:i + BATCH]):
                if result is None:
                    failed += 1
                    continue
                dense, sparse = result
                if variant == "hybrid" and sparse is None:
                    sparse = {}
                cur.execute(
                    """INSERT INTO news_embedding_variants (news_id, variant, dense, sparse, model)
                       VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (news_id, variant, to_vector_literal(dense),
                     json.dumps(sparse) if sparse is not None else None, MODEL_NAME))
                done += cur.rowcount
    if rows:
        log.info("임베딩 대상 %d건: 성공 %d, 실패 %d(다음 주기에 재시도), %.1f초",
                 len(rows), done, failed, time.monotonic() - started)
    return done
