"""분기 단독 손익 일괄 계산·검증 (마이그레이션 0016).

    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_quarterly            # 전체 다시 계산
    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_quarterly --dry-run  # 쓰지 않고 건수만
    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_quarterly --check    # 검증만 (읽기 전용)
    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_quarterly --symbols 005930,000660

- 평소에는 재무 적재(financials_loader.upsert_*)가 자동으로 계산한다. 이 명령은 처음 한 번(기존 행 전체)과 점검용.
- 다시 실행해도 결과가 같다(회사·회계연도 단위로 지우고 다시 쓴다). 회사 하나당 트랜잭션 하나.
- --check: Q1+Q2+Q3+Q4 = annual, Q1+Q2 = half, Q1+Q2+Q3 = q3 (값이 모두 있는 경우)와 NULL 사유별 건수.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

from sqlalchemy import text

from ..common.db import get_engine
from . import financials_quarterly as fq


def run(engine, symbols: list[str] | None, dry_run: bool) -> dict:
    summary = {}
    for kind in ("general", "fin"):
        with engine.connect() as conn:
            years = fq.fiscal_years(conn, kind, symbols)
        by_symbol: dict[str, list] = defaultdict(list)
        for s, fy in years:
            by_symbol[s].append(fy)
        written = 0
        if not dry_run:
            for s, fys in by_symbol.items():
                with engine.begin() as conn:
                    for fy in fys:
                        written += fq.recompute(conn, kind, s, fy)
        summary[kind] = {"companies": len(by_symbol), "fiscal_years": len(years), "rows_written": written}
    return summary


def check(engine, symbols: list[str] | None) -> dict:
    """원천 누적값과 분기 합을 대조한다. 읽기 전용."""
    report = {}
    with engine.connect() as conn:
        for kind, spec in fq.TABLES.items():
            where = " WHERE symbol = ANY(:ss)" if symbols else ""
            params = {"ss": symbols} if symbols else {}
            q = conn.execute(text(f"SELECT symbol, fiscal_year_end, quarter, {', '.join(spec['flows'])}, null_reasons"
                                  f" FROM {spec['target']}{where}"), params).mappings().all()
            src = conn.execute(text(f"SELECT symbol, period_end, period_type::text AS period_type, {', '.join(spec['flows'])}"
                                    f" FROM {spec['source']}{where}"), params).mappings().all()
            quarters: dict[tuple, dict[int, dict]] = defaultdict(dict)
            reasons = Counter()
            for r in q:
                quarters[(r["symbol"].strip(), r["fiscal_year_end"])][r["quarter"]] = r
                for col, code in (r["null_reasons"] or {}).items():
                    reasons[f"{col}:{code}"] += 1
            target_q = {"q1": 1, "half": 2, "q3": 3, "annual": 4}
            checked = mismatched = 0
            examples = []
            for r in src:
                key = (r["symbol"].strip(), fq.fiscal_year_end(r["period_end"], r["period_type"]))
                upto = target_q[r["period_type"]]
                got = quarters.get(key, {})
                for col in spec["flows"]:
                    parts = [got.get(i, {}).get(col) for i in range(1, upto + 1)]
                    if r[col] is None or any(p is None for p in parts):
                        continue
                    checked += 1
                    if sum(parts) != r[col]:
                        mismatched += 1
                        if len(examples) < 5:
                            examples.append({"symbol": key[0], "period_end": str(r["period_end"]), "col": col,
                                             "cumulative": str(r[col]), "sum_of_quarters": str(sum(parts))})
            report[kind] = {"quarter_rows": len(q), "sums_checked": checked, "sums_mismatched": mismatched,
                            "examples": examples, "null_reasons": dict(reasons.most_common())}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="분기 단독 손익 일괄 계산·검증")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 대상 건수만")
    ap.add_argument("--check", action="store_true", help="검증만 (읽기 전용)")
    args = ap.parse_args(argv)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    engine = get_engine()
    if args.check:
        report = check(engine, symbols)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if all(v["sums_mismatched"] == 0 for v in report.values()) else 1
    summary = run(engine, symbols, args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if not args.dry_run:
        print(json.dumps(check(engine, symbols), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
