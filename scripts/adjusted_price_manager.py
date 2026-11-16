#!/usr/bin/env python3
"""수정주가 관리: 감지 → 제한적 KIS 재조회 → 재동기화 계획(dry-run) → 승인 후 적용.

    # 1) 감지 (DB 읽기 전용, API 호출 없음)
    PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py detect
    # 2) 제한적 재조회 (후보 종목만, 요청 상한 적용)
    PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py recheck --max-symbols 5 --max-requests 10
    # 3) 재동기화 계획 (dry-run: KIS 전체 이력 조회 + 검증, DB 쓰기 없음)
    PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-plan --symbols 047400
    # 4) 승인 후 적용 (adjusted_prices_daily 해당 종목만, 한 트랜잭션)
    PYTHONPATH=backend .venv/bin/python scripts/adjusted_price_manager.py resync-apply --plan <plan.json> \
        --symbol 047400 --confirm <plan의 sha256> --i-understand-this-writes-db

결과: logs/diagnostics/adjusted_price_manager/<KST 시각>_<단계>/ (매번 새 폴더).
상태: logs/market/adjusted_price_state/state.json (재조회 결과·중복 억제).
KIS 원천 수정주가를 다시 계산하거나 보정하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # scripts 패키지(diagnose_adjusted_history)를 불러오기 위해
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.market import adjusted_history_diagnostics as diag
from pipelines.market import corporate_actions as ca
from pipelines.market.symbol_status import load_symbol_statuses
from pipelines.updates.preferred import STOCKS_SQL, build_map
from scripts import diagnose_adjusted_history as price_cli

KST = timezone(timedelta(hours=9))
OUTPUT_ROOT = Path("logs/diagnostics/adjusted_price_manager")
STATE_PATH = Path("logs/market/adjusted_price_state/state.json")

EVENTS_SQL = """
SELECT e.rcept_no, btrim(d.symbol) AS symbol, d.title, d.rcept_dt, e.event_type, e.base_title,
       e.is_correction, e.is_subsidiary, e.corrects, e.correction, e.parse_status, e.fields, e.pairs
