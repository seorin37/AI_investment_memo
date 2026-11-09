"""금융사 건전성 비율(BIS·K-ICS·NCR)을 정기보고서 본문에서 뽑아 financials_fin에 쓴다 (docs/financials-ratios.md).

    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_ratios --dry-run   # 읽기만, 결과 파일만 남김
    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_ratios             # financials_fin UPDATE
    PYTHONPATH=backend python -m pipelines.disclosures.run_financial_ratios --symbols 105560,000810

흐름 (financials_fin 행 하나씩):
  1. stocks.fin_type으로 채울 비율을 정한다. 은행·지주 bis_ratio, 보험 kics_ratio, 증권 ncr_ratio.
     나머지 비율과 other 업종, 은행 없는 지주(financials_ratios.NOT_APPLICABLE_SYMBOLS)는 not_applicable.
  2. 같은 기간 정기보고서(disclosures)의 비율 키워드 청크와 그 앞뒤 청크를 읽어 financials_ratios.extract_ratio로 추출.
  3. 값이 있으면 UPDATE, 못 찾으면 NULL + null_reasons 사유. 이미 저장된 값은 NULL로 덮지 않는다.
  4. 직전 분기보다 크게 바뀐 값은 review.csv에 올린다 (값은 그대로 쓴다).

산출물 (data/financials_ratios/):
  results.json   행별 결과와 출처(청크 번호·행 이름·열 머리·잠정 여부·다른 후보 값)
  review.csv     검토할 것: 추출 실패·범위 밖, 다른 곳에서 같은 값이 안 보이는 값(uncorroborated), 큰 변동
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from pipelines.common.config import REPO_ROOT

from .financials_loader import FIN_RATIOS, set_ratio
from .financials_ratios import NOT_APPLICABLE_SYMBOLS, SPECS, extract_ratio, target_column

log = logging.getLogger("financial_ratios")

OUT_DIR = REPO_ROOT / "data" / "financials_ratios"
# 직전 분기 대비 이보다 크게 바뀌면 검토 (BIS·K-ICS는 %p, NCR은 상대 변화율)
JUMP_LIMITS = {"bis_ratio": ("abs", Decimal("3")), "kics_ratio": ("abs", Decimal("60")), "ncr_ratio": ("rel", Decimal("0.5"))}

ROWS_SQL = """
SELECT f.symbol, s.name, s.fin_type, f.period_end::text, f.period_type::text,
       f.bis_ratio, f.kics_ratio, f.ncr_ratio, f.null_reasons
FROM financials_fin f JOIN stocks s USING (symbol)
ORDER BY f.symbol, f.period_end
"""
REPORT_SQL = """
SELECT rcept_no FROM disclosures
WHERE symbol = :s AND period_end = CAST(:p AS date) AND kind IN ('annual', 'half', 'quarterly')
ORDER BY rcept_no DESC LIMIT 1
"""
CHUNKS_SQL = """
WITH hit AS (
    SELECT chunk_index FROM disclosure_chunks
    WHERE rcept_no = :r AND ({keywords})
)
SELECT c.chunk_index, c.section, c.chunk_text FROM disclosure_chunks c
WHERE c.rcept_no = :r
  AND c.chunk_index IN (SELECT chunk_index + d FROM hit, (VALUES (-1), (0), (1)) AS o(d))
