#!/usr/bin/env python3
"""수정주가 이력 이상징후 진단 (수동 실행 전용, DB 읽기 전용).

    PYTHONPATH=backend .venv/bin/python scripts/diagnose_adjusted_history.py
    PYTHONPATH=backend .venv/bin/python scripts/diagnose_adjusted_history.py --symbols 047400 101140
    PYTHONPATH=backend .venv/bin/python scripts/diagnose_adjusted_history.py --start 2026-10-01 --end 2026-11-13

- READONLY_DATABASE_URL만 쓴다 (DATABASE_URL로 대신하지 않는다). 연결을 읽기 전용으로 열고 확인한 뒤 SELECT만 한다.
- KIS/KRX/DART API를 부르지 않고, 수정주가를 다시 받거나 DB를 고치지 않는다.
- 결과는 logs/diagnostics/adjusted_history/<KST 시각>/findings.json, summary.md (매번 새 폴더).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pipelines.common.db import get_read_dsn, load_env
from pipelines.market import adjusted_history_diagnostics as diag
from pipelines.market.calendar import CALENDAR_END, CALENDAR_START, is_krx_trading_day
from pipelines.market.symbol_status import load_symbol_statuses
from pipelines.updates.preferred import STOCKS_SQL, build_map

DEFAULT_OUTPUT_ROOT = Path("logs/diagnostics/adjusted_history")
SYMBOL_BATCH = 100
CONTEXT_DAYS = 45  # --start 이전 행도 읽어 첫날 수익률을 계산한다

SYMBOLS_SQL = "SELECT DISTINCT btrim(symbol) FROM adjusted_prices_daily ORDER BY 1"
PRICES_SQL = """
SELECT btrim(symbol) AS symbol, trade_date, p.close AS raw_close, p.volume, a.close AS adj_close, a.collected_at
FROM prices_daily p
FULL OUTER JOIN adjusted_prices_daily a USING (symbol, trade_date)
WHERE btrim(symbol) = ANY(%(symbols)s)
  AND (%(start)s::date IS NULL OR trade_date >= %(start)s::date)
  AND (%(end)s::date IS NULL OR trade_date <= %(end)s::date)
ORDER BY 1, trade_date
"""
COVERAGE_SQL = "SELECT min(d.rcept_dt) FROM disclosure_events e JOIN disclosures d USING (rcept_no)"
EVENTS_SQL = """
SELECT e.rcept_no, btrim(d.symbol) AS symbol, d.title, d.rcept_dt, e.event_type, e.base_title,
       e.is_correction, e.is_subsidiary, e.corrects, e.parse_status, e.pairs,
       NOT EXISTS (SELECT 1 FROM disclosure_events x WHERE x.corrects = e.rcept_no) AS is_latest
FROM disclosure_events e JOIN disclosures d USING (rcept_no)
WHERE e.event_type = ANY(%(types)s) AND btrim(d.symbol) = ANY(%(symbols)s)
  AND e.parse_status <> 'failed'
