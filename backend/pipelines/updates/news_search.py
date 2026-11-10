"""뉴스 원문 청크 검색 (configs/updates.yaml news.search: chunks). 기본(article)은 candidates.recent_news_candidates (제목+요약 벡터).

1) 종목(news_stocks)·기간(published_at >= since)으로 거른 news_chunks에서 dense 상위 dense_k(정확 검색) + sparse 상위 sparse_k
   (SparseIndex, 종목·기간마다 한 번 만들어 같은 실행의 항목들이 나눠 쓴다) → 합집합. 한쪽에만 있는 후보도 다른 점수를 실제로 계산한다.
2) dense·sparse(가중치 비율 그대로)로 줄 세운 상위 rerank_k 청크만 ColBERT 점수를 더해 weights(기본 0.4:0.2:0.4)로 다시 줄 세운다
   (질의마다 min-max 정규화, disclosures.search.rank). ColBERT 벡터는 저장하지 않아 질의 때 인코딩하고 ColbertCache에 둔다.
3) 기사마다 순위가 가장 높은 청크 하나 → Candidate(text=그 청크, similarity=그 청크의 dense 코사인, doc="chunk").
   임계값(min_similarity_news_chunks)은 이 절댓값 dense로 비교한다. 합친 점수는 질의마다 다시 맞춘 값이라 순서에만 쓴다.
4) body_hash가 같은 기사(같은 매체 재전송)는 가장 먼저 발행된 하나만 남긴다.
5) 원문이 아직 없는 기사(적재 전, 수집 실패·제외)는 기존 제목+요약 벡터(news_embedding_variants)로 찾는다. doc=""라
   기존 min_similarity_news로 거르고, 원문 청크 후보와 합친 점수로 섞어 줄 세우지 않는다.
읽기 전용: SELECT만 쓴다. 공시 검색(disclosures/search.py)은 계산 함수(rank·ColbertCache·colbert_score·SparseIndex)만 가져다 쓴다.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date

from ..disclosures.embedder import colbert_score
from ..disclosures.search import CandidateScores, ColbertCache, rank, validate_weights
from ..disclosures.sparse_store import SparseIndex
from .candidates import _news_rows, vector_literal
from .models import Candidate

MODES = ("article", "chunks")
DEFAULTS = {"dense_k": 100, "sparse_k": 100, "rerank_k": 30, "colbert": True,
            "weights": {"dense": 0.4, "sparse": 0.2, "colbert": 0.4}, "dedup_body_hash": True, "fallback_headline": True}

_SCOPE = """FROM news_chunks c
JOIN news_articles a ON a.id = c.news_id
JOIN news_stocks ns ON ns.news_id = c.news_id AND ns.symbol = %(symbol)s
WHERE a.published_at >= %(since)s"""

DENSE_SQL = f"""SELECT c.news_id, c.chunk_index, 1 - (c.dense_embedding <=> %(q)s::vector)
{_SCOPE}
ORDER BY c.dense_embedding <=> %(q)s::vector, c.news_id, c.chunk_index
LIMIT %(k)s"""

SPARSE_SQL = f"""SELECT c.news_id, c.chunk_index, c.sparse_embedding
{_SCOPE}
ORDER BY c.news_id, c.chunk_index"""

_KEYS = "JOIN unnest(%(ids)s::bigint[], %(ix)s::int[]) AS k(n, i) ON c.news_id = k.n AND c.chunk_index = k.i"

DENSE_FOR_SQL = f"""SELECT c.news_id, c.chunk_index, 1 - (c.dense_embedding <=> %(q)s::vector)
FROM news_chunks c {_KEYS}"""

META_SQL = f"""SELECT c.news_id, c.chunk_index, c.chunk_text, c.embed_text, a.title, a.url, a.published_at::date, s.name,
       b.body_hash, a.published_at
FROM news_chunks c {_KEYS}
JOIN news_articles a ON a.id = c.news_id
JOIN news_sources s ON s.id = a.source_id
JOIN news_article_bodies b ON b.news_id = c.news_id"""

# 원문이 없는 기사만 기존 방식(제목+요약 벡터)으로 (candidates.RECENT_NEWS_SQL + NOT EXISTS)
HEADLINE_SQL = """
SELECT a.id, a.title, a.summary, a.url, a.published_at::date, s.name,
       1 - (v.dense <=> %(q)s::vector) AS sim