ORDER BY c.chunk_index
"""


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="DB를 쓰지 않고 결과 파일만 남긴다 (읽기 전용 연결)")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드 (기본: financials_fin 전체)")
    ap.add_argument("--out", default=str(OUT_DIR), help="결과 폴더")
    return ap


def chunks_for(conn, rcept_no: str, column: str) -> list[tuple[int, str, str]]:
    keywords = " OR ".join(f"position(:k{i} in chunk_text) > 0" for i in range(len(SPECS[column].keywords)))
    params = {"r": rcept_no, **{f"k{i}": k for i, k in enumerate(SPECS[column].keywords)}}
    return [tuple(r) for r in conn.execute(text(CHUNKS_SQL.format(keywords=keywords)), params).all()]


def decide(conn, row: dict) -> dict[str, dict]:
    """행 하나의 세 비율 결정: {column: {value, null_code, reason, source, rcept_no}}."""
    wanted = target_column(row["symbol"], row["fin_type"])
    out: dict[str, dict] = {}
    for column in FIN_RATIOS:
        if column != wanted:
            reason = NOT_APPLICABLE_SYMBOLS.get(column, {}).get(row["symbol"]) or f"{row['fin_type'] or '일반'} 업종에는 해당 없음"
            out[column] = {"value": None, "null_code": "not_applicable", "reason": reason}
    if wanted is None:
        return out
    rcept_no = conn.execute(text(REPORT_SQL), {"s": row["symbol"], "p": row["period_end"]}).scalar()
    if rcept_no is None:
        out[wanted] = {"value": None, "null_code": "extract_failed", "reason": "정기보고서 본문 미수집", "rcept_no": None}
        return out
    result = extract_ratio(wanted, chunks_for(conn, rcept_no, wanted), row["period_end"], row["period_type"])
    out[wanted] = {"value": result.value, "null_code": result.null_code, "reason": result.reason,
                   "source": result.source, "rcept_no": rcept_no}
    return out


def jumps(results: list[dict]) -> list[dict]:
    """같은 종목·비율의 직전 기간 값 대비 큰 변동."""
    flagged = []
    last: dict[tuple[str, str], tuple[str, Decimal]] = {}
    for item in sorted(results, key=lambda r: (r["symbol"], r["period_end"])):
        for column, decision in item["ratios"].items():
            value = decision.get("value")
            if value is None:
                continue
            key = (item["symbol"], column)
            if key in last:
                prev_period, prev = last[key]
                mode, limit = JUMP_LIMITS[column]
                change = abs(value - prev) if mode == "abs" else abs(value - prev) / prev
                if change > limit:
                    flagged.append({**_ident(item), "column": column, "value": value,
                                    "issue": f"직전 {prev_period} {prev} → {value}"})
            last[key] = (item["period_end"], value)
    return flagged


def _ident(item: dict) -> dict:
    return {"symbol": item["symbol"], "name": item["name"], "period_end": item["period_end"]}


def write_row(conn, row: dict, decisions: dict[str, dict]) -> list[str]:
    """비율 세 개를 쓴다. 저장된 값을 NULL로 덮지 않는다. 남길 실패 메시지 반환."""
    failures = []
    for column, decision in decisions.items():
        value, code = decision["value"], decision["null_code"]
        if value is None and row[column] is not None:
            failures.append(f"{row['symbol']} {row['period_end']} {column}: 추출 실패 — 기존 값 {row[column]} 유지 ({decision['reason']})")
            continue
        if value is None and (row["null_reasons"] or {}).get(column) == code and row[column] is None:
            continue  # 이미 같은 사유
        if value is not None and row[column] == value and column not in (row["null_reasons"] or {}):
            continue  # 이미 같은 값
        set_ratio(conn, row["symbol"], row["period_end"], row["period_type"], column, value, code)
    return failures


def review_rows(results: list[dict]) -> list[dict]:
    rows = []
    for item in results:
        for column, decision in item["ratios"].items():
            code = decision.get("null_code")
            if code == "not_applicable":
                continue
            source = decision.get("source") or {}
            if decision["value"] is None:
                rows.append({**_ident(item), "column": column, "value": "", "issue": f"{code}: {decision['reason']}"})
            elif not source.get("corroborated"):
                rows.append({**_ident(item), "column": column, "value": decision["value"],
                             "issue": "uncorroborated: 보고서 다른 곳에서 같은 값이 안 보임"})
    return rows + jumps(results)


def run(engine, args) -> dict:
    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()}
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    failures: list[str] = []
    counts: Counter = Counter()
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(text(ROWS_SQL)).all()]
    rows = [r for r in rows if not symbols or r["symbol"] in symbols]
    for row in rows:
        with engine.connect() as conn:
            decisions = decide(conn, row)
        for column, decision in decisions.items():
            counts[(column, "value" if decision["value"] is not None else decision["null_code"])] += 1
        results.append({**_ident(row), "fin_type": row["fin_type"], "period_type": row["period_type"], "ratios": decisions})
        if not args.dry_run:
            with engine.begin() as conn:
                failures.extend(write_row(conn, row, decisions))
    review = review_rows(results)
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with (out_dir / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "period_end", "column", "value", "issue"])
        writer.writeheader()
        writer.writerows(review)
    summary = {
        "mode": "dry-run" if args.dry_run else "write",
        "rows": len(rows),
        "counts": {f"{c} {k}": n for (c, k), n in sorted(counts.items())},
        "review": len(review),
        "failures": failures,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    from pipelines.common.db import get_engine, get_read_engine

    engine = get_read_engine() if args.dry_run else get_engine()
    summary = run(engine, args)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"결과: {Path(args.out) / 'results.json'}, 검토: {Path(args.out) / 'review.csv'}")
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
