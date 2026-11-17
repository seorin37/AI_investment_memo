"""사건 공시 표준 비율 일괄 계산·점검 (마이그레이션 0018, 2026-11-17).

    PYTHONPATH=backend python -m pipelines.disclosures.run_event_metrics              # 전체 계산·저장
    PYTHONPATH=backend python -m pipelines.disclosures.run_event_metrics --dry-run    # 계산만 (DB에 쓰지 않음, 0018 전 DB에서도 됨)
    PYTHONPATH=backend python -m pipelines.disclosures.run_event_metrics --check      # 저장된 표 점검 (읽기 전용)
    PYTHONPATH=backend python -m pipelines.disclosures.run_event_metrics --symbols 012450,005930

- 계산은 event_metrics.compute (분모는 공시 접수일 전 값). 저장은 rcept_no 단위 upsert라 여러 번 돌려도 같다.
- --dry-run은 읽기 전용 연결로 계산만 하고 사건 종류별 지표 커버·사유·예시를 출력한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

from sqlalchemy import text

from ..common.db import get_engine, get_read_engine
from . import event_metrics as em


def summarize(rows: list[dict], samples: int = 2) -> dict:
    by_type: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["event_type"]].append(r)
    for t, rs in sorted(groups.items()):
        by_type[t] = {"events": len(rs),
                      "metrics": dict(Counter(k for r in rs for k in r["metrics"])),
                      "null_reasons": dict(Counter(f"{k}:{v}" for r in rs for k, v in r["null_reasons"].items()).most_common()),
                      "examples": [{"rcept_no": r["rcept_no"], "symbol": r["symbol"], "metrics": r["metrics"]}
                                   for r in rs if r["metrics"]][:samples]}
    return {"events": len(rows), "by_type": by_type}


def run(engine, only: list[str] | None, write: bool) -> dict:
    with engine.connect() as conn:
        evs = em.events(conn, only)
        rows = [em.compute_row(conn, ev) for ev in evs]
    if write:
        with engine.begin() as conn:
            for r in rows:
                em.save(conn, r)
    return summarize(rows)


def check(engine, only: list[str] | None) -> dict:
    where = " WHERE symbol = ANY(:ss)" if only else ""
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(
            f"SELECT rcept_no, symbol, event_type, metrics, null_reasons FROM disclosure_event_metrics{where}"),
            {"ss": only} if only else {}).mappings().all()]
        missing = conn.execute(text(
            "SELECT count(*) FROM disclosure_events e WHERE e.event_type = ANY(:t)"
            " AND NOT EXISTS (SELECT 1 FROM disclosure_event_metrics m WHERE m.rcept_no = e.rcept_no)"),
            {"t": list(em.EVENT_TYPES)}).scalar()
    out = summarize(rows, samples=0)
    out["events_without_metrics"] = missing
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사건 공시 표준 비율 계산·점검")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만")
    ap.add_argument("--dry-run", action="store_true", help="계산만 하고 저장하지 않는다")
    ap.add_argument("--check", action="store_true", help="저장된 표 점검만 (읽기 전용)")
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    if args.check:
        print(json.dumps(check(get_engine(), only), ensure_ascii=False, indent=1, default=str))
        return 0
    engine = get_read_engine() if args.dry_run else get_engine()   # dry-run은 읽기 전용 연결 (중앙 DB에서도 안전)
    print(json.dumps(run(engine, only, write=not args.dry_run), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