"""


class ReadOnlyRequired(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    t = diag.Thresholds()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="+", help="진단할 종목코드 (기본: 수정주가가 있는 전체 종목)")
    ap.add_argument("--start", type=date.fromisoformat, help="보고 시작일 (YYYY-MM-DD)")
    ap.add_argument("--end", type=date.fromisoformat, help="보고 종료일 (YYYY-MM-DD)")
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    ap.add_argument("--no-disclosures", action="store_true", help="공시 연결을 건너뛴다")
    ap.add_argument("--focus", nargs="*", default=["047400", "101140"], help="요약 보고서에 따로 보일 종목")
    ap.add_argument("--ratio-jump", type=float, default=t.ratio_jump)
    ap.add_argument("--adjusted-only-raw-max", type=float, default=t.adjusted_only_raw_max)
    ap.add_argument("--adjusted-only-adj-min", type=float, default=t.adjusted_only_adj_min)
    ap.add_argument("--zero-volume-return", type=float, default=t.zero_volume_return)
    ap.add_argument("--price-limit", type=float, default=t.price_limit)
    ap.add_argument("--gap-sessions", type=int, default=t.gap_sessions)
    args = ap.parse_args(argv)
    if args.start and args.end and args.start > args.end:
        ap.error("--start가 --end보다 늦습니다.")
    return args


def thresholds_from(args: argparse.Namespace) -> diag.Thresholds:
    return diag.Thresholds(
        ratio_jump=args.ratio_jump,
        adjusted_only_raw_max=args.adjusted_only_raw_max,
        adjusted_only_adj_min=args.adjusted_only_adj_min,
        zero_volume_return=args.zero_volume_return,
        price_limit=args.price_limit,
        gap_sessions=args.gap_sessions,
    )


def connect_read_only(environ=None):
    """READONLY_DATABASE_URL로만 연결하고, 세션이 읽기 전용인지 확인한다."""
    import psycopg

    if environ is None:
        load_env()
        environ = os.environ
    if not environ.get("READONLY_DATABASE_URL"):
        raise ReadOnlyRequired("READONLY_DATABASE_URL이 없습니다. 쓰기 URL로 대신 실행하지 않습니다.")
    conn = psycopg.connect(get_read_dsn(environ), options="-c default_transaction_read_only=on")
    conn.read_only = True
    verify_read_only(conn)
    return conn


def verify_read_only(conn) -> None:
    value = conn.execute("SHOW transaction_read_only").fetchone()[0]
    if str(value).lower() != "on":
        conn.close()
        raise ReadOnlyRequired("DB 세션이 읽기 전용이 아니어서 중단합니다.")


class SessionCounter:
    """두 거래일 사이에 빠진 KRX 거래일 수. 캘린더 범위 밖은 평일 수로 센다."""

    def __init__(self) -> None:
        self._cache: dict[date, bool] = {}

    def _is_session(self, day: date) -> bool:
        if day not in self._cache:
            if CALENDAR_START <= day <= CALENDAR_END:
                self._cache[day] = is_krx_trading_day(day)
            else:
                self._cache[day] = day.weekday() < 5
        return self._cache[day]

    def __call__(self, prev: date, cur: date) -> int:
        if (cur - prev).days <= 1:
            return 0
        return sum(self._is_session(prev + timedelta(days=i)) for i in range(1, (cur - prev).days))


def load_rows(conn, symbols: list[str], start: date | None, end: date | None):
    context_start = start - timedelta(days=CONTEXT_DAYS) if start else None
    with conn.cursor() as cur:
        cur.execute(PRICES_SQL, {"symbols": symbols, "start": context_start, "end": end})
        for symbol, trade_date, raw_close, volume, adj_close, collected_at in cur:
            yield diag.PriceRow(symbol, trade_date, raw_close, adj_close, volume, collected_at)


def analyze(conn, args: argparse.Namespace, *, now: datetime | None = None) -> dict:
    thresholds = thresholds_from(args)
    stocks = conn.execute(STOCKS_SQL).fetchall()
    names = {s: n for s, n, _, _ in stocks}
    pref_map, _ = build_map(stocks)
    symbols = args.symbols or [r[0] for r in conn.execute(SYMBOLS_SQL).fetchall()]
    counter = SessionCounter()

    findings: list[diag.Finding] = []
    issues: dict[str, dict] = {}
    rows_loaded = 0
    for i in range(0, len(symbols), SYMBOL_BATCH):
        batch = symbols[i:i + SYMBOL_BATCH]
        per_symbol: dict[str, list[diag.PriceRow]] = {}
        for row in load_rows(conn, batch, args.start, args.end):
            per_symbol.setdefault(row.symbol, []).append(row)
            rows_loaded += 1
        for symbol in batch:
            observations, symbol_issues = diag.build_observations(per_symbol.get(symbol, []), counter)
            if args.start:
                observations = [o for o in observations if o.trade_date >= args.start]
            findings += diag.detect(observations, thresholds, names)
            big_gaps = [g for g in symbol_issues["gaps"] if g["missing_sessions"] >= thresholds.gap_sessions]
            compact = {
                "raw_missing": len(symbol_issues["raw_missing"]),
                "adjusted_missing": len(symbol_issues["adjusted_missing"]),
                "invalid_price": symbol_issues["invalid_price"],
                "gaps_over_threshold": big_gaps,
            }
            if any(compact.values()):
                compact["raw_missing_dates"] = symbol_issues["raw_missing"][-10:]
                compact["adjusted_missing_dates"] = symbol_issues["adjusted_missing"][-10:]
                issues[symbol] = compact
        conn.rollback()  # 배치마다 읽기 트랜잭션을 닫는다

    coverage_start = None
    if not args.no_disclosures and findings:
        coverage_start = conn.execute(COVERAGE_SQL).fetchone()[0]
        common = sorted({pref_map.get(f.symbol, f.symbol) for f in findings})
        with conn.cursor() as cur:
            cur.execute(EVENTS_SQL, {"types": list(diag.CORPORATE_ACTION_EVENT_TYPES), "symbols": common})
            columns = [c.name for c in cur.description]
            events = [dict(zip(columns, r)) for r in cur.fetchall()]
        conn.rollback()
        diag.link_disclosures(
            findings, events, thresholds,
            coverage_start=coverage_start,
            common_symbol=lambda s: pref_map.get(s, s),
            parse_date=diag.parse_disclosure_date,
        )
    diag.annotate_symbol_status(findings, load_symbol_statuses())
    episodes = diag.group_episodes(findings, thresholds.episode_rows)
    generated = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "meta": {
            "generated_at": generated,
            "read_only_verified": True,
            "symbols_analyzed": len(symbols),
            "rows_loaded": rows_loaded,
            "start": args.start.isoformat() if args.start else None,
            "end": args.end.isoformat() if args.end else None,
            "thresholds": diag.asdict(thresholds),
            "dart_coverage_start": coverage_start.isoformat() if coverage_start else None,
            "disclosure_event_types": list(diag.CORPORATE_ACTION_EVENT_TYPES),
            "preferred_mapped": sum(s in pref_map for s in symbols),
            "note": "탐지는 원인 미확인 검증 대상. DB·수집 데이터는 바꾸지 않았다.",
        },
        "summary": diag.summarize(findings, episodes),
        "episodes": episodes,
        "findings": diag.finding_dicts(sorted(findings, key=lambda f: (f.symbol, f.trade_date))),
        "data_issues": issues,
        "data_issue_counts": dict(Counter(
            key for v in issues.values() for key in ("raw_missing", "adjusted_missing", "invalid_price", "gaps_over_threshold") if v[key]
        )),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        conn = connect_read_only()
    except ReadOnlyRequired as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        report = analyze(conn, args)
    finally:
        conn.close()
    out_dir = diag.new_output_dir(args.output_root)
    json_path, md_path = diag.write_report(out_dir, report, focus=args.focus)
    s = report["summary"]
    print(f"탐지 {s['findings']}건 · 묶음 {s['episodes']}개 · 종목 {s['symbols']}개")
    print(f"유형별 {s['by_type']}")
    print(f"심각도 {s['by_severity']}")
    print(f"결과: {json_path}\n요약: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
