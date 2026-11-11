"""다른 종목 자료와의 유사도로 임계값의 '하한선'(noise floor)을 구한다. 사람이 표시할 필요 없음 (DB 읽기 전용).

아이디어: 삼성전자 메모 항목과 KB금융 자료는 관련이 없다고 볼 수 있다. 그 유사도 분포는 "관련 없는 자료도 이 정도 점수는 나온다"는 바닥이다.
실제 후보와 같은 방식(종류별 상위 k건)으로 재서, 상위 백분위(p90/p95/p99)를 하한선으로 쓴다.
한계: 같은 종목 안의 관련 없는 자료는 걸러내지 못한다. 비슷한 업종은 바닥선이 높게 나온다 (그래서 기본은 업종이 다른 종목만 쓴다).
재현율은 알 수 없고, 엉뚱한 자료가 새는 비율만 알 수 있다.

    PYTHONPATH=backend python -m pipelines.updates.noise_floor --limit 30
    PYTHONPATH=backend python -m pipelines.updates.noise_floor --limit 30 --news-search chunks   # 원문 청크 검색의 하한선(news_chunks)
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path

from ..common.config import load_config, resolve_path
from .candidates import disclosure_candidates, news_candidates
from .experiment import PILOT, load_items
from .results import new_run_dir

PERCENTILES = (90, 95, 99)


def percentile(values: list[float], p: float) -> float | None:
    """선형 보간 없는 단순 백분위 (nearest-rank, 올림). 값이 없으면 None."""
    if not values:
        return None
    xs = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(xs)))
    return xs[rank - 1]


def choose_negatives(symbol: str, sectors: dict[str, str], universe: tuple[str, ...], mode: str = "different-sector") -> list[str]:
    """이 종목의 '관련 없는 자료' 쪽 종목들. different-sector는 업종이 다른 종목만 쓰고, 없으면 나머지 전부로 대신한다."""
    others = [s for s in universe if s != symbol]
    if mode == "all":
        return others
    diff = [s for s in others if sectors.get(s) and sectors.get(s) != sectors.get(symbol)]
    return diff or others


def summarize(sims: dict[str, list[float]], percentiles=PERCENTILES) -> dict:
    return {kind: {"n": len(v), **{f"p{p}": (round(percentile(v, p), 4) if v else None) for p in percentiles}}
            for kind, v in sims.items()}


def floor_for(summary: dict, kind: str, key: str = "p95") -> float | None:
    """하한선을 0.01 단위로 올림 (그 값 미만은 바닥에서 흔한 점수)."""
    v = (summary.get(kind) or {}).get(key)
    return None if v is None else math.ceil(v * 100 - 1e-9) / 100


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="다른 종목 자료로 임계값 하한선 구하기 (DB 읽기 전용)")
    ap.add_argument("--gold", default="eval/memo_eval_v0/memo_eval_v0.jsonl")
    ap.add_argument("--config", default="configs/updates.yaml")
    ap.add_argument("--symbols", default=",".join(PILOT))
    ap.add_argument("--limit", type=int, help="앞에서 N개 항목만")
    ap.add_argument("--negatives", choices=["different-sector", "all"], default="different-sector")
    ap.add_argument("--since", help="뉴스 시작일 YYYY-MM-DD (기본: 설정의 lookback_days 전)")
    ap.add_argument("--disclosure-since", default="2024-01-01")
    ap.add_argument("--out-dir", help="결과 폴더 (기본: results/updates)")
    ap.add_argument("--news-search", choices=["article", "chunks"], default="article",
                    help="chunks면 원문 청크 검색(news_search)의 하한선도 잰다 (news_chunks)")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from ..news.embedder import make_bge_m3_encoder

    cfg = load_config(args.config)
    universe = tuple(args.symbols.split(","))
    items = [i for i in load_items(resolve_path(args.gold), universe) if i.type == "topic"]
    if args.limit:
        items = items[:args.limit]
    since = date.fromisoformat(args.since) if args.since else date.today() - timedelta(days=cfg["news"]["lookback_days"])
    d_since = date.fromisoformat(args.disclosure_since)
    encode = make_bge_m3_encoder("dense")
    vectors = [d for d, _ in encode([it.query_text for it in items])]
    searcher = None
    sims: dict[str, list[float]] = {"news": [], "disclosure": []}
    if args.news_search == "chunks":
        from .news_search import load_query_encoder, release_gpu
        del encode                                              # 제목+요약 인코더를 내리고 원문 청크용 인코더를 올린다 (GPU 메모리)
        release_gpu()
        chunk_encoder = load_query_encoder()
        sims["news_chunks"] = []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, sector::text FROM stocks WHERE symbol = ANY(%(s)s)", {"s": list(universe)})
            sectors = {sym.strip(): sec for sym, sec in cur.fetchall()}
        if args.news_search == "chunks":
            from .news_search import NewsChunkSearch
            searcher = NewsChunkSearch(conn, chunk_encoder, cfg["news"].get("chunks"))
        for item, vec in zip(items, vectors):
            for other in choose_negatives(item.symbol, sectors, universe, args.negatives):
                if searcher is not None:
                    for c in searcher.articles(other, item.query_text, since)[:cfg["news"]["top_k"]]:
                        sims["news_chunks"].append(c.similarity)
                for c in news_candidates(conn, other, vec, since, cfg["news"]["top_k"], cfg["news"]["variant"]):
                    sims["news"].append(c.similarity)
                for c in disclosure_candidates(conn, other, vec, d_since, cfg["disclosure"]["top_k"]):
                    sims["disclosure"].append(c.similarity)

    summary = summarize(sims)
    out = new_run_dir(args.out_dir)
    (out / "noise_floor.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 임계값 하한선 (다른 종목 자료와의 유사도)", f"- 항목 {len(items)}개, 비교 방식 {args.negatives}", ""]
    for kind, s in summary.items():
        lines.append(f"- {kind}: 표본 {s['n']}건, " + ", ".join(f"p{p} {s[f'p{p}']}" for p in PERCENTILES))
    lines += ["", "p95는 '관련 없는 자료의 95%가 이 점수 이하'라는 뜻입니다. 임계값을 이보다 낮게 두면 엉뚱한 자료가 5% 넘게 통과합니다.",
              f"`python -m pipelines.updates.calibrate --labels <candidates_auto_<모델>.csv> --noise-floor {out / 'noise_floor.json'}` 로 정밀도 기준 추천과 합칩니다."]
    (out / "noise_floor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"결과 폴더: {out} — DB에는 아무것도 쓰지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