FROM news_embedding_variants v
JOIN news_articles a ON a.id = v.news_id
JOIN news_stocks ns ON ns.news_id = a.id AND ns.symbol = %(symbol)s
JOIN news_sources s ON s.id = a.source_id
WHERE v.variant = %(variant)s AND a.published_at >= %(since)s
  AND NOT EXISTS (SELECT 1 FROM news_article_bodies b WHERE b.news_id = a.id)
  AND 1 - (v.dense <=> %(q)s::vector) >= %(floor)s
ORDER BY a.published_at DESC, v.dense <=> %(q)s::vector
LIMIT %(k)s
"""


def check_mode(mode: str, topic_cfg: dict, uncalibrated: bool = False) -> bool:
    """검색 방식을 확인하고, chunks인데 min_similarity_news_chunks가 아직 없으면 True(보정 전: 기존 뉴스 값을 임시로 쓴다).
    2026-11-10 기본값을 chunks로 바꾸면서 보정 전에도 멈추지 않는다 (임계값은 바꾸지 않음). 호출자가 경고하고 summary에 남긴다.
    uncalibrated(--uncalibrated-chunks)는 예전 명령 호환용으로만 받는다."""
    if mode not in MODES:
        raise ValueError(f"news.search는 {MODES} 중 하나여야 합니다: {mode}")
    return mode == "chunks" and "min_similarity_news_chunks" not in topic_cfg


def load_query_encoder(batch_size: int = 4):
    """질의 dense·sparse·colbert와 문서 colbert를 news_chunks 적재와 같은 설정(BGE-M3, max_length 512)으로 만드는 인코더."""
    from ..common.config import load_config
    from ..disclosures.embedder import load_encoder

    cfg = dict(load_config("configs/common.yaml")["model"])
    cfg.update(batch_size=batch_size, max_length=512, devices=["cuda:0"])
    encoder, _ = load_encoder(cfg, offline=True, allow_cpu=True)
    return encoder


def release_gpu() -> None:
    """앞서 쓴 인코더를 내린 뒤 GPU 캐시를 비운다 (제목+요약 인코더와 원문 청크용 인코더를 함께 올리지 않게)."""
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _ids(keys):
    return {"ids": [k[0] for k in keys], "ix": [k[1] for k in keys]}


class NewsChunkSearch:
    """한 실행(같은 연결·인코더) 동안 쓰는 뉴스 청크 검색. sparse 색인과 ColBERT 벡터는 실행 안에서 다시 쓴다."""

    def __init__(self, conn, encoder, cfg: dict | None = None, cache: ColbertCache | None = None):
        self.conn, self.encoder = conn, encoder
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.weights = validate_weights(self.cfg["weights"], "news.chunks.weights")
        self.use_colbert = bool(self.cfg["colbert"]) and self.weights["colbert"] > 0
        pre = self.weights["dense"] + self.weights["sparse"]
        self.pre_weights = {"dense": self.weights["dense"] / pre, "sparse": self.weights["sparse"] / pre} if pre else \
            {"dense": 1.0}
        self.cache = cache if cache is not None else ColbertCache(512)
        self._sparse: dict[tuple[str, date], SparseIndex] = {}
        self.timings_ms: list[float] = []

    def _index(self, cur, symbol: str, since: date) -> SparseIndex:
        key = (symbol, since)
        if key not in self._sparse:
            cur.execute(SPARSE_SQL, {"symbol": symbol, "since": since})
            self._sparse[key] = SparseIndex(((int(n), int(i)), sp or {}) for n, i, sp in cur.fetchall())
        return self._sparse[key]

    def articles(self, symbol: str, query: str, since: date) -> list[Candidate]:
        """기사 단위 후보 (임계값 없이, 순위순). 기사마다 순위가 가장 높은 청크 하나, 같은 본문은 가장 먼저 발행된 기사만."""
        started = time.perf_counter()
        q = self.encoder.encode_query(query, sparse=True, colbert=self.use_colbert)
        qsparse = q.sparse or {}
        with self.conn.cursor() as cur:
            cur.execute("SET LOCAL enable_indexscan = off")      # 종목 조건이 붙으면 HNSW는 결과가 덜 나올 수 있다 (정확 검색)
            try:
                cur.execute(DENSE_SQL, {"q": vector_literal(q.dense), "symbol": symbol, "since": since,
                                        "k": int(self.cfg["dense_k"])})
                dense = {(int(n), int(i)): float(s) for n, i, s in cur.fetchall()}
                index = self._index(cur, symbol, since)
                sparse_top = dict(index.top(qsparse, int(self.cfg["sparse_k"])))
                missing = sorted(set(sparse_top) - set(dense))
                if missing:
                    cur.execute(DENSE_FOR_SQL, {"q": vector_literal(q.dense), **_ids(missing)})
                    dense.update({(int(n), int(i)): float(s) for n, i, s in cur.fetchall()})
                keys = sorted(dense)
                meta = {}
                if keys:
                    cur.execute(META_SQL, _ids(keys))
                    meta = {(int(r[0]), int(r[1])): r for r in cur.fetchall()}
            finally:
                cur.execute("SET LOCAL enable_indexscan TO DEFAULT")
        keys = [k for k in keys if k in meta]
        sparse = {}
        for k in keys:
            value = sparse_top.get(k)
            sparse[k] = value if value is not None else (index.score(qsparse, k) or 0.0)
        if not keys:
            self.timings_ms.append((time.perf_counter() - started) * 1000)
            return []
        order = [k for k, _ in rank(CandidateScores(keys, dense, sparse, {}, {}, {}, []),
                                    {**{"dense": 0.0, "sparse": 0.0}, **self.pre_weights}, len(keys))]
        if self.use_colbert:
            top = order[:int(self.cfg["rerank_k"])]
            colbert = self._colbert(q.colbert, top, meta)
            final = rank(CandidateScores(top, {k: dense[k] for k in top}, {k: sparse[k] for k in top}, colbert, {}, {}, []),
                         self.weights, len(top))
            order = [k for k, _ in final] + order[len(top):]
        out, seen, hashes = [], set(), {}
        for k in order:
            if k[0] in seen:
                continue
            seen.add(k[0])
            n, i, chunk_text, _, title, url, day, source, body_hash, published = meta[k]
            c = Candidate(ref=f"news:{n}", kind="news", symbol=symbol, date=str(day), title=title, text=chunk_text or "",
                          url=url, source=source or "", similarity=dense[k], doc="chunk")
            if self.cfg["dedup_body_hash"] and body_hash:
                prev = hashes.get(body_hash)
                if prev is not None and (prev[0], prev[1]) <= (published, n):
                    continue                                     # 같은 본문: 먼저 발행된 기사가 이미 있다
                if prev is not None:
                    out = [x for x in out if x.ref != prev[2]]   # 지금 기사가 더 먼저 발행됐다: 앞의 것을 뺀다
                hashes[body_hash] = (published, n, c.ref)
            out.append(c)
        self.timings_ms.append((time.perf_counter() - started) * 1000)
        return out

    def _colbert(self, query_vecs, keys, meta) -> dict:
        texts = {k: meta[k][3] or meta[k][2] or "" for k in keys}      # 적재 때 임베딩한 글(embed_text)과 같은 글
        namespace = str(getattr(self.encoder, "cache_namespace", type(self.encoder).__name__))
        cache_keys = {k: (str(k[0]), k[1], hashlib.sha256(texts[k].encode()).hexdigest(), namespace) for k in keys}
        vectors = {k: self.cache.get(cache_keys[k]) for k in keys}
        need = [k for k, v in vectors.items() if v is None]
        for k, vec in zip(need, self.encoder.encode_colbert_documents([texts[k] for k in need])):
            vectors[k] = vec
            self.cache.put(cache_keys[k], vec)
        return {k: colbert_score(query_vecs, vectors[k]) for k in keys}

    def recent(self, symbol: str, query: str, since: date, k: int, floor: float, *, headline_vec=None,
               headline_floor: float | None = None, variant: str = "hybrid") -> list[Candidate]:
        """recent_news_candidates와 같은 쓰임: 임계값(floor, 청크 dense) 이상인 기사를 날짜 최신순으로 k건.
        fallback_headline이면 원문이 없는 기사를 기존 제목+요약 벡터(headline_vec, headline_floor)로 더한다."""
        arts = [c for c in self.articles(symbol, query, since) if c.similarity >= floor]
        arts = sorted(arts, key=lambda c: (c.date, c.similarity), reverse=True)[:k]
        if self.cfg["fallback_headline"] and headline_vec is not None:
            arts += _news_rows(self.conn, HEADLINE_SQL, {
                "q": vector_literal(headline_vec), "symbol": symbol, "variant": variant, "since": since, "k": k,
                "floor": floor if headline_floor is None else headline_floor}, symbol)
        return arts
