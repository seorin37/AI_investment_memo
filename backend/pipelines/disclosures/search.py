"""공시 청크 검색: dense_search (pgvector) / hybrid_search (dense + sparse, min-max 정규화 가중합).

hybrid 절차: dense 후보 candidate_k(DB) + sparse 후보 candidate_k(메모리 역색인) → 합집합 →
한쪽에만 있는 후보도 다른 쪽 점수를 실제로 계산(0으로 채우지 않음) → 질의별 min-max 정규화
(최댓값=최솟값이면 모두 1.0) → hybrid = w_d × dense_norm + w_s × sparse_norm → 상위 final_k.

정확도 모드: search.exact=true(평가용)면 `SET LOCAL enable_indexscan = off`로 HNSW 없이 정확 검색,
false(서비스용)면 `SET LOCAL hnsw.ef_search = <ef_search>`.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from ..common.logging import get_logger
from .sparse_store import Key, SparseIndex


log = get_logger("disclosures.search")


@dataclass
class Filters:
    symbol: str | None = None
    kind: str | None = None
    period_end: str | None = None


@dataclass
class Hit:
    rcept_no: str
    chunk_index: int
    score: float
    dense: float | None = None
    sparse: float | None = None
    section: str = ""
    symbol: str = ""
    period_end: str = ""

    @property
    def key(self) -> Key:
        return (self.rcept_no, self.chunk_index)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 점수 결합 (순수 함수) ─────────────────────────────────
def minmax(scores: dict[Key, float]) -> dict[Key, float]:
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    if high == low:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


def combine(dense: dict[Key, float], sparse: dict[Key, float], dense_weight: float, sparse_weight: float, k: int) -> list[tuple[Key, float]]:
    """두 점수표는 같은 후보 집합(합집합)을 덮어야 한다. 정규화 가중합 상위 k (동점은 키 순)."""
    if set(dense) != set(sparse):
        raise ValueError("dense와 sparse 점수표의 후보 집합이 다릅니다 (빠진 점수를 0으로 채우지 않는다).")
    dense_norm, sparse_norm = minmax(dense), minmax(sparse)
    combined = {key: dense_weight * dense_norm[key] + sparse_weight * sparse_norm[key] for key in dense}
    return sorted(combined.items(), key=lambda item: (-item[1], item[0]))[:k]


# ── DB ───────────────────────────────────────────────
def vector_literal(vector: np.ndarray) -> str:
    return "[" + ",".join(repr(float(x)) for x in np.asarray(vector, dtype=np.float32)) + "]"


def set_search_mode(conn: Connection, exact: bool, ef_search: int) -> None:
    """트랜잭션 안에서만 유효(SET LOCAL)."""
    if exact:
        conn.execute(text("SET LOCAL enable_indexscan = off"))
    else:
        conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))


def _filter_sql(filters: Filters) -> tuple[str, dict]:
    clauses, params = [], {}
    if filters.symbol:
        clauses.append("d.symbol = :symbol")
        params["symbol"] = filters.symbol
    if filters.kind:
        clauses.append("d.kind = CAST(:kind AS disclosure_kind)")
        params["kind"] = filters.kind
    if filters.period_end:
        clauses.append("d.period_end = CAST(:period_end AS date)")
        params["period_end"] = filters.period_end
    return "".join(f" AND {c}" for c in clauses), params


def dense_candidates(conn: Connection, query_vector: np.ndarray, k: int, filters: Filters) -> list[Hit]:
    where, params = _filter_sql(filters)
    rows = conn.execute(
        text(
            "SELECT c.rcept_no, c.chunk_index, c.section, d.symbol, d.period_end::text,"
            " 1 - (c.embedding <=> CAST(:q AS vector)) AS score"
            " FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no"
            f" WHERE c.embedding IS NOT NULL{where}"
            " ORDER BY c.embedding <=> CAST(:q AS vector), c.rcept_no, c.chunk_index LIMIT :k"
        ),
        {"q": vector_literal(query_vector), "k": k, **params},
    ).all()
    return [Hit(r[0], r[1], float(r[5]), dense=float(r[5]), section=r[2] or "", symbol=r[3].strip(), period_end=r[4]) for r in rows]


def dense_scores_for(conn: Connection, query_vector: np.ndarray, keys: list[Key]) -> dict[Key, Hit]:
    """지정한 청크들의 실제 dense 점수(코사인 유사도)."""
    if not keys:
        return {}
    rows = conn.execute(
        text(
            "SELECT c.rcept_no, c.chunk_index, c.section, d.symbol, d.period_end::text,"
            " 1 - (c.embedding <=> CAST(:q AS vector))"
            " FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no"
            " JOIN unnest(CAST(:rs AS text[]), CAST(:ix AS int[])) AS k(r, i) ON c.rcept_no = k.r AND c.chunk_index = k.i"
            " WHERE c.embedding IS NOT NULL"
        ),
        {"q": vector_literal(query_vector), "rs": [k[0] for k in keys], "ix": [k[1] for k in keys]},
    ).all()
    return {(r[0], r[1]): Hit(r[0], r[1], float(r[5]), dense=float(r[5]), section=r[2] or "", symbol=r[3].strip(), period_end=r[4]) for r in rows}


def allowed_rcept_nos(conn: Connection, filters: Filters) -> set[str]:
    where, params = _filter_sql(filters)
    return set(conn.execute(text(f"SELECT d.rcept_no FROM disclosures d WHERE true{where}"), params).scalars().all())


# ── 검색 ─────────────────────────────────────────────
def dense_search(engine: Engine, encoder, query: str, filters: Filters, search_config: dict) -> list[Hit]:
    encoded = encoder.encode_query(query, sparse=False)
    with engine.begin() as conn:
        set_search_mode(conn, bool(search_config.get("exact", True)), int(search_config.get("ef_search", 200)))
        return dense_candidates(conn, encoded.dense, int(search_config.get("final_k", 10)), filters)


def hybrid_search(
    engine: Engine,
    encoder,
    sparse_index: SparseIndex,
    query: str,
    filters: Filters,
    search_config: dict,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> list[Hit]:
    """dense 후보 ∪ sparse 후보의 두 점수를 min-max 정규화해 가중합 (후보·점수 계산은 score_candidates와 공유)."""
    scores = score_candidates(engine, encoder, sparse_index, query, filters, search_config, with_colbert=False)
    ranked = combine(scores.dense, scores.sparse, dense_weight, sparse_weight, int(search_config.get("final_k", 10)))
    hits = []
    for key, score in ranked:
        base = scores.meta[key]
        hits.append(Hit(key[0], key[1], score, dense=scores.dense[key], sparse=scores.sparse[key], section=base.section, symbol=base.symbol, period_end=base.period_end))
    return hits


def timed(fn, *args, **kwargs):
    started = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - started) * 1000.0


# ── 그리드 평가용: 후보 원점수 3종 + 가중치 순위 (WO-019) ─────────────
SIGNALS = ("dense", "sparse", "colbert")


@dataclass
class CandidateScores:
    """한 질의의 후보(dense 상위 k ∪ sparse 상위 k)와 원점수. 한쪽 후보에만 있어도 다른 점수를 실제로 계산한다."""

    keys: list[Key]
    dense: dict[Key, float]
    sparse: dict[Key, float]
    colbert: dict[Key, float]
    meta: dict[Key, Hit]
    timings_ms: dict[str, float]
    dropped: list[Key]
    colbert_encoded: int = 0  # 이번 질의에서 캐시 없이 새로 인코딩한 후보 수


class ColbertCache:
    """후보 ColBERT 벡터 LRU 캐시 ((rcept_no, chunk_index) → float16 배열, 바이트 상한)."""

    def __init__(self, max_mb: float = 2048):
        from collections import OrderedDict

        self.max_bytes = int(max_mb * 2**20)
        self.items: "OrderedDict[Key, np.ndarray]" = OrderedDict()
        self.bytes = 0
        self.hits = 0
        self.misses = 0

    def get(self, key: Key):
        value = self.items.get(key)
        if value is None:
            self.misses += 1
            return None
        self.items.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key: Key, value: np.ndarray) -> None:
        if key in self.items:
            self.bytes -= self.items.pop(key).nbytes
        self.items[key] = value
        self.bytes += value.nbytes
        while self.bytes > self.max_bytes and len(self.items) > 1:
            _, old = self.items.popitem(last=False)
            self.bytes -= old.nbytes


def chunk_texts(conn: Connection, keys: list[Key]) -> dict[Key, str]:
    if not keys:
        return {}
    rows = conn.execute(
        text(
            "SELECT c.rcept_no, c.chunk_index, c.chunk_text FROM disclosure_chunks c"
            " JOIN unnest(CAST(:rs AS text[]), CAST(:ix AS int[])) AS k(r, i) ON c.rcept_no = k.r AND c.chunk_index = k.i"
        ),
        {"rs": [k[0] for k in keys], "ix": [k[1] for k in keys]},
    ).all()
    return {(r[0], r[1]): r[2] for r in rows}


def score_candidates(
    engine: Engine,
    encoder,
    sparse_index: SparseIndex,
    query: str,
    filters: Filters,
    search_config: dict,
    colbert_cache: ColbertCache | None = None,
    with_colbert: bool = True,
) -> CandidateScores:
    """hybrid_search와 같은 후보·dense·sparse 점수에 ColBERT 점수를 더해 원점수만 돌려준다 (순위는 rank())."""
    from .embedder import colbert_score

    timings: dict[str, float] = {}
    started = time.perf_counter()
    encoded = encoder.encode_query(query, sparse=True, colbert=with_colbert)
    timings["query_encode"] = (time.perf_counter() - started) * 1000.0
    candidate_k = int(search_config.get("candidate_k", 50))
    with engine.begin() as conn:
        set_search_mode(conn, bool(search_config.get("exact", True)), int(search_config.get("ef_search", 200)))
        step = time.perf_counter()
        dense_hits = {hit.key: hit for hit in dense_candidates(conn, encoded.dense, candidate_k, filters)}
        timings["dense_db"] = (time.perf_counter() - step) * 1000.0
        step = time.perf_counter()
        allowed = allowed_rcept_nos(conn, filters) if (filters.symbol or filters.kind or filters.period_end) else None
        sparse_top = dict(sparse_index.top(encoded.sparse or {}, candidate_k, allowed))
        timings["sparse"] = (time.perf_counter() - step) * 1000.0
        step = time.perf_counter()
        missing = sorted(set(sparse_top) - set(dense_hits))
        dense_hits.update(dense_scores_for(conn, encoded.dense, missing))
        timings["dense_db"] += (time.perf_counter() - step) * 1000.0

        dense_scores: dict[Key, float] = {}
        sparse_scores: dict[Key, float] = {}
        dropped: list[Key] = []
        for key in sorted(set(dense_hits) | set(sparse_top)):
            dense_hit = dense_hits.get(key)
            sparse_value = sparse_top.get(key)
            if sparse_value is None:
                sparse_value = sparse_index.score(encoded.sparse or {}, key)
            if dense_hit is None or sparse_value is None:
                dropped.append(key)
                continue
            dense_scores[key] = dense_hit.dense
            sparse_scores[key] = sparse_value
        keys = sorted(dense_scores)
        cache = colbert_cache if colbert_cache is not None else ColbertCache()
        vectors: dict[Key, object] = {}
        need: list[Key] = []
        texts: dict[Key, str] = {}
        if with_colbert:
            step = time.perf_counter()
            vectors = {key: cache.get(key) for key in keys}
            need = [key for key, vec in vectors.items() if vec is None]
            texts = chunk_texts(conn, need)
            timings["colbert"] = (time.perf_counter() - step) * 1000.0

    colbert_scores: dict[Key, float] = {}
    if with_colbert:
        # GPU 인코딩은 DB 트랜잭션을 닫은 뒤에 한다 (연결을 잡고 있지 않게)
        step = time.perf_counter()
        fresh = encoder.encode_colbert_documents([texts[key] for key in need])
        for key, vec in zip(need, fresh):
            vectors[key] = vec
            cache.put(key, vec)
        colbert_scores = {key: colbert_score(encoded.colbert, vectors[key]) for key in keys}
        timings["colbert"] += (time.perf_counter() - step) * 1000.0
    timings["total"] = (time.perf_counter() - started) * 1000.0
    if dropped:
        log.warning("점수를 계산할 수 없는 후보 제외: %s", dropped)
    return CandidateScores(keys, dense_scores, sparse_scores, colbert_scores, {k: dense_hits[k] for k in keys}, timings, dropped, len(need))


def validate_weights(weights: dict[str, float], label: str = "") -> dict[str, float]:
    """신호 이름·음수·합(1±1e-6) 검사. 빠진 신호는 0."""
    unknown = set(weights) - set(SIGNALS)
    if unknown:
        raise ValueError(f"{label}: 알 수 없는 신호 {sorted(unknown)}")
    clean = {name: float(weights.get(name) or 0.0) for name in SIGNALS}
    if any(value < 0 for value in clean.values()):
        raise ValueError(f"{label}: 음수 가중치 {clean}")
    if abs(sum(clean.values()) - 1.0) > 1e-6:
        raise ValueError(f"{label}: 가중치 합이 1이 아닙니다 ({sum(clean.values())})")
    return clean


def rank(scores: CandidateScores, weights: dict[str, float], k: int) -> list[tuple[Key, float]]:
    """가중치가 0보다 큰 신호만 질의별 min-max 정규화해 가중합 → 상위 k (동점은 키 순)."""
    used = [(name, weight) for name, weight in validate_weights(weights).items() if weight > 0]
    normalized = {name: minmax(getattr(scores, name)) for name, _ in used}
    for name, _ in used:
        if set(normalized[name]) != set(scores.keys):
            raise ValueError(f"{name} 점수가 후보 전체를 덮지 않습니다 (0 채움 금지)")
    combined = {key: sum(weight * normalized[name][key] for name, weight in used) for key in scores.keys}
    return sorted(combined.items(), key=lambda item: (-item[1], item[0]))[:k]
