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
import math
import time
from datetime import datetime
from typing import Callable

log = logging.getLogger("embedder")

MODEL_NAME = "BAAI/bge-m3"
BATCH = 16
# encode(texts) -> list[(dense_vector, sparse_dict_or_None)]
Encoder = Callable[[list[str]], list[tuple[list[float], dict[str, float] | None]]]


class EmbeddingValidationError(ValueError):
    """입출력 개수나 벡터가 잘못된 경우. 재시도하거나 일부만 저장하지 않는다."""


def _check_batch_size(batch_size: int) -> None:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")


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


def make_bge_m3_encoder(variant: str, use_fp16: bool = False, *, batch_size: int = BATCH) -> Encoder:
    """모델은 한 번 로딩한다. 반환 함수의 batch_size를 embed_window와 공유한다."""
    _check_batch_size(batch_size)
    from FlagEmbedding import BGEM3FlagModel  # 무거워서 실제 실행할 때만 import
    _patch_dtype_compat()
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=use_fp16)
    want_sparse = variant == "hybrid"

    def encode(texts: list[str]):
        _check_batch_size(encode.batch_size)
        out = model.encode(texts, batch_size=encode.batch_size, max_length=512,
                           return_dense=True, return_sparse=want_sparse, return_colbert_vecs=False)
        try:
            dense = out["dense_vecs"]
            sparse = out["lexical_weights"] if want_sparse else [None] * len(texts)
            if len(dense) != len(texts) or len(sparse) != len(texts):
                raise EmbeddingValidationError("Model output count does not match input count")
            # 단어가 없는 sparse의 빈 사전은 유지한다. hybrid의 None은 저장 전 검증에서 거부한다.
            return [([float(x) for x in d], ({str(k): float(v) for k, v in s.items()} if s is not None else None))
                    for d, s in zip(dense, sparse)]
        except EmbeddingValidationError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise EmbeddingValidationError("Malformed model output") from exc

    encode.batch_size = batch_size
    return encode


def to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8g}" for x in vec) + "]"


def embedding_text(title: str, summary: str | None) -> str:
    return f"{title}\n{summary}" if summary else title


def pending_articles(conn, variant: str, since: datetime, until: datetime, limit: int | None = None,
                     include_untagged: bool = False, *, news_ids: list[int] | None = None):
    """기간 내 미처리 기사. news_ids=None은 기존 조회, []는 DB 조회 없이 0건.

    ID를 지정해도 기간·종목·기존 임베딩 제외 조건은 그대로 적용한다.
    """
    if news_ids is not None:
        if any(isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in news_ids):
            raise ValueError("news_ids must contain positive integer IDs")
        if not news_ids:
            return []
    tagged = "" if include_untagged else "AND EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)"
    selected = "" if news_ids is None else "AND a.id = ANY(%s)"
    sql = f"""
        SELECT a.id, a.title, a.summary FROM news_articles a
        WHERE a.published_at >= %s AND a.published_at < %s
          {tagged}
          AND NOT EXISTS (SELECT 1 FROM news_embedding_variants v WHERE v.news_id = a.id AND v.variant = %s)
          {selected}
        ORDER BY a.id"""
    params: list = [since, until, variant]
    if news_ids is not None:
        params.append(list(dict.fromkeys(news_ids)))
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _encode_checked(encode: Encoder, texts: list[str]) -> list:
    results = encode(texts)
    if not isinstance(results, (list, tuple)):
        raise EmbeddingValidationError("Embedding output must be a list of dense/sparse pairs")
    if len(results) != len(texts):
        raise EmbeddingValidationError("Embedding output count does not match input count")
    if any(not isinstance(result, (tuple, list)) or len(result) != 2 for result in results):
        raise EmbeddingValidationError("Each embedding must contain dense and sparse outputs")
    return results