FROM disclosure_events e JOIN disclosures d USING (rcept_no)
WHERE e.event_type = ANY(%(types)s)
ORDER BY e.rcept_no
"""
COVERAGE_SQL = "SELECT min(d.rcept_dt) FROM disclosure_events e JOIN disclosures d USING (rcept_no)"


def now_kst() -> datetime:
    return datetime.now(KST)


def new_run_dir(step: str, root: Path = OUTPUT_ROOT) -> Path:
    path = root / f"{now_kst():%Y%m%dT%H%M%S}_{step}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: Path, payload) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")


def latest_output(step: str, filename: str, root: Path = OUTPUT_ROOT) -> Path | None:
    runs = sorted(p for p in root.glob(f"*_{step}") if (p / filename).exists()) if root.exists() else []
    return runs[-1] / filename if runs else None


# ---------------------------------------------------------------- detect


def load_events(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(EVENTS_SQL, {"types": list(ca.ACTION_EVENT_TYPES + ca.AUXILIARY_EVENT_TYPES)})
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.rollback()
    return rows


def run_detect(conn, args, *, state: dict | None = None) -> dict:
    as_of = args.as_of or now_kst().date()
    stocks = conn.execute(STOCKS_SQL).fetchall()
    conn.rollback()
    names = {s: n for s, n, _, _ in stocks}
    pref_map, _ = build_map(stocks)
    terminal = load_symbol_statuses()

    if args.price_report:
        price_report = json.loads(Path(args.price_report).read_text(encoding="utf-8"))
        price_source = str(args.price_report)
    else:
        price_args = price_cli.parse_args(["--no-disclosures"] + (["--start", args.price_start.isoformat()] if args.price_start else []))
        price_report = price_cli.analyze(conn, price_args)
        price_source = "computed"
    events = [ca.extract_event(r) for r in load_events(conn)]
    coverage = conn.execute(COVERAGE_SQL).fetchone()[0]
    conn.rollback()
    groups = ca.group_events(events)
    candidates = ca.build_candidates(
        groups, as_of=as_of, names=names, preferred_of_common=ca.preferred_of_common(pref_map),
        terminal=terminal, horizon_days=args.horizon_days, window_days=args.window_days,
    )
    verified = {s: v for s, v in ((state or {}).get("symbols") or {}).items() if v.get("status")}
    items = ca.integrate(price_report["findings"], candidates, terminal=terminal, verified=verified,
                         window_days=args.window_days)
    for it in items:  # 보류 표시 (자동 재조회·재동기화 제외는 recheck·resync가 상태 파일로 강제한다)
        hold = ((state or {}).get("symbols", {}).get(it["symbol"]) or {}).get("hold")
        if hold:
            it["hold"] = hold
            it["reasons"].append(f"hold:{hold['reason']}")
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    phases: dict[str, int] = {}
    for c in candidates:
        if c.source == "disclosure":
            phases[c.schedule_phase] = phases.get(c.schedule_phase, 0) + 1
    return {
        "meta": {
            "generated_at": now_kst().isoformat(), "as_of": as_of.isoformat(), "read_only_verified": True,
            "price_report_source": price_source, "dart_coverage_start": coverage.isoformat() if coverage else None,
            "events_loaded": len(events), "groups": len(groups), "horizon_days": args.horizon_days,
        },
        "summary": {
            "items": len(items), "by_status": counts,
            "recheck_recommended": sorted(it["symbol"] for it in items if it["recheck_recommended"]),
            "on_hold": sorted(it["symbol"] for it in items if it.get("hold")),
            "price_findings": len(price_report["findings"]),
            "disclosure_groups_by_phase": phases,
            "disclosure_groups_by_type": _count(g.event_type for g in groups),
            "subsidiary_groups": sum(g.is_subsidiary for g in groups),
            "unresolved_groups": sum(g.resolution != "resolved" for g in groups),
            "schedule_changed_groups": sum(g.schedule_changed for g in groups),
        },
        "items": items,
        "groups": [asdict(g) for g in groups],
    }


def _count(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def render_detect(report: dict) -> str:
    s, m = report["summary"], report["meta"]
    lines = [
        "# 수정주가 관리: 감지", "",
        f"- 기준일 {m['as_of']} · 공시 데이터 시작일 {m['dart_coverage_start']} · 가격 탐지 {m['price_report_source']}",
        f"- 관리 항목 {s['items']}개 · 상태 {s['by_status']}",
        f"- 재조회 권장 {len(s['recheck_recommended'])}종목: {', '.join(s['recheck_recommended']) or '-'}",
        f"- 공시 묶음 종류 {s['disclosure_groups_by_type']} · 일정 {s['disclosure_groups_by_phase']}",
        f"- 자회사 공시 묶음 {s['subsidiary_groups']} · 최신본 미확정 {s['unresolved_groups']} · 정정으로 일정 변경 {s['schedule_changed_groups']}",
        "", "## 재조회 권장·검토 항목", "",
        "| 종목 | 상태 | 가격 이상 | 공시 | 재조회 구간 | 사유 |", "|---|---|---|---|---|---|",
    ]
    for it in report["items"]:
        if it["status"] in (ca.NORMAL_ADJUSTMENT, ca.NO_ACTION) and not it["recheck_recommended"]:
            continue
        price = "; ".join(f"{f['trade_date']} {f['assessment']}" for f in it["price_findings"] if f["severity"] != "info")[:120]
        disc = "; ".join(
            f"{c['event_type']} {c['latest_rcept_no']} {c['schedule_phase']}{' (자회사)' if c['is_subsidiary'] else ''}"
            f"{' ←' + c['derived_from'] if c.get('derived_from') else ''}"
            for c in it["disclosure_candidates"])[:160]
        lines.append(f"| {it['symbol']} {it['name'] or ''} | {it['status']} | {price or '-'} | {disc or '-'} | "
                     f"{it['recheck_windows'] or '-'} | {'; '.join(it['reasons'])[:120]} |")
    lines += ["", "- 상태 HISTORY_RESYNC_CANDIDATE·SOURCE_DISCONTINUITY는 KIS 재조회 결과(state)로만 붙는다.",
              "- 권리락일은 원문에 칸이 있을 때만 쓴다. 기준일에서 계산하지 않는다.", ""]
    return "\n".join(lines)


def cmd_detect(args) -> int:
    from pipelines.market.adjusted_recheck import load_state

    conn = price_cli.connect_read_only()
    try:
        report = run_detect(conn, args, state=load_state(STATE_PATH))
    finally:
        conn.close()
    out = new_run_dir("detect")
    write_json(out / "detect.json", report)
    (out / "detect.md").write_text(render_detect(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    print(f"결과: {out}")
    return 0


# ---------------------------------------------------------------- recheck (Phase 2)

DB_WINDOW_SQL = """
SELECT btrim(p.symbol) AS symbol, p.trade_date, p.close AS raw_close, p.volume AS raw_volume,
       a.open AS adj_open, a.high AS adj_high, a.low AS adj_low, a.close AS adj_close, a.volume AS adj_volume,
       a.adjustment_basis, a.collected_at
