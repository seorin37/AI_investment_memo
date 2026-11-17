"""계산 지표 일괄 재계산·점검 (마이그레이션 0017).

    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_metrics            # 전체 다시 계산
    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_metrics --check    # 점검만 (읽기 전용)
    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_metrics --symbols 005930,000660

- 평소에는 재무 적재(financials_loader.upsert_*)가 자동으로 계산한다.
- 이 명령은 DB에 이미 있는 값으로 비율만 다시 계산한다. 이자비용(interest_cost)은 원천 응답에서 고르므로,
  처음 한 번은 `run_financials_all --force`(원천 캐시 사용)로 다시 적재해야 채워진다.
- --check: 회사별 최신 사업보고서 기준 지표별 값 있는 회사 수(일반/금융), NULL 사유별 건수, 이자비용 근거별 건수.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from sqlalchemy import text

from ..common.db import get_engine
from . import financial_metrics as fmx


def run(engine, only: list[str] | None) -> dict:
    with engine.connect() as conn:
        targets = fmx.symbols(conn, only)
    written = 0
    for s in targets:
        with engine.begin() as conn:
            written += fmx.recompute_symbol(conn, s)
    return {"companies": len(targets), "rows_written": written}


def check(engine, only: list[str] | None) -> dict:
    where = " AND m.symbol = ANY(:ss)" if only else ""
    params = {"ss": only} if only else {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT ON (m.symbol) m.symbol, s.sector::text AS sector, m.*"
            " FROM financial_metrics m JOIN stocks s USING (symbol)"
            f" WHERE m.period_type = 'annual'{where} ORDER BY m.symbol, m.period_end DESC"), params).mappings().all()
        all_rows = conn.execute(text(f"SELECT null_reasons, interest_cost_basis FROM financial_metrics m WHERE true{where}"),
                                params).mappings().all()
    latest: dict[str, dict] = {}
    for sector in ("general", "financial"):
        group = [r for r in rows if r["sector"] == sector]
        latest[sector] = {"companies": len(group),
                          **{c: sum(1 for r in group if r[c] is not None) for c in fmx.METRICS},
                          "interest_coverage_basis": dict(Counter(r["interest_coverage_basis"] for r in group if r["interest_coverage"] is not None))}
    reasons = Counter(f"{c}:{code}" for r in all_rows for c, code in (r["null_reasons"] or {}).items())
    return {"latest_annual": latest, "rows": len(all_rows),
            "interest_cost_basis": dict(Counter(r["interest_cost_basis"] for r in all_rows)),
            "null_reasons": dict(reasons.most_common())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="계산 지표 일괄 재계산·점검")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만")
    ap.add_argument("--check", action="store_true", help="점검만 (읽기 전용)")
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    engine = get_engine()
    if not args.check:
        print(json.dumps(run(engine, only), ensure_ascii=False, indent=1))
    print(json.dumps(check(engine, only), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
