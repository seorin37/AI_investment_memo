"""검색 가중치 그리드 평가: Dense·Sparse·ColBERT 조합을 같은 질문·같은 후보로 비교한다 (WO-019).

- 모델 1회 로드, sparse 역색인 1회 구축. 질문마다 후보(dense 상위 k ∪ sparse 상위 k)와 원점수 3종을 한 번만 계산하고
  모든 조합에 가중치만 바꿔 적용한다 (search.score_candidates → search.rank).
- ColBERT는 전체 문서를 미리 저장하지 않고 후보만 질의 시점에 인코딩한다(벡터는 LRU 캐시).
- 평가는 정확 검색(search.exact=true). 기준표는 WO-018 정렬판(사실 그룹), 채점 대상(eval_status=scored)만.
- --split dev:0.7 --seed 42: 기업별 층화 분할, dev에서 최고 조합(Complete@10 → MRR → GroupRecall@10 → 그리드 순서)을
  고르고 test 점수를 따로 보고한다.

    PYTHONPATH=backend python -m pipelines.disclosures.evaluate_grid --grid configs/grid.yaml \\
        --reference eval/reference_rag_repair_20261022_v1_db/reference_annotations.jsonl --split dev:0.7 --seed 42 --offline
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Callable

import yaml
from sqlalchemy import text

from ..common.config import data_path, load_config, resolve_path
from ..common.logging import get_logger, setup_logging
from . import reference_eval as ref
from .evaluate import percentile
from .loader import KST
from .search import CandidateScores, ColbertCache, Filters, rank, score_candidates, validate_weights


log = get_logger("disclosures.evaluate_grid")
FILTERS = ("symbol", "none", "symbol_period")
STAGES = ("query_encode", "dense_db", "sparse", "colbert", "total")


def load_grid(path: Path) -> tuple[list[dict], dict]:
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    combos = []
    seen = set()
    for item in data.get("combos", []):
        combo_id = str(item["id"])
        if combo_id in seen:
            raise ValueError(f"조합 id 중복: {combo_id}")
        seen.add(combo_id)
        weights = validate_weights({k: item.get(k, 0.0) for k in ("dense", "sparse", "colbert")}, combo_id)
        combos.append({"id": combo_id, "weights": weights, "note": item.get("note", "")})
    if not combos:
        raise ValueError("그리드에 조합이 없습니다.")
    return combos, data.get("colbert", {})


def question_filters(question: ref.RefQuestion, mode: str) -> Filters:
    if mode == "none":
        return Filters()
    if mode == "symbol_period" and len(question.periods) == 1:
        return Filters(symbol=question.symbol, period_end=question.periods[0])
    return Filters(symbol=question.symbol)  # symbol, 또는 기간이 여러 개인 질문


def run_grid(
    questions: list[ref.RefQuestion],
    combos: list[dict],
    scorer: Callable[[ref.RefQuestion], CandidateScores],
    final_k: int = 10,
) -> list[dict]:
    """질문마다 scorer를 한 번 호출하고 모든 조합의 순위·지표를 낸다."""
    results = []
    for number, question in enumerate(questions, 1):
        scores = scorer(question)
        per_combo = {}
        for combo in combos:
            ranked = rank(scores, combo["weights"], final_k)
            keys = [key for key, _ in ranked]
            per_combo[combo["id"]] = {
                **ref.score_question(keys, question),
                "top": [
                    {
                        "rcept_no": key[0],
                        "chunk_index": key[1],
                        "section": scores.meta[key].section if key in scores.meta else "",
                        "score": round(value, 6),
                        "dense": round(scores.dense[key], 6),
                        "sparse": round(scores.sparse[key], 6),
                        "colbert": round(scores.colbert[key], 6) if key in scores.colbert else None,
                        "evidence": key in question.evidence,
                    }
                    for key, value in ranked
                ],
            }
        results.append(
            {
                "id": question.id,
                "symbol": question.symbol,
                "question_type": question.question_type,
                "design_intent": question.design_intent,
                "needs_human_check": question.needs_human_check,
                "query": question.query,
                "candidates": len(scores.keys),
                "colbert_encoded": scores.colbert_encoded,
                "dropped": [list(k) for k in scores.dropped],
                "timings_ms": {k: round(v, 1) for k, v in scores.timings_ms.items()},
                "combos": per_combo,
            }
        )
        log.info("[%d/%d] %s 후보 %d, %.0fms", number, len(questions), question.id, len(scores.keys), scores.timings_ms.get("total", 0.0))
    return results


def _rows(results: list[dict], combo_id: str, ids: set[str] | None = None) -> list[dict]:
    return [
        {**r["combos"][combo_id], "symbol": r["symbol"], "question_type": r["question_type"], "design_intent": r["design_intent"]}
        for r in results
        if ids is None or r["id"] in ids
    ]


def summarize(results: list[dict], combos: list[dict], dev_ids: list[str] | None = None, test_ids: list[str] | None = None) -> dict:
    reviewed = {r["id"] for r in results if not r["needs_human_check"]}
    summary: dict = {"combos": {}}
    for combo in combos:
        cid = combo["id"]
        entry = {
            "weights": combo["weights"],
            "note": combo["note"],
            "all": ref.aggregate(_rows(results, cid)),
            "reviewed": ref.aggregate(_rows(results, cid, reviewed)),
            "by_symbol": ref.grouped(_rows(results, cid), "symbol"),
            "by_question_type": ref.grouped(_rows(results, cid), "question_type"),
            "by_design_intent": ref.grouped(_rows(results, cid), "design_intent"),
        }
        if dev_ids is not None:
            entry["dev"] = ref.aggregate(_rows(results, cid, set(dev_ids)))
            entry["test"] = ref.aggregate(_rows(results, cid, set(test_ids or [])))
        summary["combos"][cid] = entry
    if dev_ids is not None:
        order = {c["id"]: i for i, c in enumerate(combos)}
        best = max(
            combos,
            key=lambda c: (
                summary["combos"][c["id"]]["dev"].get("complete@10", 0),
                summary["combos"][c["id"]]["dev"].get("mrr", 0),
                summary["combos"][c["id"]]["dev"].get("group_recall@10", 0),
                -order[c["id"]],
            ),
        )
        summary["selection"] = {
            "rule": "dev Complete@10 → MRR → GroupRecall@10 → 그리드 순서",
            "best_on_dev": best["id"],
            "test_of_best": summary["combos"][best["id"]]["test"],
        }
    stage = {}
    for name in STAGES:
        values = [r["timings_ms"][name] for r in results if name in r["timings_ms"]]
        if values:
            stage[name] = {"mean_ms": round(mean(values), 1), "p95_ms": round(percentile(values, 0.95), 1)}
    if stage:
        base = stage.get("query_encode", {}).get("mean_ms", 0) + stage.get("dense_db", {}).get("mean_ms", 0)
        with_sparse = base + stage.get("sparse", {}).get("mean_ms", 0)
        encoded = sum(r.get("colbert_encoded", 0) for r in results)
        colbert_ms = sum(r["timings_ms"].get("colbert", 0) for r in results)
        mean_candidates = mean(r["candidates"] for r in results)
        # 캐시가 없는 서비스 상황 추정: 이번 실행의 후보 1개당 ColBERT 시간 × 질문당 평균 후보 수
        per_doc = colbert_ms / encoded if encoded else None
        summary["latency"] = {
            "note": "질의 인코딩은 dense·sparse·colbert를 한 번에 계산한 시간. 조합별이 아니라 단계별 측정값으로 방식별 지연을 추정한다. "
            "colbert 관측값은 실행 중 후보 벡터 캐시가 적중한 몫을 포함하므로, 캐시 없는 추정(cold)을 함께 낸다.",
            "stages": stage,
            "colbert_encoded_docs": encoded,
            "colbert_ms_per_encoded_doc": round(per_doc, 2) if per_doc else None,
            "estimated_mean_ms": {
                "D100 (질의 인코딩 + dense)": round(base, 1),
                "D·S 조합 (+ sparse)": round(with_sparse, 1),
                "C 조합 관측 (+ colbert, 캐시 포함)": round(with_sparse + stage.get("colbert", {}).get("mean_ms", 0), 1),
                "C 조합 추정 (+ colbert, 캐시 없음)": round(with_sparse + per_doc * mean_candidates, 1) if per_doc else None,
            },
        }
    return summary


def write_outputs(out_json: Path, out_csv: Path, payload: dict) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    subsets = ["all", "reviewed", "dev", "test"]
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["combo", "dense", "sparse", "colbert", "subset", "n", "complete@5", "complete@10", "group_recall@5", "group_recall@10", "mrr"])
        for cid, entry in payload["summary"]["combos"].items():
            w = entry["weights"]
            for subset in subsets:
                if subset not in entry:
                    continue
                m = entry[subset]
                writer.writerow([cid, w["dense"], w["sparse"], w["colbert"], subset, m.get("n", 0)] + [m.get(k, "") for k in ("complete@5", "complete@10", "group_recall@5", "group_recall@10", "mrr")])


def check_reference_corpus(reference: Path, db_chunks: int) -> dict:
    """정렬판이 만들어진 코퍼스(청크 수·파서·청커 버전)와 현재가 다르면 중단 (다시 청킹했으면 정렬판을 다시 만들어야 한다)."""
    from .chunker import CHUNKER_VERSION
    from .parser import PARSER_VERSION

    summary_path = reference.parent / "alignment_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"{summary_path}가 없습니다. eval_reference로 정렬판을 만드세요.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    corpus = summary.get("corpus", {})
    current = {"db_chunks": db_chunks, "parser_version": PARSER_VERSION, "chunker_version": CHUNKER_VERSION}
    differ = {k: (corpus.get(k), v) for k, v in current.items() if corpus.get(k) != v}
    if differ:
        raise SystemExit(
            f"정렬판 코퍼스와 현재가 다릅니다 (정렬판, 현재): {differ}. "
            "`python -m pipelines.disclosures.eval_reference`로 정렬판을 다시 만드세요."
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="검색 가중치 그리드 평가 (Dense·Sparse·ColBERT)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--grid", default="configs/grid.yaml")
    ap.add_argument("--reference", default="eval/reference_rag_repair_20261022_v1_db/reference_annotations.jsonl")
    ap.add_argument("--filter", choices=FILTERS, default="symbol", help="검색 범위: symbol(기본) | none | symbol_period")
    ap.add_argument("--split", default=None, help="예: dev:0.7 — 기업별 층화 dev/test 분할")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=None, help="스모크용: 기업별로 고르게 N문항")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true")
    args = ap.parse_args(argv)

    from .embedder import load_encoder, set_offline

    set_offline(args.offline)
    setup_logging()
    config = load_config(args.config)
    combos, colbert_cfg = load_grid(resolve_path(args.grid))
    search_config = dict(config.get("search", {}))
    search_config["exact"] = True  # 평가는 항상 정확 검색
    final_k = int(search_config.get("final_k", 10))
    reference = resolve_path(args.reference)
    questions, excluded = ref.load_reference(reference)
    if args.limit:
        questions = ref.stratified_limit(questions, args.limit)
    dev_ids = test_ids = None
    if args.split:
        name, _, ratio = args.split.partition(":")
        if name != "dev" or not ratio:
            raise SystemExit("--split 형식은 dev:0.7 입니다.")
        dev_ids, test_ids = ref.stratified_split(questions, float(ratio), args.seed)

    from ..common.db import get_engine
    from .sparse_store import SparseIndex

    engine = get_engine()
    with engine.connect() as conn:
        db_chunks = int(conn.execute(text("SELECT count(*) FROM disclosure_chunks")).scalar())
        rcept_nos = conn.execute(text("SELECT DISTINCT rcept_no FROM disclosure_chunks")).scalars().all()
    alignment = check_reference_corpus(reference, db_chunks)
    index = SparseIndex.from_dir(data_path(config, "sparse_dir"), rcept_nos)
    if len(index) != db_chunks:
        raise SystemExit(f"sparse 역색인({len(index)})과 DB 청크({db_chunks}) 수가 다릅니다. hybrid 임베딩을 먼저 완료하세요.")
    encoder, model_info = load_encoder(config["model"], args.offline, args.allow_cpu)
    cache = ColbertCache(float(colbert_cfg.get("cache_max_mb", 2048)))
    with_colbert = any(c["weights"]["colbert"] > 0 for c in combos)

    import torch

    def scorer(question: ref.RefQuestion) -> CandidateScores:
        return score_candidates(engine, encoder, index, question.query, question_filters(question, args.filter), search_config, cache, with_colbert)

    log.info("워밍업 질의 (CUDA 초기화 시간이 지연시간에 섞이지 않게)")
    score_candidates(engine, encoder, index, "워밍업", Filters(), search_config, ColbertCache(64), with_colbert)
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    results = run_grid(questions, combos, scorer, final_k)
    elapsed = time.perf_counter() - started
    summary = summarize(results, combos, dev_ids, test_ids)
    payload = {
        "created_at": datetime.now(KST).isoformat(timespec="seconds"),
        "args": vars(args),
        "reference": {"path": str(reference), "source_sha256": alignment.get("source_sha256"), "excluded": excluded},
        "corpus": {"db_chunks": db_chunks, "sparse_index": len(index)},
        "model": model_info,
        "search": search_config,
        "filter": args.filter,
        "questions": len(questions),
        "split": {"seed": args.seed, "dev": dev_ids, "test": test_ids} if dev_ids is not None else None,
        "elapsed_sec": round(elapsed, 1),
        "gpu_max_memory_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3) if torch.cuda.is_available() else None,
        "colbert_cache": {"hits": cache.hits, "misses": cache.misses, "mb": round(cache.bytes / 2**20, 1), "items": len(cache.items)},
        "summary": summary,
        "per_question": results,
    }
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    logs = data_path(config, "logs_dir")
    out_json, out_csv = logs / f"eval_grid_{ts}.json", logs / f"eval_grid_{ts}_summary.csv"
    write_outputs(out_json, out_csv, payload)
    print_table(summary, combos)
    print(f"결과: {out_json}\n요약: {out_csv}", file=sys.stderr)
    return 0


def print_table(summary: dict, combos: list[dict]) -> None:
    subsets = ["all", "reviewed"] + (["dev", "test"] if "selection" in summary else [])
    header = f"{'조합':7s} {'d/s/c':16s}" + "".join(f" | {s}: C@5 C@10 GR@10 MRR" for s in subsets)
    print(header)
    for combo in combos:
        entry = summary["combos"][combo["id"]]
        w = combo["weights"]
        line = f"{combo['id']:7s} {w['dense']:.2f}/{w['sparse']:.2f}/{w['colbert']:.2f}  "
        for subset in subsets:
            m = entry[subset]
            line += f" | n={m['n']:3d} {m.get('complete@5', 0):.3f} {m.get('complete@10', 0):.3f} {m.get('group_recall@10', 0):.3f} {m.get('mrr', 0):.3f}"
        print(line)
    if "selection" in summary:
        print(f"dev 최고 조합: {summary['selection']['best_on_dev']} → test {summary['selection']['test_of_best']}")
    if "latency" in summary:
        print("예상 평균 지연(ms):", summary["latency"]["estimated_mean_ms"])


if __name__ == "__main__":
    raise SystemExit(main())
