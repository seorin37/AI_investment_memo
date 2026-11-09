"""코스피 전체 재무 수치 무인 실행 (financials / financials_fin, docs/financials-kospi-plan.md).

    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all            # 실행 (중단 후 다시 실행하면 이어서)
    PYTHONPATH=backend python -m pipelines.disclosures.run_financials_all --status   # 진행 상황만 보기

흐름 (기업 1곳씩):
  1. 대상: run_all과 같은 universe(data/run_all/universe.json). 없으면 KRX·corpCode로 만들고 stocks에 INSERT.
  2. 기업개황(company.json) → 결산월·업종코드. 대상 기간은 configs periods 범위 안에서 결산월 기준 최근 len(periods)개.
  3. 재무제표(CFS, 없으면 OFS)·주식 총수 원본 수집. 저장본이 있으면 다시 호출하지 않는다.
  4. 금융 세부 업종 판별(fin_classify) → stocks.sector·fin_type 갱신.
  5. 매핑·적재: financials(+금융사는 financials_fin). NULL은 null_reasons에 사유 코드를 남긴다.
     대상 기간 1년 전 기간이 대상에 없으면(2023년) 같은 보고서의 전기 값으로 채운다. 이미 있는 행은 덮지 않는다.
  6. DART 요청 한도(020)면 다음 날 00:05 KST까지 기다렸다가 같은 기업부터 이어 간다 (--no-wait면 종료 코드 3).
비율(BIS·K-ICS·NCR)은 공시 본문이 필요해 이 명령에서 다루지 않는다 (run_all 완료 후 별도 단계).

산출물 (data/run_financials/):
  state.json            기업별 상태 (done · partial · error). --retry-failed로 partial·error 다시 처리
  failed.csv            실패 (수집·매핑·적재 오류)
  review.csv            검토할 NULL (needs_review·no_standard_id). not_reported·not_applicable은 summary 집계만
  classification.csv    금융 판별 결과와 근거 (검토 사유가 있는 기업 표시)
  no_data.csv           재무 API에 자료가 없는 기간 (CFS·OFS 모두 013: 신규 상장·XBRL 미제출 등)
  provenance/{종목}.jsonl  컬럼별 출처 (account_id, 응답 필드, 원본 파일)
  summary.json          상태별 기업 수, 업종별 수, 컬럼별 NULL 사유 집계
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from argparse import Namespace
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.dart_reports import DartError, DartRateLimitError

from ..common.config import data_path, load_config, resolve_path
from ..common.file_lock import LockUnavailable, acquire_file_lock
from ..common.logging import REDACTOR, get_logger, setup_logging
from . import financials, financials_dart
from .fin_classify import classify
from .loader import KST
from .run_all import State, seconds_until_reset, window


log = get_logger("disclosures.run_financials_all")

EXIT_OK, EXIT_FAILURES, EXIT_NO_KEY, EXIT_RATE_LIMITED = 0, 1, 2, 3
MAX_CONSECUTIVE_ERRORS = 10
REVIEW_CODES = {"needs_review", "no_standard_id"}
STAGE_LABELS = {"company": "기업개황", "collect": "수집", "map": "매핑", "load": "DB 적재", "validate": "검증", "run": "실행 오류"}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="코스피 전체 DART 재무 수치 무인 실행 (financials / financials_fin)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mapping", default="configs/financials_mapping.yaml")
    ap.add_argument("--state-dir", default="data/run_financials", help="상태·CSV·출처 파일 위치")
    ap.add_argument("--universe-dir", default="data/run_all", help="run_all과 공유하는 universe.json 위치")
    ap.add_argument("--refresh-universe", action="store_true", help="KRX·corpCode로 대상 목록을 새로 만든다")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만 처리 (시험용, universe 안에서만)")
    ap.add_argument("--max-companies", type=int, default=None, help="시가총액 상위 N개까지만 처리 (시험용)")
    ap.add_argument("--retry-failed", action="store_true", help="partial·error 상태 기업도 다시 처리")
    ap.add_argument("--no-prior", action="store_true", help="전기(1년 전) 비교값을 채우지 않는다")
    ap.add_argument("--no-wait", action="store_true", help="DART 한도(020)면 기다리지 않고 종료 (종료 코드 3)")
    ap.add_argument("--status", action="store_true", help="진행 상황만 출력하고 종료")
    return ap


# ── 대상 기간 ────────────────────────────────────────
def fiscal_slots(fy_end_month: int, start: str, end: str, count: int) -> list[str]:
    """[start, end] 안에서 결산월 기준 분기 말 최근 count개 (오래된 순)."""
    year, month = int(end[:4]), int(end[5:7])
    slots: list[str] = []
    while len(slots) < count:
        period_end = financials.month_end(year, month)
        if period_end < start:
            break
        if period_end <= end and (month - fy_end_month) % 3 == 0:
            slots.append(period_end)
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return sorted(slots)


def fy_end_month(company_info: dict) -> int:
    value = str(company_info.get("acc_mt") or "").strip()
    return int(value) if value.isdigit() and 1 <= int(value) <= 12 else 12


# ── 기업 1곳 처리 ────────────────────────────────────
class Context:
    def __init__(self, args, config: dict, state_dir: Path, engine, api_key: str, session):
        self.args = args
        self.config = config
        self.state_dir = state_dir
        self.engine = engine
        self.api_key = api_key
        self.session = session
        self.mapping = financials.load_mapping(resolve_path(args.mapping))
        self.statements_dir = data_path(config, "financials_raw_dir")
        self.shares_dir = data_path(config, "shares_raw_dir")
        self.company_dir = data_path(config, "raw_dir") / "company"
        self.start, self.end, self.slots = window(config)


def _item(stage: str, reason: str, period_end: str = "") -> dict:
    return {"stage": stage, "period_end": period_end, "reason": REDACTOR.redact(str(reason))}


def null_counts(mapped: list[financials.MappedPeriod]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = {}
    for m in mapped:
        for table, reasons in (("financials", m.null_reasons), ("financials_fin", m.fin_null_reasons)):
            for column, code in reasons.items():
                counts.setdefault(f"{table}.{column}", Counter())[code] += 1
    return {k: dict(v) for k, v in sorted(counts.items())}


def unexplained_nulls(m: financials.MappedPeriod) -> list[str]:
    """NULL인데 사유 코드가 없는 컬럼 (있으면 매핑 버그)."""
    missing = [f"financials.{c}" for c, v in m.values.items() if v is None and c not in m.null_reasons]
    if m.fin_values is not None:
        missing += [f"financials_fin.{c}" for c, v in m.fin_values.items() if v is None and c not in m.fin_null_reasons]
    return missing


def process_company(ctx: Context, symbol: str, corp_code: str) -> tuple[dict, list[dict]]:
    """(state 행, 검토 항목). DART 020·인증 오류는 그대로 올린다."""
    items: list[dict] = []
    row: dict = {"calls": 0}
    try:
        info, called = financials_dart.fetch_company(corp_code, ctx.api_key, ctx.company_dir, session=ctx.session)
        row["calls"] += called
    except (DartRateLimitError, financials_dart.DartAuthError):
        raise
    except DartError as exc:
        return {**row, "status": "error", "failed_items": [_item("company", exc)]}, []
    fy = fy_end_month(info)
    targets = [financials_dart.Target(symbol, corp_code, p, fy) for p in fiscal_slots(fy, ctx.start, ctx.end, ctx.slots)]
    row.update({"fy_end_month": fy, "induty_code": info.get("induty_code"), "targets": [t.period_end for t in targets]})

    report = financials_dart.collect(targets, ctx.api_key, ctx.statements_dir, ctx.shares_dir, session=ctx.session)
    row["calls"] += report.calls
    chosen: dict[str, tuple[str, Path]] = {}
    no_data: list[str] = []
    for target in targets:
        found = financials_dart.cached_statement(ctx.statements_dir, target)
        if found is not None:
            chosen[target.period_end] = found
        elif any(f.startswith(f"{symbol} {target.period_end}: 재무제표 CFS·OFS 모두") for f in report.failures):
            no_data.append(target.period_end)
    for failure in report.failures:  # "{종목} {기간}: 사유"
        if "CFS·OFS 모두 데이터 없음" not in failure:
            head, _, reason = failure.partition(": ")
            items.append(_item("collect", reason or failure, head.split(" ")[-1] if " " in head else ""))
    row["no_data"] = no_data

    statements = {p: json.loads(path.read_text(encoding="utf-8")) for p, (_, path) in chosen.items()}
    if not statements:
        row.update({"status": "done" if not items else "error", "fin_type": None, "basis": "재무제표 없음", "failed_items": items})
        return row, []
    annual = [p for p in sorted(statements) if financials.period_type(p, fy) == "annual"]
    basis_period = (annual or sorted(statements))[-1]
    cls = classify(info.get("induty_code", ""), statements[basis_period].get("list", []), symbol)
    row.update({"fin_type": cls.fin_type, "basis": f"{cls.basis} ({basis_period} 기준)", "classification_review": cls.review})

    mapped: list[financials.MappedPeriod] = []
    slot_set = set(statements) | set(row["targets"])
    for target in targets:
        if target.period_end not in chosen:
            continue
        fs_div, path = chosen[target.period_end]
        shares_file = financials_dart.shares_path(ctx.shares_dir, target)
        shares_data = json.loads(shares_file.read_text(encoding="utf-8")) if shares_file.exists() else None
        variants = [False]
        if not ctx.args.no_prior and financials.prior_period_end(target.period_end) not in slot_set:
            variants.append(True)
        for prior in variants:
            try:
                mapped.append(financials.map_period(
                    symbol, target.period_end, fs_div, statements[target.period_end], path.name, shares_data,
                    shares_file.name if shares_data is not None else None, ctx.mapping,
                    fin_type=cls.fin_type, fy_end_month=fy, prior=prior,
                ))
            except Exception as exc:  # 한 기간 매핑 오류는 그 기간만 실패로 남긴다
                items.append(_item("map", f"{type(exc).__name__}: {exc}", target.period_end))
    for m in mapped:
        missing = unexplained_nulls(m)
        if missing:
            items.append(_item("validate", f"사유 없는 NULL {missing}", m.period_end))

    from .financials_loader import update_stock_sector, upsert_financials, upsert_financials_fin

    written = {"direct": 0, "prior": 0}
    try:
        with ctx.engine.begin() as conn:
            update_stock_sector(conn, symbol, cls.fin_type)
            for m in mapped:
                wrote = upsert_financials(conn, m, keep_direct=m.prior)
                if m.fin_values is not None:
                    upsert_financials_fin(conn, m, keep_direct=m.prior)
                written["prior" if m.prior else "direct"] += wrote
    except Exception as exc:
        items.append(_item("load", f"{type(exc).__name__}: {exc}"))
        written = {"direct": 0, "prior": 0}
    else:
        write_provenance(ctx.state_dir / "provenance" / f"{symbol}.jsonl", mapped)

    review = [item for m in mapped for item in m.review_items if item["null_code"] in REVIEW_CODES]
    row.update({
        "status": "done" if not items else ("partial" if written["direct"] else "error"),
        "periods": written["direct"],
        "prior_periods": written["prior"],
        "null_counts": null_counts(mapped),
        "review_count": len(review),
        "failed_items": items,
    })
    return row, review


def write_provenance(path: Path, mapped: list[financials.MappedPeriod]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for m in mapped:
            for row in m.provenance:
                record = {**row, "rcept_no": m.rcept_no, "fs_div": m.fs_div, "prior": m.prior}
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
    os.replace(temp, path)


# ── 산출 파일 ────────────────────────────────────────
def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:  # 엑셀에서 한글이 깨지지 않게 BOM
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(temp, path)


def save_review(state_dir: Path, symbol: str, review: list[dict]) -> None:
    path = state_dir / "review" / f"{symbol}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_outputs(state: State, names: dict[str, str], state_dir: Path) -> None:
    failed, classes, no_data, review = [], [], [], []
    for symbol, row in sorted(state.companies.items()):
        name = names.get(symbol, "")
        for item in row.get("failed_items", []):
            failed.append([symbol, name, STAGE_LABELS.get(item["stage"], item["stage"]), item["period_end"], item["reason"], row.get("updated_at", "")])
        if "fin_type" in row:
            classes.append([symbol, name, row.get("induty_code") or "", row.get("fy_end_month", ""), row["fin_type"] or "general",
                            row.get("basis", ""), row.get("classification_review") or ""])
        no_data.extend([symbol, name, p] for p in row.get("no_data", []))
        path = state_dir / "review" / f"{symbol}.json"
        if path.exists():
            for item in json.loads(path.read_text(encoding="utf-8")):
                unmapped = "; ".join(f"{u['account_nm']}={u['value']}" for u in item.get("unmapped", []))
                review.append([symbol, name, item["period_end"], item["table"], item["column"], item["null_code"], item["reason"], unmapped, item["file"]])
    _write_csv(state_dir / "failed.csv", ["종목코드", "기업명", "실패 단계", "대상 기간", "사유", "기록 시각"], failed)
    _write_csv(state_dir / "classification.csv", ["종목코드", "기업명", "업종코드", "결산월", "판별", "근거", "검토 사유"], classes)
    _write_csv(state_dir / "no_data.csv", ["종목코드", "기업명", "대상 기간"], no_data)
    _write_csv(state_dir / "review.csv", ["종목코드", "기업명", "기간", "표", "컬럼", "사유 코드", "사유", "표준 ID 없는 계정(이름=값)", "원본 파일"], review)


def write_summary(state: State, symbols: list[str], state_dir: Path) -> dict:
    rows = state.companies
    nulls: dict[str, Counter] = {}
    for row in rows.values():
        for column, codes in row.get("null_counts", {}).items():
            nulls.setdefault(column, Counter()).update(codes)
    summary = {
        "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
        "companies": len(symbols),
        "status": state.counts(),
        "fin_types": dict(Counter(row.get("fin_type") or "general" for row in rows.values() if "fin_type" in row)),
        "periods": sum(row.get("periods", 0) for row in rows.values()),
        "prior_periods": sum(row.get("prior_periods", 0) for row in rows.values()),
        "calls": sum(row.get("calls", 0) for row in rows.values()),
        "review_rows": sum(row.get("review_count", 0) for row in rows.values()),
        "classification_review": sorted(s for s, row in rows.items() if row.get("classification_review")),
        "null_reasons": {k: dict(v) for k, v in sorted(nulls.items())},
        "not_started": [s for s in symbols if s not in rows],
    }
    (state_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summary


def print_status(state: State) -> None:
    counts = state.counts()
    rows = state.companies.values()
    print(f"처리 {len(state.companies)}개사 | " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
          + f" | 기간 {sum(r.get('periods', 0) for r in rows):,}행 + 전기 {sum(r.get('prior_periods', 0) for r in rows):,}행"
          + f", DART 호출 {sum(r.get('calls', 0) for r in rows):,}회, 검토 {sum(r.get('review_count', 0) for r in rows):,}건")


# ── 실행 ─────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging()
    config = load_config(args.config)
    state_dir = resolve_path(args.state_dir)
    state = State(state_dir / "state.json")
    if args.status:
        print_status(state)
        return EXIT_OK

    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        _process_lock = acquire_file_lock(state_dir / ".lock", timeout=0)
    except LockUnavailable:
        print("다른 run_financials_all이 이미 실행 중입니다.", file=sys.stderr)
        return EXIT_FAILURES

    from .pipeline import get_api_key

    api_key = get_api_key()
    if not api_key:
        print("DART_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        return EXIT_NO_KEY
    REDACTOR.add(api_key)

    from ..common.db import get_engine
    from .dart import PoliteSession
    from .financials_loader import preflight
    from .run_all import prepare_universe

    engine = get_engine()
    universe_args = Namespace(refresh_universe=args.refresh_universe)
    companies = prepare_universe(universe_args, config, resolve_path(args.universe_dir), engine)
    if args.symbols:
        wanted = {s.strip() for s in args.symbols.split(",") if s.strip()}
        companies = [c for c in companies if c.symbol in wanted]
    if args.max_companies is not None:
        companies = companies[: args.max_companies]
    symbols = [c.symbol for c in companies]
    names = {c.symbol: c.name for c in companies}
    with engine.connect() as conn:
        preflight(conn, symbols)

    dart_cfg = config.get("dart", {})
    session = PoliteSession(
        interval=float(dart_cfg.get("request_interval_sec", 0.2)),
        attempts=int(dart_cfg.get("max_attempts", 3)),
        base_delay=float(dart_cfg.get("backoff_base_sec", 1.0)),
    )
    ctx = Context(args, config, state_dir, engine, api_key, session)
    pending = [c for c in companies if c.symbol in set(state.pending(symbols, args.retry_failed))]
    log.info("대상 %d개사, 남은 %d개사, 기간 %s ~ %s (기업당 %d개, 전기 %s)", len(symbols), len(pending), ctx.start, ctx.end, ctx.slots,
             "제외" if args.no_prior else "포함")

    started = time.monotonic()
    consecutive_errors = 0
    index = 0
    while index < len(pending):
        company = pending[index]
        try:
            row, review = process_company(ctx, company.symbol, company.corp_code)
        except DartRateLimitError:
            if args.no_wait:
                log.error("DART 요청 한도(020) → 종료. 내일 같은 명령으로 다시 실행하면 이어서 진행합니다.")
                return EXIT_RATE_LIMITED
            wait = seconds_until_reset()
            log.warning("DART 요청 한도(020) → %.1f시간 대기 후 %s부터 다시 시작", wait / 3600, company.symbol)
            time.sleep(wait)
            continue
        except financials_dart.DartAuthError as exc:
            log.error("DART 인증키 오류 → 중단: %s", REDACTOR.redact(str(exc)))
            return EXIT_NO_KEY
        except Exception as exc:
            log.exception("%s 처리 실패", company.symbol)
            row, review = {"status": "error", "failed_items": [_item("run", f"{type(exc).__name__}: {exc}")]}, []
        row["updated_at"] = datetime.now(KST).isoformat(timespec="seconds")
        state.companies[company.symbol] = row
        state.save()
        save_review(state_dir, company.symbol, review)
        index += 1

        consecutive_errors = consecutive_errors + 1 if row["status"] == "error" else 0
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            log.error("%d개사 연속 error → 중단. 마지막 오류: %s", consecutive_errors, row["failed_items"][-1]["reason"])
            write_outputs(state, names, state_dir)
            write_summary(state, symbols, state_dir)
            return EXIT_FAILURES
        log.info("%s %s: %s %s, 기간 %d + 전기 %d, 검토 %d, 호출 %d (%d/%d, %.0f분 경과)",
                 company.symbol, company.name, row["status"], row.get("fin_type") or "general", row.get("periods", 0),
                 row.get("prior_periods", 0), row.get("review_count", 0), row.get("calls", 0), index, len(pending),
                 (time.monotonic() - started) / 60)
        if index % 20 == 0:
            write_outputs(state, names, state_dir)

    write_outputs(state, names, state_dir)
    summary = write_summary(state, symbols, state_dir)
    log.info("완료: %d개사 %s, 업종 %s, 기간 %d행 + 전기 %d행, 검토 %d건 → %s",
             summary["companies"], summary["status"], summary["fin_types"], summary["periods"], summary["prior_periods"],
             summary["review_rows"], state_dir / "summary.json")
    return EXIT_FAILURES if state.counts().keys() & {"partial", "error"} else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