def _encode_safely(encode: Encoder, chunk: list, *, fail_fast: bool = False) -> list:
    """묶음 전체가 실패하면 한 건씩 다시 시도해서, 문제 있는 기사만 건너뛴다.

    [(행, (dense, sparse) 또는 None)]을 돌려준다. 한 기사 때문에 나머지가 계속 막히는 일을 막는다.
    """
    try:
        return list(zip(chunk, _encode_checked(encode, [embedding_text(t, s) for _, t, s in chunk])))
    except EmbeddingValidationError:
        raise
    except Exception as exc:
        if fail_fast:
            raise
        log.warning("묶음 임베딩 실패(%s: %s). 한 건씩 다시 시도합니다.", type(exc).__name__, exc)
    out = []
    for row in chunk:
        try:
            out.append((row, _encode_checked(encode, [embedding_text(row[1], row[2])])[0]))
        except EmbeddingValidationError:
            raise
        except Exception as exc:
            log.error("임베딩 실패, 건너뜀: news_id=%s (%s: %s)", row[0], type(exc).__name__, exc)
            out.append((row, None))
    return out


def _validate_embedding(dense: list[float], sparse: dict[str, float] | None, variant: str) -> None:
    try:
        if (len(dense) != 1024 or any(isinstance(x, bool) or not math.isfinite(x) for x in dense)
                or not 0 < math.hypot(*dense) < math.inf):
            raise EmbeddingValidationError("Dense vector must have 1024 finite values and a nonzero finite norm")
        if variant == "hybrid" and sparse is None:
            raise EmbeddingValidationError("Hybrid sparse output must be a dictionary, not None")
        if sparse is not None:
            if not isinstance(sparse, dict) or any(
                not isinstance(k, str) or not k or isinstance(v, bool) or not math.isfinite(v) or v < 0
                for k, v in sparse.items()
            ):
                raise EmbeddingValidationError("Sparse output must map nonempty string tokens to finite nonnegative weights")
    except (TypeError, OverflowError) as exc:
        raise EmbeddingValidationError("Embedding contains invalid numeric values") from exc


def embed_window(conn, variant: str, encode: Encoder, since: datetime, until: datetime,
                 limit: int | None = None, include_untagged: bool = False, *,
                 news_ids: list[int] | None = None, batch_size: int | None = None,
                 fail_fast: bool = False) -> int:
    """새로 임베딩한 기사 수. 이미 해당 variant가 있는 기사는 건너뛴다(재실행 안전).

    실패한 기사는 저장하지 않으므로 다음 실행에서 다시 대상이 된다.
    처리 대상 수, 성공, 실패, 걸린 시간을 로그로 남긴다.

    batch_size 생략 시 BGE 인코더 설정(기본 16)을 따른다. 지정 시 내부·외부에 함께 적용한다.
    fail_fast=True면 모델 오류를 재시도하지 않는다. 개수·벡터 검증 오류는 항상 중단한다.
    모든 결과를 검증한 후 저장하므로, 뒤쪽 배치의 검증 실패도 INSERT 전에 발견한다.
    """
    started = time.monotonic()
    if batch_size is None:
        batch_size = getattr(encode, "batch_size", BATCH)
    _check_batch_size(batch_size)
    if hasattr(encode, "batch_size"):
        encode.batch_size = batch_size
    rows = pending_articles(conn, variant, since, until, limit, include_untagged, news_ids=news_ids)
    done = failed = 0
    prepared = []
    for i in range(0, len(rows), batch_size):
        for (news_id, _, _), result in _encode_safely(encode, rows[i:i + batch_size], fail_fast=fail_fast):
            if result is None:
                failed += 1
                continue
            dense, sparse = result
            _validate_embedding(dense, sparse, variant)
            prepared.append((news_id, variant, to_vector_literal(dense),
                             json.dumps(sparse, allow_nan=False) if sparse is not None else None, MODEL_NAME))
    if prepared:
        with conn.cursor() as cur:
            for params in prepared:
                cur.execute(
                    """INSERT INTO news_embedding_variants (news_id, variant, dense, sparse, model)
                       VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    params)
                done += cur.rowcount
    if rows:
        log.info("임베딩 대상 %d건: 성공 %d, 실패 %d(다음 주기에 재시도), %.1f초",
                 len(rows), done, failed, time.monotonic() - started)
    return done
