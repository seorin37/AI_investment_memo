"""검색 평가: Recall@5 · Recall@10 · MRR · 지연시간.

질의 파일(jsonl) 한 줄: {"query", "symbol"?, "period_end"?, "kind"?, "gold": [{"rcept_no", "section_prefix"}]}
정답 판정: 결과 청크의 rcept_no가 같고 section이 section_prefix로 시작하면 해당 gold 항목을 맞힌 것.
Recall@k = top-k가 맞힌 gold 항목 수 / gold 항목 수, MRR = 첫 정답 순위의 역수(final_k 안에 없으면 0).
평가는 항상 정확 검색(search.exact=true)으로 한다.

    PYTHONPATH=backend python -m pipelines.disclosures.evaluate --config configs/common.yaml \\
        --mode-config configs/hybrid.yaml --queries eval/queries.jsonl --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

from sqlalchemy import text

from ..common.config import data_path, load_config, resolve_path
from ..common.logging import get_logger, setup_logging
from .loader import KST
from .search import Filters, Hit, dense_search, hybrid_search, timed


log = get_logger("disclosures.evaluate")


def load_queries(path: Path) -> list[dict]:
    queries = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("query") or not row.get("gold"):
                raise ValueError(f"{path.name}:{number}: query와 gold가 필요합니다.")
            queries.append(row)
    return queries


def matches(hit: Hit, gold: dict) -> bool:
    return hit.rcept_no == gold["rcept_no"] and hit.section.startswith(gold.get("section_prefix", ""))


def recall_at(hits: list[Hit], gold: list[dict], k: int) -> float:
    top = hits[:k]
    return sum(1 for g in gold if any(matches(h, g) for h in top)) / len(gold)


def reciprocal_rank(hits: list[Hit], gold: list[dict]) -> float:
    for rank, hit in enumerate(hits, 1):
        if any(matches(hit, g) for g in gold):
            return 1.0 / rank
    return 0.0


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(per_query: list[dict]) -> dict:
    latencies = [q["latency_ms"] for q in per_query]
    return {
        "queries": len(per_query),
        "recall@5": round(mean(q["recall@5"] for q in per_query), 4) if per_query else 0.0,
        "recall@10": round(mean(q["recall@10"] for q in per_query), 4) if per_query else 0.0,
        "mrr": round(mean(q["rr"] for q in per_query), 4) if per_query else 0.0,
        "latency_ms_mean": round(mean(latencies), 1) if latencies else 0.0,
        "latency_ms_p50": round(percentile(latencies, 0.5), 1),
        "latency_ms_p95": round(percentile(latencies, 0.95), 1),
    }


def evaluate(queries: list[dict], search_fn) -> dict:
    """search_fn(query_row) -> list[Hit]. 질의별 지표와 요약을 반환한다."""
    per_query = []
    for row in queries:
        hits, latency = timed(search_fn, row)
        per_query.append(
            {
                "query": row["query"],
                "recall@5": recall_at(hits, row["gold"], 5),
                "recall@10": recall_at(hits, row["gold"], 10),
                "rr": reciprocal_rank(hits, row["gold"]),
                "latency_ms": round(latency, 1),
                "top": [{"rcept_no": h.rcept_no, "chunk_index": h.chunk_index, "section": h.section, "score": round(h.score, 4)} for h in hits[:10]],
            }
        )
    return {"summary": summarize(per_query), "per_query": per_query}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공시 검색 평가 (Recall@5·@10·MRR·지연시간)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mode-config", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true")
    args = ap.parse_args(argv)

    from .embedder import load_encoder, set_offline

    set_offline(args.offline)
    setup_logging()
    config = load_config(args.config, args.mode_config)
    mode = config.get("mode")
    search_config = dict(config.get("search", {}))
    if not search_config.get("exact", True):
        log.warning("평가는 정확 검색으로 한다: search.exact=false를 true로 바꿔 실행합니다.")
    search_config["exact"] = True
    queries = load_queries(resolve_path(args.queries))

    from ..common.db import get_read_engine

    engine = get_read_engine()
    encoder, model_info = load_encoder(config["model"], args.offline, args.allow_cpu)
    if mode == "hybrid":
        from .sparse_store import SparseIndex

        index = SparseIndex.from_engine(engine)
        weights = config.get("hybrid", {})
        dense_weight, sparse_weight = float(weights.get("dense_weight", 0.5)), float(weights.get("sparse_weight", 0.5))
        log.info("sparse 역색인 %d청크, 가중치 dense %.2f / sparse %.2f", len(index), dense_weight, sparse_weight)

        def search_fn(row):
            return hybrid_search(engine, encoder, index, row["query"], _filters(row), search_config, dense_weight, sparse_weight)
    else:

        def search_fn(row):
            return dense_search(engine, encoder, row["query"], _filters(row), search_config)

    search_fn({"query": "워밍업"})  # 첫 질의의 CUDA 초기화 시간이 지연시간에 섞이지 않게
    result = evaluate(queries, search_fn)
    result.update(mode=mode, model=model_info, search=search_config, hybrid=config.get("hybrid"))
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    out = data_path(config, "logs_dir") / f"eval_{mode}_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    print(f"평가 결과: {out}", file=sys.stderr)
    return 0


def _filters(row: dict) -> Filters:
    return Filters(symbol=row.get("symbol"), kind=row.get("kind"), period_end=row.get("period_end"))


if __name__ == "__main__":
    raise SystemExit(main())
