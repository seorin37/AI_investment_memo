"""코스피 수시공시(주요사항·거래소·기타 공시) 수집.

    PYTHONPATH=backend python -m pipelines.disclosures.run_events --dry-run                 # 오늘
    PYTHONPATH=backend python -m pipelines.disclosures.run_events --dry-run --date 2026-10-29
    PYTHONPATH=backend python -m pipelines.disclosures.run_events --dry-run --since 2026-10-21 --until 2026-11-03

    PYTHONPATH=backend python -m pipelines.disclosures.run_events                     # 오늘치 저장 (하루 2번 실행용)
    PYTHONPATH=backend python -m pipelines.disclosures.run_events --since 2026-10-05   # 몰아 받기

흐름: 목록(list.json) → 종류 거르기(configs/disclosure_events.yaml) → 원문 ZIP(data/raw/dart/events/docs)
     → 항목-값(events_parse) → 필드(events_fields) → disclosures·disclosure_events·disclosure_chunks
     → 임베딩(정기보고서와 같은 BGE-M3 설정, --no-embed면 건너뜀)
--dry-run은 DB를 쓰지 않고 data/events/dryrun_{since}_{until}.json에 종류별·날짜별 건수만 남긴다.
저장 모드는 DATABASE_URL의 DB에 쓴다. 테스트 DB에 쓰려면 DATABASE_URL을 테스트 DB로 바꿔 실행한다.
다시 실행하면 이미 저장한 공시는 건너뛴다(실패한 것만 다시). 결과는 data/events/run_*.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from app.dart_reports import DartDownloadError, DartError, DartRateLimitError, download_document, validate_document_zip

from ..common.config import REPO_ROOT, load_config
from ..common.logging import REDACTOR, get_logger, setup_logging
from .dart import PoliteSession
from .events_fields import EventFieldRules, extract_fields
from .events_list import EventRules, SelectReport, days_between, fetch_day, select_events
from .events_loader import done_rcept_nos, known_symbols, preflight_events, upsert_event
from .events_parse import EventParseError, parse_event_zip
from .loader import KST, PreflightError
from .pipeline import EXIT_FAILURES, EXIT_NO_KEY, EXIT_OK, get_api_key


log = get_logger("disclosures.run_events")

EXIT_RATE_LIMITED = 3
EXIT_USAGE = 2
MAX_CONSECUTIVE_STORE_ERRORS = 5


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="코스피 수시공시 수집 (1단계: 목록 받기·종류 거르기)")
    ap.add_argument("--config", default="configs/disclosure_events.yaml")
    ap.add_argument("--date", help="하루만 (YYYY-MM-DD). 기본: 오늘(KST)")
    ap.add_argument("--since", help="시작일 (YYYY-MM-DD)")
    ap.add_argument("--until", help="종료일 (YYYY-MM-DD, 기본: 오늘)")
    ap.add_argument("--universe", default="data/run_all/universe.json", help="코스피 종목 목록 (없으면 거르지 않음)")
    ap.add_argument("--no-cache", action="store_true", help="지난 날짜 목록도 DART에서 다시 받는다")
    ap.add_argument("--dry-run", action="store_true", help="DB를 쓰지 않고 목록·종류 집계만")
    ap.add_argument("--common-config", default="configs/common.yaml", help="임베딩 모델 설정")
    ap.add_argument("--reparse", action="store_true", help="이미 저장한 공시도 원문을 다시 읽어 저장")
    ap.add_argument("--no-embed", action="store_true", help="청크만 저장하고 임베딩은 건너뜀 (나중에 다시 실행하면 채운다)")
    ap.add_argument("--offline", action="store_true", help="HF_HUB_OFFLINE=1 (모델은 로컬 캐시에서만)")
    ap.add_argument("--allow-cpu", action="store_true", help="GPU가 없으면 CPU로 임베딩")
    return ap


def _parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_range(args, today: date) -> tuple[date, date]:
    if args.date and (args.since or args.until):
        raise ValueError("--date와 --since/--until은 같이 쓸 수 없습니다.")
    if args.date:
        day = _parse_day(args.date)
        return day, day
    until = _parse_day(args.until) if args.until else today
    since = _parse_day(args.since) if args.since else until
    return since, until


def load_universe_symbols(path: Path) -> set[str] | None:
    if not path.exists():
        log.warning("universe 파일이 없어 종목 필터를 쓰지 않습니다: %s", path)
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {company["symbol"] for company in data["companies"]}


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def print_summary(since: date, until: date, refs, report: SelectReport, out_path: Path) -> None:
    days = (until - since).days + 1
    data = report.to_dict()
    print(f"\n== 수시공시 dry-run {since} ~ {until} ({days}일) ==")
    print(f"목록 {data['total_listed']}건 → 수집 대상 {data['selected']}건 (정정 {data['corrections_selected']}건, "
          f"자회사 {sum(r.is_subsidiary for r in refs)}건)")
    print(f"제외 {sum(report.excluded_titles.values())}건 · 미분류 {sum(report.unclassified_titles.values())}건 · "
          f"universe 밖 {sum(report.not_in_universe.values())}건 · 종목코드 없음 {report.no_stock_code}건")
    print("\n[종류별]")
    for event_type, count in report.by_event_type.most_common():
        print(f"  {event_type:22s} {count:5d}  (하루 평균 {count / days:.1f})")
    if report.unclassified_titles:
        print("\n[미분류 보고서명 상위 20 — 받을지 정해서 설정에 넣어 주세요]")
        for title, count in report.unclassified_titles.most_common(20):
            print(f"  {count:4d}  {title}")
    print(f"\n자세한 내용: {out_path}")


def embedding_identity(model_cfg: dict) -> tuple[str, str, str]:
    """(model_name, revision, config_hash) — pipeline.Run.embed와 같은 규칙이라 정기보고서 청크와 섞여도 같은 모델로 본다."""
    identity = {key: model_cfg.get(key) for key in ("name", "revision", "max_length")}
    config_hash = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return str(model_cfg["name"]), str(model_cfg["revision"]), config_hash


def _download(ref, api_key: str, docs_dir: Path, session) -> Path:
    path = docs_dir / f"{ref.symbol}_{ref.rcept_no}.zip"
    if path.exists():
        try:
            validate_document_zip(path.read_bytes())
            return path
        except DartDownloadError:
            log.warning("기존 ZIP 무효, 다시 받음: %s", path.name)
    return download_document(ref.rcept_no, api_key, path, session=session)


@dataclass
class CollectSummary:
    loaded: list[str] = field(default_factory=list)  # 이번에 저장한 접수번호
    status: Counter = field(default_factory=Counter)  # parse_status별 건수
    skipped_done: int = 0
    skipped_unknown_symbol: Counter = field(default_factory=Counter)
    corrects_linked: int = 0
    failures: list[dict] = field(default_factory=list)
    rate_limited: bool = False
    stopped_on_errors: bool = False  # 저장 실패가 연이어 나서 멈춤

    def to_dict(self) -> dict:
        return {
            "loaded": len(self.loaded),
            "parse_status": dict(self.status),
            "skipped_done": self.skipped_done,
            "skipped_unknown_symbol": dict(self.skipped_unknown_symbol),
            "corrects_linked": self.corrects_linked,
            "failures": self.failures,
            "rate_limited": self.rate_limited,
            "stopped_on_errors": self.stopped_on_errors,
        }


def collect_events(
    engine,
    refs: list,
    api_key: str,
    docs_dir: Path,
    field_rules: EventFieldRules,
    *,
    session=None,
    reparse: bool = False,
    download=_download,
) -> CollectSummary:
    """원문 받기 → 항목-값 → 필드 → 저장. 공시 1건 = 트랜잭션 1개.

    - stocks에 없는 종목은 건너뛴다 (disclosures.symbol FK).
    - 같은 파서 버전으로 이미 저장한(실패 제외) 공시는 건너뛴다 (--reparse면 다시).
    - 원문을 못 받거나 못 읽으면 parse_status=failed로 남기고 계속한다. 다음 실행에서 다시 시도한다.
    - DART 한도(020)면 거기서 멈추고 rate_limited=True.
    """
    summary = CollectSummary()
    store_errors = 0
    ordered = sorted(refs, key=lambda ref: ref.rcept_no)  # 원본이 정정본보다 먼저 저장되게
    with engine.connect() as conn:
        known = known_symbols(conn, [ref.symbol for ref in ordered])
        done = set() if reparse else done_rcept_nos(conn, [ref.rcept_no for ref in ordered])
    for ref in ordered:
        if ref.symbol not in known:
            summary.skipped_unknown_symbol[ref.symbol] += 1
            continue
        if ref.rcept_no in done:
            summary.skipped_done += 1
            continue
        parsed = result = None
        error = None
        try:
            path = download(ref, api_key, docs_dir, session)
            parsed = parse_event_zip(path, ref.rcept_no)
            result = extract_fields(ref.event_type, parsed.pairs, field_rules)
        except DartRateLimitError:
            summary.rate_limited = True
            log.error("DART 요청 한도(020) — %s에서 멈춤. 다음 실행에서 이어 받습니다.", ref.rcept_no)
            break
        except (DartError, EventParseError, zipfile.BadZipFile, OSError) as exc:
            error = REDACTOR.redact(f"{type(exc).__name__}: {exc}")[:500]
            summary.failures.append({"rcept_no": ref.rcept_no, "symbol": ref.symbol, "title": ref.title, "error": error})
            log.warning("원문 처리 실패: %s %s — %s", ref.rcept_no, ref.title, error)
        try:
            with engine.begin() as conn:  # 1건 = 1트랜잭션: 실패하면 이 건만 되돌린다
                outcome = upsert_event(conn, ref, parsed, result, parse_error=error)
        except Exception as exc:  # 한 건 때문에 전체 실행이 멈추지 않게. 연속으로 실패하면 멈춘다(DB 장애 등)
            store_errors += 1
            message = REDACTOR.redact(f"저장 실패 {type(exc).__name__}: {exc}")[:500]
            summary.failures.append({"rcept_no": ref.rcept_no, "symbol": ref.symbol, "title": ref.title, "error": message})
            log.exception("저장 실패: %s %s", ref.rcept_no, ref.title)
            if store_errors >= MAX_CONSECUTIVE_STORE_ERRORS:
                log.error("저장 실패가 %d건 연속 — 멈춥니다.", store_errors)
                summary.stopped_on_errors = True
                break
            continue
        store_errors = 0
        summary.loaded.append(ref.rcept_no)
        summary.status["failed" if parsed is None else result.parse_status] += 1
        summary.corrects_linked += int(outcome["corrects"] is not None)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging()
    config = load_config(args.config)
    try:
        since, until = resolve_range(args, datetime.now(KST).date())
        days = days_between(since, until)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE

    api_key = get_api_key()
    if not api_key:
        print("DART_API_KEY가 없습니다 (.env 또는 환경 변수).", file=sys.stderr)
        return EXIT_NO_KEY
    REDACTOR.add(api_key)

    rules = EventRules.from_config(config)
    kind_by_type = dict(config["list"]["pblntf_types"])
    universe = load_universe_symbols(_repo_path(args.universe))
    raw_dir = _repo_path(config["paths"]["raw_dir"])
    out_dir = _repo_path(config["paths"]["out_dir"])
    session = PoliteSession()

    report = SelectReport()
    refs = []
    try:
        for day in days:
            items = fetch_day(api_key, day, config["list"], raw_dir, session=session, use_cache=not args.no_cache)
            day_refs, report = select_events(items, rules, kind_by_type, universe, report)
            refs.extend(day_refs)
    except DartRateLimitError:
        log.error("DART 요청 한도(020)에 걸렸습니다. 내일 다시 실행하세요.")
        return EXIT_RATE_LIMITED

    out_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        out_path = out_dir / f"dryrun_{since:%Y%m%d}_{until:%Y%m%d}.json"
        with out_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump({"since": since.isoformat(), "until": until.isoformat(), **report.to_dict(),
                       "events": [ref.to_dict() for ref in refs]}, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        print_summary(since, until, refs, report, out_path)
        return EXIT_OK

    # ── 저장 모드: DATABASE_URL의 DB에 쓴다
    from ..common.db import get_engine

    engine = get_engine()
    print(f"[DB] {engine.url.host}:{engine.url.port}/{engine.url.database}  (DATABASE_URL)")
    with engine.connect() as conn:
        try:
            preflight_events(conn)
        except PreflightError as exc:
            print(f"DB 점검 실패: {exc}", file=sys.stderr)
            return EXIT_FAILURES
    common = load_config(args.common_config)
    field_rules = EventFieldRules.from_config(config)
    summary = collect_events(engine, refs, api_key, raw_dir / "docs", field_rules, session=session, reparse=args.reparse)

    embed_result = None
    if summary.loaded and not args.no_embed:
        if args.offline:
            from .embedder import set_offline

            set_offline(True)
        from .embedder import embed_pending, load_encoder

        encoder, _ = load_encoder(common["model"], args.offline, args.allow_cpu)
        model_name, revision, config_hash = embedding_identity(common["model"])
        report_embed = embed_pending(engine.begin, encoder, summary.loaded, model_name=model_name,
                                     model_revision=revision, config_hash=config_hash)
        embed_result = {"pending": report_embed.pending, "embedded": report_embed.embedded, "failed": report_embed.failed}

    out_path = out_dir / f"run_{datetime.now(KST):%Y%m%d_%H%M%S}.json"
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"since": since.isoformat(), "until": until.isoformat(), "listed": report.to_dict()["selected"],
                   **summary.to_dict(), "embedding": embed_result}, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(f"\n== 수시공시 수집 {since} ~ {until} ==")
    print(f"대상 {len(refs)}건 → 저장 {len(summary.loaded)}건 {dict(summary.status)} · 이미 처리 {summary.skipped_done}건 · "
          f"stocks에 없는 종목 {sum(summary.skipped_unknown_symbol.values())}건 · 정정 연결 {summary.corrects_linked}건")
    if embed_result:
        print(f"임베딩: {embed_result}")
    if summary.failures:
        print(f"처리 실패 {len(summary.failures)}건 (다음 실행에서 다시 시도) — failures 참고")
    print(f"자세한 내용: {out_path}")
    if summary.rate_limited:
        return EXIT_RATE_LIMITED
    if summary.stopped_on_errors or (embed_result and embed_result["failed"]):
        return EXIT_FAILURES
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
