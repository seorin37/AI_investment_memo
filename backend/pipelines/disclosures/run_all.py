"""코스피 전체 정기보고서 무인 통합 파이프라인 (hybrid: dense + sparse).

    PYTHONPATH=backend python -m pipelines.disclosures.run_all            # 실행 (중단 후 다시 실행하면 이어서)
    PYTHONPATH=backend python -m pipelines.disclosures.run_all --status   # 진행 상황만 보기

흐름:
  1. universe  KRX 코스피 목록 × DART corpCode → data/run_all/universe.json, stocks INSERT (처음 한 번)
  2. 기업 묶음(--batch-size)마다 pipeline.Run 그대로: collect → parse → chunk → load → embed → validate
     - 대상 슬롯: configs의 periods 범위(첫 해 1월 1일 ~ 마지막 기간) 안의 정기보고서 최근 len(periods)건.
       결산월이 12월이 아니어도 같은 규칙으로 고르고, 헤더 라벨(1분기·반기 …)은 결산월 기준으로 붙인다.
     - 묶음이 끝날 때마다 data/run_all/state.json에 기업별 상태를 저장한다. 다시 실행하면 done 기업은 건너뛴다.
  3. DART 요청 한도(020)에 걸리면 다음 날 00:05 KST까지 기다렸다가 같은 묶음부터 이어 간다 (--no-wait면 종료).
  4. 원문을 못 찾거나 파싱·적재·임베딩에 실패한 보고서는 건너뛰고 계속한다. 묶음마다 아래 파일을 다시 쓴다.
     - failed_reports.csv   지금 남아 있는 실패 (보고서 1건 = 1행, 엑셀에서 바로 열림)
     - under_slots.csv      실패는 없지만 대상 기간 보고서가 기업당 건수보다 적은 기업 (신규 상장 등)
     - failures_history.jsonl  지금까지의 모든 실패 기록 (재시도로 해결된 것 포함, 추가만 함)
     상태: done(실패 없음) · partial(일부 보고서 실패) · error(적재된 보고서 0건 + 실패). --retry-failed로 둘 다 다시 처리.
  5. 끝나면 data/run_all/summary.json (상태별 기업 수, 문서·청크 수, 미달·실패 기업).

BGE-M3는 처음 한 번만 올려 모든 묶음에서 다시 쓴다. 매니페스트는 묶음별 파일(data/run_all/manifests/)에 남겨
기존 4개사 실험용 data/chunks/manifest.jsonl은 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from argparse import Namespace
from datetime import date, datetime, timedelta
from pathlib import Path

from app.dart_reports import DartRateLimitError
from sqlalchemy import text

from ..common.config import data_path, load_config, resolve_path
from ..common.file_lock import LockUnavailable, acquire_file_lock
from ..common.logging import REDACTOR, get_logger, setup_logging
from . import chunker as chunker_mod
from . import dart
from .dart import failure_item
from .loader import KST
from .pipeline import EXIT_FAILURES, EXIT_NO_KEY, EXIT_OK, STEPS, Run, get_api_key
from .universe import Company, build_universe, fetch_kospi_rows, load_universe, save_universe, stock_names, upsert_stocks


log = get_logger("disclosures.run_all")

EXIT_RATE_LIMITED = 3
MAX_CONSECUTIVE_FATAL = 3
STAGE_LABELS = {
    "corp_code": "corpCode 없음",
    "list": "목록 조회",
    "missing": "목록에 없음",
    "download": "원문 다운로드",
    "parse": "파싱",
    "chunk": "청킹",
    "load": "DB 적재",
    "embed": "임베딩",
    "batch": "묶음 전체 오류",
}
KIND_LABELS = {"annual": "사업보고서", "half": "반기보고서", "quarterly": "분기보고서"}


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="코스피 전체 DART 정기보고서 무인 통합 파이프라인 (hybrid)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mode-config", default="configs/hybrid.yaml")
    ap.add_argument("--state-dir", default="data/run_all", help="상태·universe·요약 파일 위치")
    ap.add_argument("--batch-size", type=int, default=20, help="한 묶음의 기업 수")
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드만 처리 (시험용, universe 안에서만)")
    ap.add_argument("--max-companies", type=int, default=None, help="시가총액 상위 N개까지만 처리 (시험용)")
    ap.add_argument("--refresh-universe", action="store_true", help="KRX·corpCode로 대상 목록을 새로 만든다")
    ap.add_argument("--retry-failed", action="store_true", help="partial·error 상태 기업도 다시 처리")
    ap.add_argument("--no-wait", action="store_true", help="DART 한도(020)면 기다리지 않고 종료 (종료 코드 3)")
    ap.add_argument("--status", action="store_true", help="진행 상황만 출력하고 종료")
    ap.add_argument("--offline", action="store_true", help="HF_HUB_OFFLINE=1 (모델은 로컬 캐시에서만)")
    ap.add_argument("--allow-cpu", action="store_true", help="CUDA가 없으면 CPU로 실행 (기본은 중단)")
    return ap


# ── 상태 파일 ────────────────────────────────────────
class State:
    """기업별 처리 상태. 묶음이 끝날 때마다 원자적으로 저장한다."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"companies": {}, "batches": []}

    @property
    def companies(self) -> dict[str, dict]:
        return self.data["companies"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    def pending(self, symbols: list[str], retry_failed: bool) -> list[str]:
        skip = {"done"} if retry_failed else {"done", "partial", "error"}
        return [s for s in symbols if self.companies.get(s, {}).get("status") not in skip]

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in self.companies.values():
            result[row["status"]] = result.get(row["status"], 0) + 1
        return result


# ── 공용 자원 (모델 1회 로드) ──────────────────────────
class Shared:
    def __init__(self, config: dict, offline: bool, allow_cpu: bool):
        self.config = config
        self.offline = offline
        self.allow_cpu = allow_cpu
        self._encoder = None
        self._token_counter = None

    def encoder_factory(self):
        if self._encoder is None:
            from .embedder import load_encoder

            self._encoder = load_encoder(self.config["model"], self.offline, self.allow_cpu)
        return self._encoder

    def token_counter_factory(self):
        if self._token_counter is None:
            from .embedder import load_tokenizer, resolve_model_path

            model = self.config["model"]
            path = resolve_model_path(model["name"], model["revision"], self.offline)
            self._token_counter = chunker_mod.HFTokenCounter(load_tokenizer(path))
        return self._token_counter


class BatchRun(Run):
    """pipeline.Run에 기업명·슬롯 선택·묶음별 매니페스트만 바꿔 끼운다."""

    def __init__(self, args: Namespace, config: dict, shared: Shared, names: dict[str, str], selector, manifest_path: Path):
        super().__init__("hybrid", args, config, shared.token_counter_factory, shared.encoder_factory)
        self.companies = names
        self.selector = selector
        self.manifest_path = manifest_path
        self.rate_limited = False

    def collect(self):
        try:
            return super().collect()
        except DartRateLimitError:
            self.rate_limited = True
            raise


# ── 실행 ─────────────────────────────────────────────
def window(config: dict) -> tuple[str, str, int]:
    periods = sorted(str(p) for p in config["targets"]["periods"])
    return f"{periods[0][:4]}-01-01", periods[-1], len(periods)


def seconds_until_reset(now: datetime | None = None) -> float:
    """다음 날 00:05 KST까지 남은 초 (DART 일일 한도 초기화 여유 5분)."""
    now = now or datetime.now(KST)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return max(60.0, (reset - now).total_seconds())


def company_status(engine, symbols: list[str], start: str, end: str) -> dict[str, tuple[int, int, int]]:
    """{symbol: (대상 기간 문서 수, 청크 수, 임베딩 없는 청크 수)}"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT d.symbol, count(DISTINCT d.rcept_no), count(c.id), count(c.id) FILTER (WHERE c.dense_embedding IS NULL)"
                " FROM disclosures d LEFT JOIN disclosure_chunks c ON c.rcept_no = d.rcept_no"
                " WHERE d.symbol = ANY(:ss) AND d.kind IN ('annual', 'half', 'quarterly')"
                " AND d.period_end BETWEEN :start AND :end GROUP BY d.symbol"
            ),
            {"ss": symbols, "start": date.fromisoformat(start), "end": date.fromisoformat(end)},
        ).all()
    return {str(r[0]).strip(): (int(r[1]), int(r[2]), int(r[3])) for r in rows}


def prepare_universe(args, config: dict, state_dir: Path, engine) -> list[Company]:
    path = state_dir / "universe.json"
    if path.exists() and not args.refresh_universe:
        trade_date, companies = load_universe(path)
        log.info("universe 재사용: %s 기준 %d개사 (%s)", trade_date, len(companies), path)
    else:
        api_key = get_api_key()
        if not api_key:
            raise SystemExit("DART_API_KEY가 없어 corpCode를 받을 수 없습니다.")
        REDACTOR.add(api_key)
        raw_dir = data_path(config, "raw_dir")
        corp_codes = dart.load_corp_codes(api_key, raw_dir / "corpCode.xml", float(config["dart"].get("corp_code_cache_days", 7)))
        trade_date, rows = fetch_kospi_rows(datetime.now(KST).date() - timedelta(days=1))
        companies, unmatched = build_universe(rows, corp_codes)
        save_universe(path, trade_date, companies, unmatched)
        log.info("universe 생성: KRX %s 코스피 %d종목 → 대상 %d개사 (corpCode 없음 %d: 우선주 등)", trade_date, len(rows), len(companies), len(unmatched))
    with engine.begin() as conn:
        inserted = upsert_stocks(conn, companies)
    log.info("stocks 새 종목 %d행 추가", inserted)
    return companies


def print_status(state: State, universe_path: Path) -> None:
    total = len(load_universe(universe_path)[1]) if universe_path.exists() else 0
    counts = state.counts()
    docs = sum(row.get("docs", 0) for row in state.companies.values())
    chunks = sum(row.get("chunks", 0) for row in state.companies.values())
    failed = sum(len(row.get("failed_items", [])) for row in state.companies.values())
    print(f"대상 {total}개사 | " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f" | 문서 {docs:,}건, 청크 {chunks:,}개, 실패 보고서 {failed}건")
    if state.data["batches"]:
        last = state.data["batches"][-1]
        print(f"마지막 묶음 #{last['batch']} {last['finished_at']} ({last['seconds']:.0f}초, 실패 {len(last['failures'])}건)")


def write_failure_files(state: State, names: dict[str, str], state_dir: Path, slots: int) -> int:
    """state의 남은 실패를 failed_reports.csv로, 건수 미달 기업을 under_slots.csv로 다시 쓴다. 실패 행 수 반환."""
    failed_rows = []
    under_rows = []
    for symbol, row in sorted(state.companies.items()):
        for item in row.get("failed_items", []):
            failed_rows.append([
                symbol, names.get(symbol, ""), STAGE_LABELS.get(item["stage"], item["stage"]), item["period_end"],
                KIND_LABELS.get(item["kind"], item["kind"]), item["rcept_no"], item["title"], item["reason"],
                row.get("batch", ""), row.get("updated_at", ""),
            ])
        if row["status"] == "done" and row.get("docs", 0) < slots:
            under_rows.append([symbol, names.get(symbol, ""), row.get("docs", 0), slots - row.get("docs", 0)])
    _write_csv(
        state_dir / "failed_reports.csv",
        ["종목코드", "기업명", "실패 단계", "대상 기간", "보고서 유형", "접수번호", "보고서명", "사유", "묶음", "기록 시각"],
        failed_rows,
    )
    _write_csv(state_dir / "under_slots.csv", ["종목코드", "기업명", "적재 보고서 수", "부족 수"], under_rows)
    return len(failed_rows)


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:  # 엑셀에서 한글이 깨지지 않게 BOM
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(temp, path)


def append_history(state_dir: Path, batch_no: int, items: list[dict], now: str) -> None:
    if not items:
        return
    with (state_dir / "failures_history.jsonl").open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps({**item, "batch": batch_no, "recorded_at": now}, ensure_ascii=False) + "\n")


def write_summary(state: State, companies: list[Company], state_dir: Path, slots: int) -> dict:
    names = {c.symbol: c.name for c in companies}
    rows = state.companies
    summary = {
        "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
        "companies": len(companies),
        "status": state.counts(),
        "docs": sum(r.get("docs", 0) for r in rows.values()),
        "chunks": sum(r.get("chunks", 0) for r in rows.values()),
        "under_slots": [
            {"symbol": s, "name": names.get(s, ""), "docs": r.get("docs", 0)}
            for s, r in sorted(rows.items()) if r["status"] == "done" and r.get("docs", 0) < slots
        ],
        "errors": [
            {"symbol": s, "name": names.get(s, ""), "status": r["status"], "docs": r.get("docs", 0), "failed_reports": len(r.get("failed_items", []))}
            for s, r in sorted(rows.items()) if r["status"] in {"partial", "error"}
        ],
        "not_started": [c.symbol for c in companies if c.symbol not in rows],
    }
    path = state_dir / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return summary


def run_batch(batch_no: int, symbols: list[str], args, config: dict, shared: Shared, names: dict[str, str], selector, state_dir: Path) -> BatchRun:
    batch_args = Namespace(
        steps=",".join(STEPS),
        symbols=",".join(symbols),
        limit=None,
        from_zip=[],
        dry_run=False,
        offline=args.offline,
        allow_cpu=args.allow_cpu,
    )
    manifest = state_dir / "manifests" / f"batch_{batch_no:05d}.jsonl"
    run = BatchRun(batch_args, config, shared, {s: names[s] for s in symbols}, selector, manifest)
    run.execute()
    return run


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.offline:
        from .embedder import set_offline

        set_offline(True)
    setup_logging()
    config = load_config(args.config, args.mode_config)
    if config.get("mode") != "hybrid":
        print(f"hybrid 모드 설정이 아닙니다: {args.mode_config}", file=sys.stderr)
        return EXIT_FAILURES
    state_dir = resolve_path(args.state_dir)
    state = State(state_dir / "state.json")
    if args.status:
        print_status(state, state_dir / "universe.json")
        return EXIT_OK

    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        _process_lock = acquire_file_lock(state_dir / ".lock", timeout=0)
    except LockUnavailable:
        print("다른 run_all이 이미 실행 중입니다.", file=sys.stderr)
        return EXIT_FAILURES

    api_key = get_api_key()
    if not api_key:
        print("DART_API_KEY가 설정되지 않았습니다.", file=sys.stderr)
        return EXIT_NO_KEY
    REDACTOR.add(api_key)

    from ..common.db import get_engine

    engine = get_engine()
    companies = prepare_universe(args, config, state_dir, engine)
    if args.symbols:
        wanted = {s.strip() for s in args.symbols.split(",") if s.strip()}
        companies = [c for c in companies if c.symbol in wanted]
    if args.max_companies is not None:
        companies = companies[: args.max_companies]
    symbols = [c.symbol for c in companies]

    start, end, slots = window(config)
    selector = lambda symbol, corp_code, items: dart.select_window_candidates(symbol, corp_code, items, start, end, slots)  # noqa: E731
    with engine.connect() as conn:
        names = {c.symbol: c.name for c in companies}
        names.update(stock_names(conn, symbols))
    # 기존 실험 문서와 헤더(=fingerprint)가 같도록 configs의 기업명을 가장 우선한다.
    names.update({str(k): v for k, v in config["targets"]["companies"].items() if str(k) in names})

    shared = Shared(config, args.offline, args.allow_cpu)
    pending = state.pending(symbols, args.retry_failed)
    log.info("대상 %d개사, 남은 %d개사, 기간 %s ~ %s (기업당 최대 %d건), 묶음 %d개사", len(symbols), len(pending), start, end, slots, args.batch_size)

    started = time.monotonic()
    done_this_run = 0
    consecutive_fatal = 0
    batch_no = len(state.data["batches"])
    while pending:
        batch = pending[: args.batch_size]
        batch_no += 1
        batch_started = time.monotonic()
        log.info("묶음 #%d 시작: %s", batch_no, ", ".join(f"{s} {names[s]}" for s in batch))
        run = run_batch(batch_no, batch, args, config, shared, names, selector, state_dir)

        if run.rate_limited:
            if args.no_wait:
                log.error("DART 요청 한도(020) → 종료. 내일 같은 명령으로 다시 실행하면 이어서 진행합니다.")
                return EXIT_RATE_LIMITED
            wait = seconds_until_reset()
            log.warning("DART 요청 한도(020) → %.1f시간 대기 후 묶음 #%d부터 다시 시작", wait / 3600, batch_no)
            time.sleep(wait)
            batch_no -= 1
            continue

        failures = [REDACTOR.redact(f) for f in run.failures]
        global_failures = [f for f in failures if not any(f.startswith(s) for s in batch)]
        db_status = company_status(engine, batch, start, end)
        now = datetime.now(KST).isoformat(timespec="seconds")
        batch_items: list[dict] = []
        for symbol in batch:
            docs, chunks, unembedded = db_status.get(symbol, (0, 0, 0))
            items = [i for i in run.failed_items if i["symbol"] == symbol]
            if unembedded:
                items.append(failure_item(symbol, "embed", f"임베딩 없는 청크 {unembedded}개 (다시 실행하면 이어서 임베딩)"))
            items.extend(failure_item(symbol, "batch", f) for f in global_failures)
            batch_items.extend(items)
            state.companies[symbol] = {
                "status": "done" if not items else ("partial" if docs else "error"),
                "docs": docs,
                "chunks": chunks,
                "unembedded": unembedded,
                "failed_items": items,
                "batch": batch_no,
                "updated_at": now,
            }
        seconds = time.monotonic() - batch_started
        state.data["batches"].append({
            "batch": batch_no,
            "symbols": batch,
            "status": run.record.get("status"),
            "failures": failures,
            "seconds": round(seconds, 1),
            "finished_at": now,
        })
        state.save()
        append_history(state_dir, batch_no, batch_items, now)
        failed_total = write_failure_files(state, names, state_dir, slots)

        fatal = all(state.companies[s]["status"] == "error" for s in batch) and bool(global_failures)
        consecutive_fatal = consecutive_fatal + 1 if fatal else 0
        if consecutive_fatal >= MAX_CONSECUTIVE_FATAL:
            log.error("묶음 %d개 연속 전체 실패 → 중단. 마지막 오류: %s", consecutive_fatal, global_failures[-1])
            write_summary(state, companies, state_dir, slots)
            return EXIT_FAILURES

        done_this_run += len(batch)
        pending = pending[len(batch):]
        elapsed = time.monotonic() - started
        eta_h = elapsed / done_this_run * len(pending) / 3600
        counts = state.counts()
        log.info(
            "묶음 #%d 끝 (%.0f초): done %d, partial %d, error %d (실패 보고서 %d건), 남은 %d개사, 이번 실행 경과 %.1f시간, 남은 예상 %.1f시간",
            batch_no, seconds, counts.get("done", 0), counts.get("partial", 0), counts.get("error", 0), failed_total,
            len(pending), elapsed / 3600, eta_h,
        )

    summary = write_summary(state, companies, state_dir, slots)
    log.info(
        "완료: %d개사 (%s), 문서 %d건, 청크 %d개, %d건 미만 %d개사, 실패 있는 기업 %d개사 → %s, 실패 목록 %s",
        summary["companies"], summary["status"], summary["docs"], summary["chunks"], slots,
        len(summary["under_slots"]), len(summary["errors"]), state_dir / "summary.json", state_dir / "failed_reports.csv",
    )
    return EXIT_FAILURES if summary["errors"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
