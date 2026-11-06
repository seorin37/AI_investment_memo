"""정기보고서 증분 업데이트: 새로 나온 사업·반기·분기보고서와 정정본만 본문·재무·비율·임베딩까지 갱신한다.

    PYTHONPATH=backend python -m pipelines.disclosures.run_periodic_updates --dry-run   # 계획만 (DB 읽기 전용, 다운로드 없음)
    PYTHONPATH=backend python -m pipelines.disclosures.run_periodic_updates             # 실행 (작업 스케줄러가 매일 새벽 1회)
    PYTHONPATH=backend python -m pipelines.disclosures.run_periodic_updates --since 2026-07-01 --until 2026-11-06

흐름 (docs/periodic-updates.md):
  1. 목록   날짜별 list.json(정기공시 A·코스피) → 사업·반기·분기보고서만. 기간 기본값: 지난 종료일 - 3일 ~ 오늘
            (첫 실행은 2026-07-01부터). 지난 날짜 목록은 data/raw/dart/periodic/lists에 캐시.
  2. 판단   DB(disclosures)·상태 파일에 없는 접수번호만 (종목, 종류, 기준일) 슬롯으로 묶는다.
            DB에 같은 슬롯이 있으면 정정본 → loader.upsert_disclosure가 교체 (참조된 원본은 교체 보류, 현행 규칙).
  3. 본문   run_all의 BatchRun 그대로 (collect → parse → chunk → load). 슬롯 선택만 계획한 슬롯으로 바꾼다.
  4. 재무   본문을 받은 (종목, 기준일)은 그 기간 재무 API를 다시 받아(refresh) financials·financials_fin 갱신.
            재무 API에 아직 자료가 없으면(013) 다음 실행에서 다시 본다 (최대 14일).
  5. 비율   재무를 갱신한 금융사만 run_financial_ratios (BIS·K-ICS·NCR).
  6. 임베딩 이번·이전 실행에서 저장하고 아직 임베딩 없는 청크 (--no-embed면 건너뜀, 다음 실행이 채운다).
  7. 검증   임베딩까지 끝난 문서에 pipeline.validate. 결과는 data/periodic_updates/runs/run_*.json.
보고서는 쌓기만 한다 (오래된 기간을 지우지 않는다). 종료 코드: 0 정상, 1 실패 있음, 3 DART 한도(020), 4 API 키 없음.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from argparse import Namespace
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from app.dart_reports import DartRateLimitError
from sqlalchemy import bindparam, text

from ..common.config import data_path, load_config, resolve_path
from ..common.file_lock import LockUnavailable, acquire_file_lock
from ..common.logging import REDACTOR, get_logger, setup_logging
from . import financials_dart
from .dart import PoliteSession
from .events_list import days_between, fetch_day
from .loader import KST
from .periodic_updates import LIST_CONFIG, Plan, UpdateState, build_plan, make_selector, parse_filings
from .pipeline import EXIT_FAILURES, EXIT_OK, get_api_key


log = get_logger("disclosures.run_periodic_updates")

EXIT_RATE_LIMITED = 3
EXIT_NO_KEY = 4
BODY_STEPS = "collect,parse,chunk,load"  # 임베딩·검증은 재무·비율 뒤에 한 번에
PERIODIC_KINDS = ("annual", "half", "quarterly")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="정기보고서 증분 업데이트 (본문·재무·비율·임베딩)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mode-config", default="configs/hybrid.yaml")
    ap.add_argument("--mapping", default="configs/financials_mapping.yaml")
    ap.add_argument("--state-dir", default="data/periodic_updates", help="상태·실행 기록 위치")
    ap.add_argument("--universe", default="data/run_all/universe.json", help="코스피 대상 목록 (run_all이 만든 것)")
    ap.add_argument("--since", help="목록 시작일 (기본: 지난 실행 종료일 - 3일, 첫 실행은 2026-07-01)")
    ap.add_argument("--until", help="목록 종료일 (기본: 오늘 KST)")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만 (시험용)")
    ap.add_argument("--max-companies", type=int, default=None, help="계획의 앞 N개사만 처리 (시험용)")
    ap.add_argument("--batch-size", type=int, default=20, help="본문 단계 한 묶음의 기업 수")
    ap.add_argument("--dry-run", action="store_true", help="목록·계획만 (DB 읽기 전용, 원문 다운로드·쓰기 없음)")
    ap.add_argument("--no-cache", action="store_true", help="지난 날짜 목록도 DART에서 다시 받는다")
    ap.add_argument("--no-embed", action="store_true", help="임베딩·검증을 건너뜀 (다음 실행이 이어서 임베딩)")
    ap.add_argument("--offline", action="store_true", help="HF_HUB_OFFLINE=1 (모델은 로컬 캐시에서만)")
    ap.add_argument("--allow-cpu", action="store_true", help="CUDA가 없으면 CPU로 임베딩")
    return ap


# ── DB 조회 ──────────────────────────────────────────
def known_rcept_nos(conn, rcept_nos: list[str]) -> set[str]:
    if not rcept_nos:
        return set()
    rows = conn.execute(
        text("SELECT rcept_no FROM disclosures WHERE rcept_no IN :rs").bindparams(bindparam("rs", expanding=True)),
        {"rs": sorted(set(rcept_nos))},
    ).scalars().all()
    return set(rows)


def existing_slots(conn, symbols: list[str]) -> dict[tuple[str, str, str], str]:
    """{(symbol, kind, period_end): 가장 최근 접수번호} — DB에 있는 정기보고서 슬롯."""
    if not symbols:
        return {}
    rows = conn.execute(
        text(
            "SELECT symbol, kind::text, period_end::text, max(rcept_no) FROM disclosures"
            " WHERE symbol IN :ss AND kind IN ('annual', 'half', 'quarterly') GROUP BY 1, 2, 3"
        ).bindparams(bindparam("ss", expanding=True)),
        {"ss": sorted(set(symbols))},
    ).all()
    return {(str(s).strip(), k, p): r for s, k, p, r in rows}


def unembedded(conn, rcept_nos: list[str]) -> dict[str, int]:
    if not rcept_nos:
        return {}
    rows = conn.execute(
        text(
            "SELECT rcept_no, count(*) FROM disclosure_chunks WHERE rcept_no IN :rs"
            " AND (dense_embedding IS NULL OR sparse_embedding IS NULL) GROUP BY rcept_no"
        ).bindparams(bindparam("rs", expanding=True)),
        {"rs": sorted(set(rcept_nos))},
    ).all()
    return {r[0]: int(r[1]) for r in rows}


def present_rcept_nos(conn, rcept_nos: list[str]) -> set[str]:
    return known_rcept_nos(conn, rcept_nos)


def max_period(conn, symbol: str) -> str | None:
    return conn.execute(
        text("SELECT max(period_end)::text FROM disclosures WHERE symbol = :s AND kind IN ('annual', 'half', 'quarterly')"),
        {"s": symbol},
    ).scalar()


# ── 1~2단계: 목록·계획 ───────────────────────────────
def list_filings(api_key: str, since: date, until: date, raw_dir: Path, universe: set[str], min_period: str, *,
                  session, use_cache: bool):
    items: list[dict] = []
    for day in days_between(since, until):
        items.extend(fetch_day(api_key, day, LIST_CONFIG, raw_dir, session=session, use_cache=use_cache))
    return parse_filings(items, universe, min_period)


# ── 3단계: 본문 ──────────────────────────────────────
def body_outcomes(plan: Plan, batch: list[str], run) -> tuple[dict, dict]:
    """(성공 {key: ref}, 실패 {key: 사유}). key = (symbol, kind, period_end)."""
    collected = {(r["symbol"], r["kind"], r["period_end"]): r for r in run.record.get("collected", [])}
    failed_by_rcept = {item["rcept_no"]: item for item in run.failed_items if item.get("rcept_no")}
    failed_by_slot = {(i["symbol"], i.get("kind", ""), i.get("period_end", "")): i for i in run.failed_items}
    failed_by_symbol = {i["symbol"]: i for i in run.failed_items if not i.get("period_end")}
    ok: dict = {}
    failed: dict = {}
    for symbol in batch:
        for kind, period_end in sorted(plan.slots.get(symbol, set())):
            key = (symbol, kind, period_end)
            ref = collected.get(key)
            if ref is not None and ref["rcept_no"] not in failed_by_rcept:
                ok[key] = ref
                continue
            item = (failed_by_rcept.get(ref["rcept_no"]) if ref else None) or failed_by_slot.get(key) or failed_by_symbol.get(symbol)
            failed[key] = f"{item['stage']}: {item['reason']}" if item else "회사 목록에서 이 슬롯 후보를 찾지 못함"
    return ok, failed


def run_bodies(args, config: dict, plan: Plan, names: dict[str, str], state: UpdateState, state_dir: Path, summary: dict):
    """본문 단계. 반환: (성공 키 → ref, 한도 초과 여부)."""
    from .run_all import BatchRun, Shared

    shared = Shared(config, args.offline, args.allow_cpu)
    selector = make_selector(plan)
    manifest = state_dir / "manifest.jsonl"
    symbols = plan.symbols
    loaded: dict = {}
    for start in range(0, len(symbols), args.batch_size):
        batch = symbols[start:start + args.batch_size]
        log.info("본문 묶음 %d/%d: %s", start // args.batch_size + 1, -(-len(symbols) // args.batch_size),
                 ", ".join(f"{s} {names.get(s, '')}" for s in batch))
        batch_args = Namespace(steps=BODY_STEPS, symbols=",".join(batch), limit=None, from_zip=[], dry_run=False,
                               offline=args.offline, allow_cpu=args.allow_cpu)
        run = BatchRun(batch_args, config, shared, {s: names[s] for s in batch}, selector, manifest)
        run.execute()
        if run.rate_limited:
            log.error("DART 요청 한도(020) → 본문 단계 중단. 다음 실행에서 이어 갑니다.")
            return loaded, True, shared
        if not run.record.get("collected") and run.failures and not run.failed_items:
            raise RuntimeError("본문 묶음 전체 실패: " + REDACTOR.redact("; ".join(run.failures)))
        ok, failed = body_outcomes(plan, batch, run)
        now = datetime.now(KST).isoformat(timespec="seconds")
        for key, ref in ok.items():
            state.mark(plan.filings[key], "loaded", now, note=f"적재 {ref['rcept_no']}")
            state.clear_failure(key)
            state.data.setdefault("embed_queue", [])
            if ref["rcept_no"] not in state.data["embed_queue"]:
                state.data["embed_queue"].append(ref["rcept_no"])
            state.add_financials(key[0], key[2], now[:10])
            loaded[key] = ref
        for key, reason in failed.items():
            gave_up = state.record_failure(key, plan.filings[key], now, reason)
            summary["body_failures"].append({"symbol": key[0], "kind": key[1], "period_end": key[2],
                                             "reason": REDACTOR.redact(reason), "gave_up": gave_up})
        state.save()
    return loaded, False, shared


# ── 4~5단계: 재무·비율 ───────────────────────────────
def run_financials(args, config: dict, engine, api_key: str, session, state: UpdateState, corp_codes: dict[str, str],
                   state_dir: Path, summary: dict) -> list[str]:
    """대기 중인 (종목, 기준일) 재무를 받는다. 반환: 재무를 갱신한 종목."""
    from .run_financials_all import Context, fy_end_month, process_company

    ctx = Context(Namespace(mapping=args.mapping, no_prior=False), config, state_dir, engine, api_key, session)
    today = datetime.now(KST).date()
    by_symbol: dict[str, list[str]] = {}
    for name in sorted(state.pending_financials):
        symbol, period_end = name.split("|")
        if args.symbols and symbol not in args.symbol_set:
            continue
        by_symbol.setdefault(symbol, []).append(period_end)
    updated: list[str] = []
    for symbol, periods in sorted(by_symbol.items()):
        corp_code = corp_codes.get(symbol)
        if not corp_code:
            summary["financials"]["failed"].append({"symbol": symbol, "reason": "corp_code 없음"})
            continue
        try:
            info, _ = financials_dart.fetch_company(corp_code, api_key, ctx.company_dir, session=session)
            fy = fy_end_month(info)
            ready = []
            for period_end in periods:
                entry = state.pending_financials[f"{symbol}|{period_end}"]
                target = financials_dart.Target(symbol, corp_code, period_end, fy)
                report = financials_dart.collect([target], api_key, ctx.statements_dir, ctx.shares_dir,
                                                 session=session, refresh=bool(entry.get("refresh")))
                entry["attempts"] = int(entry.get("attempts", 0)) + 1
                if financials_dart.cached_statement(ctx.statements_dir, target) is not None:
                    ready.append(period_end)
                else:
                    summary["financials"]["waiting"].append({"symbol": symbol, "period_end": period_end,
                                                             "reason": "; ".join(report.failures) or "재무제표 없음"})
            if not ready:
                continue
            with engine.connect() as conn:
                end = max([max_period(conn, symbol) or ""] + ready)
            ctx.end, ctx.slots = end, 10_000  # 대상 기간 시작(2024-01-01)부터 이 기업의 최신 보고서 기간까지 전부
            row, _ = process_company(ctx, symbol, corp_code)
        except (DartRateLimitError, financials_dart.DartAuthError):
            state.save()
            raise
        except Exception as exc:  # 한 기업 실패는 기록하고 다음 기업으로 (대기 목록에 남아 다음 실행이 다시 본다)
            log.exception("%s 재무 처리 실패", symbol)
            summary["financials"]["failed"].append({"symbol": symbol, "reason": REDACTOR.redact(f"{type(exc).__name__}: {exc}")})
            continue
        if row.get("status") == "error":
            summary["financials"]["failed"].append({"symbol": symbol, "reason": REDACTOR.redact(json.dumps(row.get("failed_items", []), ensure_ascii=False))})
            continue
        for period_end in ready:
            state.pending_financials.pop(f"{symbol}|{period_end}", None)
        updated.append(symbol)
        summary["financials"]["updated"].append({"symbol": symbol, "periods": ready, "fin_type": row.get("fin_type"),
                                                 "status": row.get("status")})
        state.save()
    for name in state.expired_financials(today):
        summary["financials"]["gave_up"].append(name)
        state.pending_financials.pop(name, None)
    state.save()
    return updated


def run_ratios(engine, symbols: list[str], state_dir: Path, summary: dict) -> None:
    if not symbols:
        return
    from .run_financial_ratios import run as ratios_run

    with engine.connect() as conn:
        fin = conn.execute(
            text("SELECT DISTINCT symbol FROM financials_fin WHERE symbol IN :ss").bindparams(bindparam("ss", expanding=True)),
            {"ss": symbols},
        ).scalars().all()
    fin = sorted(str(s).strip() for s in fin)
    if not fin:
        return
    result = ratios_run(engine, Namespace(symbols=",".join(fin), dry_run=False, out=str(state_dir / "ratios")))
    summary["ratios"] = {"symbols": fin, "counts": result["counts"], "failures": result["failures"]}


# ── 6~7단계: 임베딩·검증 ─────────────────────────────
def run_embed_validate(args, config: dict, engine, shared, state: UpdateState, state_dir: Path, summary: dict) -> None:
    from .run_all import BatchRun, Shared
    from .validate import validate

    queue = list(state.data.get("embed_queue", []))
    with engine.connect() as conn:
        present = present_rcept_nos(conn, queue)  # 정정본으로 교체되어 사라진 문서는 뺀다
        queue = [r for r in queue if r in present]
        pending = unembedded(conn, queue)
    summary["embed"] = {"queue_docs": len(queue), "pending_docs": len(pending), "pending_chunks": sum(pending.values())}
    if args.no_embed:
        state.data["embed_queue"] = queue
        state.save()
        return
    if pending:
        shared = shared or Shared(config, args.offline, args.allow_cpu)
        embed_args = Namespace(steps="embed", symbols="", limit=None, from_zip=[], dry_run=False, offline=args.offline, allow_cpu=args.allow_cpu)
        runner = BatchRun(embed_args, config, shared, {}, None, state_dir / "manifest.jsonl")
        runner.engine = engine
        summary["embed"].update(runner.embed(sorted(pending)))
    with engine.connect() as conn:
        left = unembedded(conn, queue)
    done = [r for r in queue if r not in left]
    if done:
        with engine.connect() as conn:
            result = validate(conn, done, manifest_path=state_dir / "manifest.jsonl", expected_per_symbol=None)
        summary["validate"] = {"docs": len(done), "ok": result["ok"],
                               "failed_checks": [c["name"] for c in result["checks"] if not c["ok"]]}
        for check in result["checks"]:
            log.info("validate %s %s", "OK " if check["ok"] else "FAIL", check["name"])
    state.data["embed_queue"] = [r for r in queue if r in left]
    summary["embed"]["left_docs"] = len(state.data["embed_queue"])
    state.save()


# ── 실행 ─────────────────────────────────────────────
def write_run(state_dir: Path, summary: dict) -> Path:
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    path = state_dir / "runs" / f"run_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json.loads(REDACTOR.redact(json.dumps(summary, ensure_ascii=False, default=str))),
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    args.symbol_set = {s.strip() for s in args.symbols.split(",") if s.strip()}
    if args.offline:
        from .embedder import set_offline

        set_offline(True)
    setup_logging()
    config = load_config(args.config, args.mode_config)
    state_dir = resolve_path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        _lock = acquire_file_lock(state_dir / ".lock", timeout=0)
    except LockUnavailable:
        print("다른 run_periodic_updates가 이미 실행 중입니다.", file=sys.stderr)
        return EXIT_FAILURES
    state = UpdateState(state_dir / "state.json")

    api_key = get_api_key()
    if not api_key:
        print("DART_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        return EXIT_NO_KEY
    REDACTOR.add(api_key)

    universe_path = resolve_path(args.universe)
    if not universe_path.exists():
        print(f"universe가 없습니다: {universe_path} (run_all을 먼저 실행)", file=sys.stderr)
        return EXIT_FAILURES
    from .universe import load_universe, stock_names

    _, companies = load_universe(universe_path)
    corp_codes = {c.symbol: c.corp_code for c in companies}
    universe = set(corp_codes)
    if args.symbol_set:
        universe &= args.symbol_set

    today = datetime.now(KST).date()
    since = date.fromisoformat(args.since) if args.since else state.default_since()
    until = date.fromisoformat(args.until) if args.until else today
    dart_cfg = config["dart"]
    session = PoliteSession(
        interval=float(dart_cfg.get("request_interval_sec", 0.2)),
        attempts=int(dart_cfg.get("max_attempts", 3)),
        base_delay=float(dart_cfg.get("backoff_base_sec", 1.0)),
    )
    started = time.monotonic()
    summary: dict = {
        "started_at": datetime.now(KST).isoformat(timespec="seconds"),
        "mode": "dry-run" if args.dry_run else "write",
        "since": since.isoformat(), "until": until.isoformat(),
        "body_failures": [],
        "financials": {"updated": [], "waiting": [], "failed": [], "gave_up": []},
    }

    if args.dry_run:
        from ..common.db import get_read_engine

        engine = get_read_engine()
    else:
        from ..common.db import get_engine

        engine = get_engine()

    try:
        from .run_all import window

        min_period = window(config)[0]  # 대상 기간 시작(2024-01-01) 앞 보고서의 정정본은 받지 않는다
        filings, skipped = list_filings(api_key, since, until, data_path(config, "raw_dir") / "periodic", universe,
                                        min_period, session=session, use_cache=not args.no_cache)
    except DartRateLimitError:
        log.error("DART 요청 한도(020) → 목록 단계 중단")
        return EXIT_RATE_LIMITED
    with engine.connect() as conn:
        in_db = known_rcept_nos(conn, [f.rcept_no for f in filings])
        known = in_db | set(state.handled)
        slots = existing_slots(conn, sorted({f.symbol for f in filings if f.rcept_no not in known}))
    plan = build_plan(filings, known, slots)
    if args.max_companies is not None:
        keep = set(plan.symbols[: args.max_companies])
        plan.slots = {s: v for s, v in plan.slots.items() if s in keep}
        plan.filings = {k: v for k, v in plan.filings.items() if k[0] in keep}
        plan.amended = {k for k in plan.amended if k[0] in keep}
    summary.update({"listed": len(filings), "skipped": skipped, "plan": plan.to_dict(),
                    "titles": dict(Counter(f.prefix + f.kind for f in filings).most_common())})
    log.info("목록 %s ~ %s: 정기보고서 %d건, 이미 처리 %d건 → 처리할 슬롯 %d개 (신규 %d, 정정 %d), %d개사",
             since, until, len(filings), plan.known, summary["plan"]["slots"], summary["plan"]["new_slots"],
             summary["plan"]["amended_slots"], len(plan.slots))

    if args.dry_run:
        summary["pending_financials"] = len(state.pending_financials)
        summary["embed_queue"] = len(state.data.get("embed_queue", []))
        path = write_run(state_dir, summary)
        print(json.dumps({k: summary[k] for k in ("since", "until", "listed")} | {"plan": {k: v for k, v in summary["plan"].items() if k != "items"}},
                         ensure_ascii=False, indent=1))
        print(f"계획: {path}")
        return EXIT_OK

    from .loader import PreflightError, preflight

    try:
        if plan.symbols:  # 새 보고서가 없으면 본문 단계를 건너뛴다 (빈 목록으로 점검하면 SQL 오류)
            with engine.connect() as conn:
                preflight(conn, plan.symbols)
    except PreflightError as exc:
        print(f"DB 시작 전 점검 실패 → 중단: {exc}", file=sys.stderr)
        return EXIT_FAILURES

    code = EXIT_OK
    shared = None
    try:
        if plan.slots:
            with engine.connect() as conn:
                names = {c.symbol: c.name for c in companies if c.symbol in plan.slots}
                names.update(stock_names(conn, plan.symbols))
            names.update({str(k): v for k, v in config["targets"]["companies"].items() if str(k) in names})
            loaded, limited, shared = run_bodies(args, config, plan, names, state, state_dir, summary)
            summary["bodies"] = {"loaded": len(loaded), "failed": len(summary["body_failures"])}
            if limited:
                code = EXIT_RATE_LIMITED
        updated = run_financials(args, config, engine, api_key, session, state, corp_codes, state_dir, summary)
        run_ratios(engine, updated, state_dir, summary)
        run_embed_validate(args, config, engine, shared, state, state_dir, summary)
        if code == EXIT_OK:
            state.data["last_until"] = until.isoformat()
            state.save()
    except DartRateLimitError:
        log.error("DART 요청 한도(020) → 중단. 다음 실행에서 이어 갑니다.")
        code = EXIT_RATE_LIMITED
    except financials_dart.DartAuthError as exc:
        log.error("DART 인증키 오류 → 중단: %s", REDACTOR.redact(str(exc)))
        code = EXIT_NO_KEY
    finally:
        state.save()
        summary["finished_at"] = datetime.now(KST).isoformat(timespec="seconds")
        summary["minutes"] = round((time.monotonic() - started) / 60, 1)
        summary["pending_financials"] = len(state.pending_financials)
        path = write_run(state_dir, summary)

    problems = (summary["body_failures"] or summary["financials"]["failed"]
                or (summary.get("validate") and not summary["validate"]["ok"])
                or (summary.get("embed", {}).get("failed")))
    print(f"\n== 정기보고서 증분 업데이트 {since} ~ {until} ==")
    print(f"목록 {len(filings)}건 → 처리 슬롯 {summary['plan']['slots']}개 (신규 {summary['plan']['new_slots']}, 정정 {summary['plan']['amended_slots']})"
          f" · 본문 적재 {summary.get('bodies', {}).get('loaded', 0)} · 본문 실패 {len(summary['body_failures'])}")
    fin = summary["financials"]
    print(f"재무 갱신 {len(fin['updated'])}개사 · 대기 {len(fin['waiting'])}건 · 실패 {len(fin['failed'])}개사 · 포기 {len(fin['gave_up'])}건")
    if "ratios" in summary:
        print(f"비율 {len(summary['ratios']['symbols'])}개사 · 실패 {len(summary['ratios']['failures'])}")
    if "embed" in summary:
        print(f"임베딩 {summary['embed']}")
    if "validate" in summary:
        print(f"검증 {summary['validate']}")
    print(f"자세한 내용: {path}")
    if code != EXIT_OK:
        return code
    return EXIT_FAILURES if problems else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
