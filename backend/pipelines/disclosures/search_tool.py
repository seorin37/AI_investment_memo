"""DB의 dense+sparse와 질의 시 ColBERT를 사용하는 공시 4:2:4 검색 CLI."""

from __future__ import annotations

import argparse
import json

from ..common.config import load_config
from ..common.db import get_engine
from ..common.logging import setup_logging
from .embedder import load_encoder, set_offline
from .search import ColbertCache, Filters, search_424
from .sparse_store import SparseIndex


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공시 검색 (dense 0.4 / sparse 0.2 / ColBERT 0.4)")
    ap.add_argument("query")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--symbol")
    ap.add_argument("--kind")
    ap.add_argument("--period-end")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true")
    args = ap.parse_args(argv)

    setup_logging()
    set_offline(args.offline)
    config = load_config(args.config)
    engine = get_engine()
    index = SparseIndex.from_engine(engine)
    encoder, _ = load_encoder(config["model"], args.offline, args.allow_cpu)
    cache = ColbertCache(float(config.get("colbert", {}).get("cache_max_mb", 2048)))
    hits = search_424(
        engine,
        encoder,
        index,
        args.query,
        Filters(symbol=args.symbol, kind=args.kind, period_end=args.period_end),
        config.get("search", {}),
        cache,
    )
    print(json.dumps([hit.to_dict() for hit in hits], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