FROM prices_daily p JOIN adjusted_prices_daily a USING (symbol, trade_date)
WHERE btrim(p.symbol) = %(symbol)s AND p.trade_date BETWEEN %(start)s AND %(end)s
ORDER BY p.trade_date
"""
DB_RANGE_SQL = "SELECT min(trade_date), max(trade_date), count(*) FROM adjusted_prices_daily WHERE btrim(symbol) = %(symbol)s"
LATEST_DATE_SQL = "SELECT max(trade_date) FROM adjusted_prices_daily"
CACHE_GLOBS = ("logs/diagnostics/adjusted_history_recheck/*/kis_raw_responses.json",
               "logs/diagnostics/adjusted_price_manager/*_recheck/kis_raw_responses.json",
               "logs/diagnostics/adjusted_price_manager/*_resync-plan/kis_raw_responses.json")


def db_window_loader(conn):
    def load(symbol: str, start: date, end: date) -> list[dict]:
        with conn.cursor() as cur:
            cur.execute(DB_WINDOW_SQL, {"symbol": symbol, "start": start, "end": end})
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.rollback()
        return rows
    return load


def make_fetch(budgeted, *, clock=now_kst, blackout_check=True):
    """기존 fetch_daily_range로 페이지를 넘기고, 남긴 원본 페이지로 다시 정규화(중복 날짜 확인)한다."""
    from pipelines.market.adjusted_recheck import RecheckNotAllowed, in_blackout, rows_from_pages
    from pipelines.market.kis import fetch_daily_range

    def fetch(symbol: str, start: date, end: date):
        if blackout_check and in_blackout(clock()):
            raise RecheckNotAllowed("KIS Capture·Finalize·Morning 수집 시간대라 요청하지 않습니다.")
        before = len(budgeted.log)
        fetch_daily_range(budgeted, symbol, start, end, adjusted=True)
        pages = [entry["output2"] for entry in budgeted.log[before:]]
        return rows_from_pages(symbol, pages, start, end)
    return fetch


def _cache_paths(extra: list[Path] | None) -> list[Path]:
    paths = [p for pattern in CACHE_GLOBS for p in sorted(REPO_ROOT.glob(pattern))]
    return paths + list(extra or [])


class LazyBudgetedClient:
    """실제로 KIS가 필요할 때만 기존 KisClient를 만든다 (캐시로 끝나면 클라이언트도 토큰도 쓰지 않는다)."""

    def __init__(self, max_requests: int, allowed: set[str], client_factory=None) -> None:
        from pipelines.market.adjusted_recheck import BudgetedClient

        self._factory = client_factory
        self._budgeted_cls = BudgetedClient
        self.max_requests = max_requests
        self.allowed = allowed
        self.client = None
        self.budgeted = None
        self._log: list[dict] = []

    @property
    def log(self) -> list[dict]:
        return self._log

    def daily_page(self, *args, **kwargs):
        if self.budgeted is None:
            if self._factory is None:
                from pipelines.market.kis import KisClient
                self._factory = KisClient
            self.client = self._factory()
            self.budgeted = self._budgeted_cls(self.client, max_requests=self.max_requests, allowed_symbols=self.allowed)
            self.budgeted.log = self._log  # 같은 목록에 기록
        return self.budgeted.daily_page(*args, **kwargs)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def metrics(self) -> dict:
        used = self.budgeted.used if self.budgeted else 0
        client = self.client.request_metrics() if self.client is not None else {"total": 0}
        return {"budget_used": used, "max_requests": self.max_requests, **client}


def _lazy_budgeted(max_requests: int, allowed: set[str], client_factory=None):
    lazy = LazyBudgetedClient(max_requests, allowed, client_factory)
    return lazy, lazy.close, lazy.metrics, lambda: lazy.log


def cmd_recheck(args) -> int:
    from pipelines.daily_refresh import ADVISORY_LOCK_KEY
    from pipelines.market import adjusted_recheck as rc

    detect_path = args.detect_report or latest_output("detect", "detect.json")
    if not detect_path:
        print("detect 결과가 없습니다. 먼저 detect를 실행하세요.", file=sys.stderr)
        return 2
    detect = json.loads(Path(detect_path).read_text(encoding="utf-8"))
    state = rc.load_state(STATE_PATH)
    now = now_kst()
    conn = price_cli.connect_read_only()
    try:
        with rc.market_lock(conn, ADVISORY_LOCK_KEY) as acquired:
            if not acquired:
                print("다른 시장데이터 수집이 실행 중이라 중단합니다.", file=sys.stderr)
                return 4
            latest_db = conn.execute(LATEST_DATE_SQL).fetchone()[0]
            conn.rollback()
            targets, skipped = rc.select_targets(
                detect["items"], state, now=now, max_symbols=args.max_symbols, latest_db_date=latest_db,
                symbols=set(args.symbols) if args.symbols else None)
            cache = rc.load_cached_pages(_cache_paths(args.reuse_responses))
            if args.list_only:
                print(json.dumps({"targets": [t.__dict__ for t in targets], "skipped": skipped}, ensure_ascii=False,
                                 indent=1, default=str))
                return 0
            out = new_run_dir("recheck")
            lazy, close, metrics, log = _lazy_budgeted(args.max_requests, {t.symbol for t in targets})
            fetch = make_fetch(lazy)
            results, deferred = [], []
            try:
                for i, target in enumerate(targets):
                    try:
                        result = rc.recheck_symbol(
                            target, load_db_rows=db_window_loader(conn), fetch=fetch, cache=cache,
                            cache_max_age=timedelta(days=args.cache_max_age_days), now=now)
                    except rc.RequestBudgetExceeded as exc:
                        deferred = [t.symbol for t in targets[i:]]
                        print(f"요청 상한 도달: {exc}", file=sys.stderr)
                        break
                    results.append(result)
                    rc.update_state(state, result, result_path=str(out / "recheck.json"), now=now)
            finally:
                close()
    finally:
        conn.close()
    raw = {"run_at_kst": now.isoformat(), "tr_id": "FHKST03010100", "FID_ORG_ADJ_PRC": "0",
           "request_metrics": metrics(), "requests": log()}
    write_json(out / "kis_raw_responses.json", raw)
    summary = {"targets": [t.symbol for t in targets], "deferred_by_budget": deferred, "skipped": skipped,
               "statuses": {r["symbol"]: r["status"] for r in results}, "request_metrics": raw["request_metrics"],
               "detect_report": str(detect_path)}
    write_json(out / "recheck.json", {"summary": summary, "results": results})
    (out / "recheck.md").write_text(render_recheck(summary, results), encoding="utf-8")
    rc.save_state(STATE_PATH, state)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"결과: {out}")
    return 0


def render_recheck(summary: dict, results: list[dict]) -> str:
    lines = ["# 수정주가 관리: 제한적 재조회", "",
             f"- KIS 요청 {summary['request_metrics']} · 대상 {summary['targets']} · 상한으로 미룬 종목 {summary['deferred_by_budget']}",
             f"- 건너뜀 {summary['skipped']}", "",
             "| 종목 | 상태 | 구간 | 출처 | 변경 날짜 수 | KIS 비율 | DB 비율 | KIS 단절 | 사유 |", "|---|---|---|---|---:|---|---|---|---|"]
    for r in results:
        for w in r["windows"]:
            lines.append(f"| {r['symbol']} | {w['status']} | {w['start']}~{w['end']} | {w['origin']['source']} | "
                         f"{len(w['changed_dates'])} | {w['kis_ratio_levels']} | {w['db_ratio_levels']} | "
                         f"{[d['trade_date'] for d in w['kis_discontinuities']]} | {'; '.join(w['reasons'])} |")
        lines.append(f"| **{r['symbol']}** | **{r['status']}** | | | | | | | 다음: {r['next_step']} |")
    lines += ["", "- HISTORY_RESYNC_CANDIDATE: 구간 확인만 끝난 상태. 전체 이력은 resync-plan(승인 후)으로 확인한다.",
              "- SOURCE_DISCONTINUITY: 같은 증거로는 다시 요청하지 않는다. 가격을 보정하지 않는다.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- resync (Phase 3)


def cmd_resync_plan(args) -> int:
    from pipelines.daily_refresh import ADVISORY_LOCK_KEY
    from pipelines.market import adjusted_recheck as rc
    from pipelines.market import adjusted_resync as rs

    state = rc.load_state(STATE_PATH)
    for symbol in args.symbols:
        if rc.is_held(state["symbols"].get(symbol)):
            print(f"{symbol}: 보류 중이라 계획을 만들지 않습니다 ({state['symbols'][symbol]['hold']['reason']}).",
                  file=sys.stderr)
            return 3
        status = (state["symbols"].get(symbol) or {}).get("status")
        if status != ca.HISTORY_RESYNC_CANDIDATE:
            print(f"{symbol}: 재조회 상태가 {status}라 계획을 만들지 않습니다 (HISTORY_RESYNC_CANDIDATE만).", file=sys.stderr)
            return 3
    now = now_kst()
    conn = price_cli.connect_read_only()
    plans = []
    try:
        with rc.market_lock(conn, ADVISORY_LOCK_KEY) as acquired:
            if not acquired:
                print("다른 시장데이터 수집이 실행 중이라 중단합니다.", file=sys.stderr)
                return 4
            ranges = {}
            for symbol in args.symbols:
                lo, hi, n = conn.execute(DB_RANGE_SQL, {"symbol": symbol}).fetchone()
                conn.rollback()
                ranges[symbol] = (lo, hi, n)
            estimate = sum(n // rs_page() + 2 for _, _, n in ranges.values())
            if estimate > args.max_requests:
                print(f"예상 요청 {estimate}건이 상한 {args.max_requests}건을 넘어 실행하지 않습니다.", file=sys.stderr)
                return 5
            out = new_run_dir("resync-plan")
            lazy, close, metrics, log = _lazy_budgeted(args.max_requests, set(args.symbols))
            fetch = make_fetch(lazy)
            try:
                for symbol in args.symbols:
                    lo, hi, _ = ranges[symbol]
                    db_rows = db_window_loader(conn)(symbol, lo, hi)
                    kis_rows, zero, dup = fetch(symbol, lo, hi)
                    plan = rs.build_plan(symbol, db_rows, kis_rows, zero_rows=zero, duplicates=dup,
                                         kis_fetched_at=now_kst(), recheck_status=state["symbols"][symbol]["status"])
                    write_json(out / f"plan_{symbol}.json", plan)
                    plans.append(plan)
            finally:
                close()
    finally:
        conn.close()
    write_json(out / "kis_raw_responses.json", {"run_at_kst": now.isoformat(), "request_metrics": metrics(),
                                                "requests": log()})
    lines = ["# 수정주가 재동기화 계획 (dry-run, DB 쓰기 없음)", ""]
    for p in plans:
        lines += [f"## {p['symbol']} · {p['status']}", "",
                  f"- 행 {p['row_count']} · 변경 {p['changed_rows']} {p['changed_range']} · 차단 사유 {p['blocking_failures']}",
                  f"- DB 비율 구간 {p['ratio_levels_db'][:6]}", f"- KIS 비율 구간 {p['ratio_levels_kis'][:6]}",
                  f"- plan_sha256 `{p['plan_sha256']}`", ""]
        lines += [f"  - {c['name']}: {'통과' if c['passed'] else '실패'} {c['detail'] if not c['passed'] else ''}" for c in p["checks"]]
        lines.append("")
    (out / "plan.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"결과: {out}")
    return 0


def rs_page() -> int:
    from pipelines.market.adjusted_recheck import PAGE_SIZE
    return PAGE_SIZE


def cmd_resync_apply(args) -> int:
    from pipelines.common.db import database_url
    from pipelines.daily_refresh import daily_refresh_lock
    from pipelines.market import adjusted_recheck as rc
    from pipelines.market import adjusted_resync as rs
    from sqlalchemy import create_engine

    if not args.i_understand_this_writes_db:
        print("실제 DB 갱신에는 --i-understand-this-writes-db가 필요합니다.", file=sys.stderr)
        return 3
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    state = rc.load_state(STATE_PATH)
    if rc.is_held(state["symbols"].get(args.symbol)):
        print(f"{args.symbol}: 보류 중이라 적용하지 않습니다. release-hold(승인) 뒤 계획을 다시 만드세요.", file=sys.stderr)
        return 3
    if (state["symbols"].get(args.symbol) or {}).get("status") != ca.HISTORY_RESYNC_CANDIDATE:
        print("재조회 상태가 HISTORY_RESYNC_CANDIDATE가 아니라 적용하지 않습니다.", file=sys.stderr)
        return 3
    now = now_kst()
    rs.validate_for_apply(plan, symbol=args.symbol, confirm=args.confirm, now=now,
                          max_age=timedelta(hours=args.max_plan_age_hours))
    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with daily_refresh_lock() as acquired:
            if not acquired:
                print("다른 시장데이터 수집이 실행 중이라 중단합니다.", file=sys.stderr)
                return 4
            result = rs.apply_plan(engine.begin, plan, symbol=args.symbol, confirm=args.confirm,
                                   backup_dir=args.backup_dir, now=now,
                                   max_age=timedelta(hours=args.max_plan_age_hours))
    finally:
        engine.dispose()
    entry = state["symbols"][args.symbol]
    entry.update({"status": ca.NO_ACTION, "applied_at": now.isoformat(), "applied_plan": plan["plan_sha256"],
                  "backup_path": result["backup_path"]})
    rc.save_state(STATE_PATH, state)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def cmd_hold(args) -> int:
    """보류 설정 (상태 파일만 바꾼다, DB·API 없음)."""
    from pipelines.market import adjusted_recheck as rc

    state = rc.load_state(STATE_PATH)
    entry = rc.set_hold(state, args.symbol, reason=args.reason, now=now_kst(), by=args.by)
    rc.save_state(STATE_PATH, state)
    print(json.dumps({args.symbol: entry["hold"]}, ensure_ascii=False, indent=1))
    return 0


def cmd_release_hold(args) -> int:
    """보류 해제: 종목코드를 다시 적고 승인 플래그·승인자·근거가 있어야 한다."""
    from pipelines.market import adjusted_recheck as rc

    if not args.i_approve_release or args.confirm_symbol != args.symbol:
        print("보류 해제에는 --i-approve-release와 --confirm-symbol <같은 종목코드>가 필요합니다.", file=sys.stderr)
        return 3
    state = rc.load_state(STATE_PATH)
    try:
        rc.release_hold(state, args.symbol, approved_by=args.approved_by, note=args.note, now=now_kst())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    rc.save_state(STATE_PATH, state)
    print(f"{args.symbol} 보류 해제 기록 완료. 재동기화 전에 resync-plan을 다시 실행하세요.")
    return 0


RESTORE_PREVIEW_SQL = """
SELECT trade_date, open, high, low, close, volume, adjustment_basis, source, collected_at
FROM adjusted_prices_daily WHERE btrim(symbol) = %(symbol)s ORDER BY trade_date
"""


def _restore_approved(state: dict, symbol: str, backup: dict, backup_path: Path) -> bool:
    """승인된 적용(resync-apply)이 만든 백업인지: 상태 파일의 적용 기록과 대조한다."""
    entry = state["symbols"].get(symbol) or {}
    return bool(backup.get("plan_sha256")) and (
        entry.get("applied_plan") == backup["plan_sha256"]
        or Path(entry.get("backup_path") or "").resolve() == backup_path.resolve()
    )


def cmd_resync_restore(args) -> int:
    from pipelines.market import adjusted_recheck as rc
    from pipelines.market import adjusted_resync as rs

    backup = rs.load_backup(args.backup)  # 무결성 확인 (실패 시 예외)
    state = rc.load_state(STATE_PATH)
    if not _restore_approved(state, args.symbol, backup, args.backup):
        print("상태 파일에 이 백업을 만든 승인된 적용 기록이 없어 복원하지 않습니다.", file=sys.stderr)
        return 3
    out = new_run_dir("restore")
    conn = price_cli.connect_read_only()
    try:
        with conn.cursor() as cur:
            cur.execute(RESTORE_PREVIEW_SQL, {"symbol": args.symbol})
            cols = [c.name for c in cur.description]
            current = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.rollback()
    finally:
        conn.close()
    preview = rs.plan_restore(backup, current, symbol=args.symbol)
    write_json(out / "restore_preview.json", {**preview, "backup_path": str(args.backup), "dry_run": True,
                                              "previewed_at": now_kst().isoformat()})
    print(json.dumps(preview, ensure_ascii=False, indent=1))
    if not args.i_understand_this_writes_db:
        print(f"dry-run만 했습니다. 결과: {out}")
        return 0 if preview["status"] != "blocked" else 3
    if preview["status"] != "ready" or args.confirm != preview["restore_sha256"]:
        print("복원 조건이 맞지 않거나 --confirm 값이 restore_sha256과 다릅니다.", file=sys.stderr)
        return 3
    return _execute_restore(args, backup, state, out)


def _execute_restore(args, backup: dict, state: dict, out: Path) -> int:
    from pipelines.common.db import database_url
    from pipelines.daily_refresh import daily_refresh_lock
    from pipelines.market import adjusted_recheck as rc
    from pipelines.market import adjusted_resync as rs
    from sqlalchemy import create_engine

    engine = create_engine(database_url(), pool_pre_ping=True)
    now = now_kst()
    try:
        with daily_refresh_lock() as acquired:
            if not acquired:
                print("다른 시장데이터 수집이 실행 중이라 중단합니다.", file=sys.stderr)
                return 4
            result = rs.apply_restore(engine.begin, backup, symbol=args.symbol, confirm=args.confirm,
                                      backup_dir=args.backup_dir, now=now)
    finally:
        engine.dispose()
    write_json(out / "restore_result.json", {**result, "restored_at": now.isoformat(), "backup_path": str(args.backup)})
    entry = state["symbols"].setdefault(args.symbol, {})
    entry.update({"status": ca.HISTORY_RESYNC_CANDIDATE, "restored_at": now.isoformat(),
                  "restored_from": str(args.backup), "pre_restore_backup": result["pre_restore_backup"]})
    rc.save_state(STATE_PATH, state)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


# ---------------------------------------------------------------- argparse


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect", help="공시·가격 기반 감지 (읽기 전용)")
    d.add_argument("--as-of", type=date.fromisoformat)
    d.add_argument("--price-report", type=Path, help="기존 diagnose_adjusted_history findings.json 재사용")
    d.add_argument("--price-start", type=date.fromisoformat, help="가격 탐지 시작일 (기본 전체)")
    d.add_argument("--horizon-days", type=int, default=30, help="다가오는 일정으로 볼 기간")
    d.add_argument("--window-days", type=int, default=10, help="재조회 구간: 발생일 전후 달력일")
    _add_more_commands(sub)
    return ap.parse_args(argv)


def _add_more_commands(sub) -> None:
    r = sub.add_parser("recheck", help="후보 종목만 KIS 수정 일봉 짧은 구간 재조회·비교 (DB 쓰기 없음)")
    r.add_argument("--detect-report", type=Path, help="기본: 가장 최근 detect.json")
    r.add_argument("--symbols", nargs="+", help="이 종목들로 한정")
    r.add_argument("--max-symbols", type=int, default=5)
    r.add_argument("--max-requests", type=int, default=10, help="KIS 요청 상한 (토큰 요청 제외)")
    r.add_argument("--reuse-responses", type=Path, nargs="*", help="추가로 재사용할 kis_raw_responses.json")
    r.add_argument("--cache-max-age-days", type=float, default=7)
    r.add_argument("--list-only", action="store_true", help="대상만 보여 주고 요청하지 않는다")

    p = sub.add_parser("resync-plan", help="재동기화 후보의 KIS 전체 이력 조회·검증 계획 (DB 쓰기 없음)")
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--max-requests", type=int, default=25)

    a = sub.add_parser("resync-apply", help="승인된 계획 1종목 적용 (adjusted_prices_daily만, 한 트랜잭션)")
    a.add_argument("--plan", type=Path, required=True)
    a.add_argument("--symbol", required=True)
    a.add_argument("--confirm", required=True, help="계획의 plan_sha256")
    a.add_argument("--i-understand-this-writes-db", action="store_true")
    a.add_argument("--max-plan-age-hours", type=float, default=24)
    a.add_argument("--backup-dir", type=Path, default=Path("logs/market/adjusted_price_backups"))

    s = sub.add_parser("resync-restore", help="resync-apply 백업으로 되돌리기 (기본 dry-run)")
    s.add_argument("--backup", type=Path, required=True)
    s.add_argument("--symbol", required=True)
    s.add_argument("--confirm", help="dry-run이 보여 준 restore_sha256")
    s.add_argument("--i-understand-this-writes-db", action="store_true")
    s.add_argument("--backup-dir", type=Path, default=Path("logs/market/adjusted_price_backups"),
                   help="복원 직전 현재 값을 남길 곳")


    h = sub.add_parser("hold", help="종목 보류: 자동 재조회·재동기화 계획·적용에서 제외 (상태 파일만)")
    h.add_argument("--symbol", required=True)
    h.add_argument("--reason", required=True)
    h.add_argument("--by", default="operator")

    rh = sub.add_parser("release-hold", help="보류 해제 (명시적 승인 필요)")
    rh.add_argument("--symbol", required=True)
    rh.add_argument("--confirm-symbol", required=True)
    rh.add_argument("--approved-by", required=True)
    rh.add_argument("--note", required=True, help="해제 근거 (예: 기업행동 공시 접수번호)")
    rh.add_argument("--i-approve-release", action="store_true")


COMMANDS = {"detect": cmd_detect, "recheck": cmd_recheck, "resync-plan": cmd_resync_plan,
            "resync-apply": cmd_resync_apply, "resync-restore": cmd_resync_restore,
            "hold": cmd_hold, "release-hold": cmd_release_hold}


def main(argv=None) -> int:
    from pipelines.market import adjusted_resync as rs

    args = parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except price_cli.ReadOnlyRequired as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (rs.PlanRejected, rs.StalePlan, rs.BackupInvalid, rs.RestoreRejected, rs.ApplyVerificationError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
