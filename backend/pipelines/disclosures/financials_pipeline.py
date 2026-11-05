"""DART 구조화 재무 수치 실행 (WO-015): collect → load → bis → validate.

  collect  data/raw/dart/financials/{종목}_{연도}_{보고서코드}_{CFS|OFS}.json, data/raw/dart/shares/{종목}_{연도}_{보고서코드}.json
  load     financials / financials_fin UPSERT, data/financials/provenance.jsonl
  bis      금융 종목 bis_ratio를 disclosure_chunks(읽기 전용)에서 추출해 UPDATE
  validate 완료 조건 자동 검사 (financials_validate)
실행 기록: logs/financials_{ts}.json (ingest_runs는 쓰지 않는다 — ingest_job enum에 재무 항목이 없음)

`--root`는 설정 `paths.*`의 상대 경로(데이터·로그)와 `.env`를 해석할 기준 디렉터리다 (기본: 이 저장소 루트).
`--config`·`--mapping` 파일 자체는 코드와 같은 저장소(현재 디렉터리 → 저장소 루트 순)에서 읽는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from app.dart_reports import DartRateLimitError
from app.targets import TARGET_SYMBOLS

from ..common.config import REPO_ROOT, data_path, load_config, resolve_path
from ..common.logging import REDACTOR, get_logger, setup_logging
from . import financials, financials_dart, financials_shares
from .loader import KST


log = get_logger("disclosures.financials")

STEPS = ["collect", "load", "bis", "validate"]
EXIT_OK, EXIT_FAILURES, EXIT_NO_KEY = 0, 1, 2
ENV_KEYS = ("DART_API_KEY", "DATABASE_URL")


class StepError(RuntimeError):
    pass


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="DART 구조화 재무 수치 수집·적재 (financials / financials_fin)")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mapping", default="configs/financials_mapping.yaml")
    ap.add_argument("--steps", default=",".join(STEPS), help="쉼표 구분: " + ",".join(STEPS))
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드 (기본: TARGET_SYMBOLS)")
    ap.add_argument("--periods", default="", help="쉼표 구분 period_end (기본: config targets.periods)")
    ap.add_argument("--refresh", action="store_true", help="저장된 원본 JSON이 있어도 다시 받는다")
    ap.add_argument("--dry-run", action="store_true", help="DART 호출·DB 쓰기 없이 계획(collect)·매핑 결과만 출력")
    ap.add_argument("--root", default=str(REPO_ROOT), help="상대 경로와 .env 기준 디렉터리 (기본: 저장소 루트)")
    return ap


def parse_steps(value: str) -> list[str]:
    steps = [s.strip() for s in value.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        raise SystemExit(f"알 수 없는 단계: {', '.join(unknown)}")
    return [s for s in STEPS if s in steps]


def load_env(root: Path) -> None:
    """DART_API_KEY·DATABASE_URL이 환경에 없으면 root/.env를 load_dotenv로 읽는다 (값은 출력하지 않음)."""
    if all(os.environ.get(key) for key in ENV_KEYS):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except ImportError:  # pragma: no cover
        pass


def read_corp_codes(engine, symbols: list[str]) -> dict[str, str]:
    """stocks.dart_corp_code를 읽는다 (읽기 전용)."""
    from sqlalchemy import bindparam, text

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT symbol, dart_corp_code FROM stocks WHERE symbol IN :ss").bindparams(bindparam("ss", expanding=True)),
            {"ss": symbols},
        ).all()
    return {symbol.strip(): (corp or "").strip() for symbol, corp in rows if corp and corp.strip()}


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1, default=str)
        handle.write("\n")
    os.replace(temp, path)


PROVENANCE_KEY = ("symbol", "period_end", "table", "column")


def update_provenance(path: Path, rows: list[dict]) -> None:
    """컬럼별 출처를 (symbol, period_end, table, column) 단위로 교체해 다시 쓴다."""
    merged: dict[tuple, dict] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    merged[tuple(row[k] for k in PROVENANCE_KEY)] = row
    for row in rows:
        merged[tuple(row[k] for k in PROVENANCE_KEY)] = json.loads(json.dumps(row, ensure_ascii=False, default=str))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for key in sorted(merged):
            handle.write(json.dumps(merged[key], ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(temp, path)


def _short(value) -> str:
    """요약 표시용: 원 단위 금액은 억원, 주당 값은 그대로."""
    if value is None:
        return "NULL"
    if value == value.to_integral_value() and abs(value) >= 10**8:
        return f"{value / 10**8:,.0f}억"
    return f"{value:,}"


class Run:
    def __init__(self, args, config: dict, *, engine=None, session=None):
        self.args = args
        self.config = config
        self.root = Path(args.root).resolve()
        self.steps = parse_steps(args.steps)
        self.statements_dir = data_path(config, "financials_raw_dir", self.root)
        self.shares_dir = data_path(config, "shares_raw_dir", self.root)
        self.logs_dir = data_path(config, "logs_dir", self.root)
        self.provenance_path = data_path(config, "financials_dir", self.root) / "provenance.jsonl"
        self.mapping_path = resolve_path(args.mapping)
        requested_periods = [p.strip() for p in args.periods.split(",") if p.strip()]
        self.periods = requested_periods or [str(p) for p in config["targets"]["periods"]]
        self.symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] or list(TARGET_SYMBOLS)
        self.engine = engine
        self.session = session
        self.api_key: str | None = None
        self.failures: list[str] = []
        self.resolved_shares: dict[tuple[str, str], financials.ShareCounts | None] = {}
        self.record: dict = {
            "started_at": datetime.now(KST).isoformat(timespec="seconds"),
            "argv": sys.argv[1:],
            "steps": self.steps,
            "dry_run": bool(args.dry_run),
            "symbols": self.symbols,
            "periods": self.periods,
        }

    def targets(self, corp_codes: dict[str, str]) -> list[financials_dart.Target]:
        return [financials_dart.Target(s, corp_codes.get(s, ""), p) for s in self.symbols for p in self.periods]

    def collect(self) -> None:
        if self.args.dry_run:
            plan = financials_dart.plan_calls(self.targets({}), self.statements_dir, self.shares_dir, refresh=self.args.refresh)
            self.record["collect_plan"] = plan
            log.info(
                "dry-run 수집 계획: 대상 %d건, 최소 호출 %d회 (재무제표 %d + 주식 총수 %d), CFS 013 시 OFS 최대 %d회 추가",
                plan["targets"], plan["min_calls"], plan[financials_dart.STATEMENTS_ENDPOINT],
                plan[financials_dart.SHARES_ENDPOINT], plan["possible_ofs_retries"],
            )
            return
        corp_codes = read_corp_codes(self.engine, self.symbols)
        missing = [s for s in self.symbols if s not in corp_codes]
        if missing:
            raise StepError(f"stocks.dart_corp_code가 없습니다: {', '.join(missing)}")
        from .dart import PoliteSession

        dart_cfg = self.config.get("dart", {})
        session = self.session or PoliteSession(
            interval=float(dart_cfg.get("request_interval_sec", 0.2)),
            attempts=int(dart_cfg.get("max_attempts", 3)),
            base_delay=float(dart_cfg.get("backoff_base_sec", 1.0)),
        )
        report = financials_dart.collect(
            self.targets(corp_codes), self.api_key, self.statements_dir, self.shares_dir, session=session, refresh=self.args.refresh
        )
        self.record["collect"] = report.to_dict()
        self.failures.extend(report.failures)
        for note in report.notes:
            log.info("참고: %s", note)
        log.info("수집 완료: 실제 호출 %d회, 재무제표 %d건, 주식 총수 %d건, 실패 %d건", report.calls, len(report.statements), len(report.shares), len(report.failures))

    def map_all(self) -> list[financials.MappedPeriod]:
        """저장된 원본만으로 대상 전체를 매핑한다 (DART·DB 호출 없음). 원본이 없으면 실패로 기록."""
        mapping = financials.load_mapping(self.mapping_path)
        mapped: list[financials.MappedPeriod] = []
        for target in self.targets({}):
            chosen = financials_dart.cached_statement(self.statements_dir, target)
            if chosen is None:
                self.failures.append(f"{target.symbol} {target.period_end}: 사용할 재무제표 원본이 없습니다 (collect 먼저)")
                continue
            fs_div, path = chosen
            shares_file = financials_dart.shares_path(self.shares_dir, target)
            shares_data = json.loads(shares_file.read_text(encoding="utf-8")) if shares_file.exists() else None
            statement = json.loads(path.read_text(encoding="utf-8"))
            rcept_nos = sorted({str(r["rcept_no"]) for r in statement.get("list", []) if r.get("rcept_no")})
            fallback_counts, fallback_source = self.resolve_share_fallback(
                target, mapping, shares_data, rcept_nos[0] if len(rcept_nos) == 1 else None
            )
            mapped.append(
                financials.map_period(
                    target.symbol, target.period_end, fs_div, statement, path.name, shares_data,
                    shares_file.name if shares_data is not None else None, mapping,
                    fallback_shares=fallback_counts, fallback_shares_source=fallback_source,
                )
            )
            self.resolved_shares[(target.symbol, target.period_end)] = mapped[-1].shares
        return mapped

    def resolve_share_fallback(self, target, mapping, shares_data: dict | None, statement_rcept_no: str | None):
        """API 주식 수가 정상인 슬롯은 그대로 두고, 불완전할 때만 같은 접수번호 청크를 조회한다."""
        api_counts = financials.parse_share_counts(shares_data) if shares_data is not None else None
        if api_counts is not None and api_counts.issued is not None and api_counts.treasury is not None:
            return None, None
        if self.engine is None or statement_rcept_no is None:
            return None, None
        from sqlalchemy import text

        with self.engine.connect() as conn:
            same_report = conn.execute(
                text("SELECT 1 FROM disclosures WHERE rcept_no = :r AND symbol = :s AND period_end = CAST(:p AS date)"
                     " AND kind IN ('annual','half','quarterly')"),
                {"r": statement_rcept_no, "s": target.symbol, "p": target.period_end},
            ).first()
            if not same_report:
                return None, {"reason": "재무 API와 같은 접수번호의 공시 청크 없음", "rcept_no": statement_rcept_no}
            voting_chunks = conn.execute(
                text("SELECT chunk_index, section, chunk_text FROM disclosure_chunks WHERE rcept_no = :r"
                     " AND (position('발행주식총수(A)' in chunk_text) > 0 OR position('의결권 현황' in chunk_text) > 0)"
                     " ORDER BY chunk_index"),
                {"r": statement_rcept_no},
            ).all()
            candidates = []
            rejected = []
            by_index = {chunk_index: (section, chunk_text) for chunk_index, section, chunk_text in voting_chunks}
            for chunk_index, section, chunk_text in voting_chunks:
                if "발행주식총수(A)" not in chunk_text:
                    continue
                parsed = financials_shares.parse_voting_rights(chunk_text, target.period_end)
                context_index = None
                previous = by_index.get(chunk_index - 1)
                if parsed.counts is None and previous and previous[0] == section and "의결권 현황" in previous[1]:
                    parsed = financials_shares.parse_voting_rights(previous[1] + "\n" + chunk_text, target.period_end)
                    context_index = chunk_index - 1 if parsed.counts is not None else None
                if parsed.counts is not None:
                    candidates.append((chunk_index, context_index, parsed))
                else:
                    rejected.append({"chunk_index": chunk_index, "reason": parsed.reason})
            if not candidates and f"{target.symbol} {target.period_end}" in mapping.capital_note_fallback_periods:
                note_chunks = conn.execute(
                    text("SELECT chunk_index, chunk_text FROM disclosure_chunks WHERE rcept_no = :r"
                         " AND position('발행주식수' in chunk_text) > 0 AND position('유통주식수' in chunk_text) > 0"
                         " ORDER BY chunk_index"),
                    {"r": statement_rcept_no},
                ).all()
                for chunk_index, chunk_text in note_chunks:
                    parsed = financials_shares.parse_capital_note(chunk_text, target.period_end)
                    if parsed.counts is not None:
                        candidates.append((chunk_index, None, parsed))
                    else:
                        rejected.append({"chunk_index": chunk_index, "reason": parsed.reason})
        unique = {(p.counts.issued, p.counts.treasury, p.counts.outstanding) for _, _, p in candidates}
        if len(unique) != 1:
            reason = "주식 수 공시 fallback 후보 없음" if not candidates else f"주식 수 공시 fallback 값이 모호함: {sorted(unique)}"
            return None, {"reason": reason, "rcept_no": statement_rcept_no, "rejected": rejected}
        indexes = [index for index, _, _ in candidates]
        parsed = candidates[0][2]
        context_indexes = [context for _, context, _ in candidates if context is not None]
        return parsed.counts, {"rcept_no": statement_rcept_no, "chunk_index": indexes[0] if len(indexes) == 1 else indexes,
                               **parsed.source, "context_chunk_index": context_indexes[0] if len(context_indexes) == 1 else context_indexes or None,
                               "rejected": rejected}

    def needs_share_fallback_db(self) -> bool:
        if "load" not in self.steps:
            return False
        for target in self.targets({}):
            path = financials_dart.shares_path(self.shares_dir, target)
            if not path.exists():
                continue
            counts = financials.parse_share_counts(json.loads(path.read_text(encoding="utf-8")))
            if counts is None or counts.issued is None or counts.treasury is None:
                return True
        return False

    def load(self) -> None:
        mapped = self.map_all()
        review = [line for m in mapped for line in m.review]
        self.record["mapping"] = {
            f"{m.symbol} {m.period_end}": {"fs_div": m.fs_div, "rcept_no": m.rcept_no, **m.values, **(m.fin_values or {})} for m in mapped
        }
        self.record["review"] = review
        for m in mapped:
            v = m.values
            fin = "" if m.fin_values is None else " | " + " ".join(f"{k}={_short(x)}" for k, x in m.fin_values.items())
            log.info(
                "%s %s %s 매출=%s 영업=%s 순익=%s 자산=%s 부채=%s 자본=%s EPS=%s BPS=%s%s",
                m.symbol, m.period_end, m.fs_div, _short(v["revenue"]), _short(v["operating_income"]), _short(v["net_income"]),
                _short(v["total_assets"]), _short(v["total_liabilities"]), _short(v["total_equity"]), _short(v["eps"]), _short(v["bps"]), fin,
            )
        for line in review:
            log.info("검토: %s", line)
        if self.args.dry_run:
            log.info("dry-run: %d건 매핑, 검토 %d건 (DB·provenance 쓰기 없음)", len(mapped), len(review))
            return
        from .financials_loader import preflight, upsert_financials, upsert_financials_fin

        with self.engine.connect() as conn:
            preflight(conn, self.symbols)
        for m in mapped:
            with self.engine.begin() as conn:
                upsert_financials(conn, m)
                if m.fin_values is not None:
                    upsert_financials_fin(conn, m)
        provenance = [{**row, "rcept_no": m.rcept_no, "fs_div": m.fs_div} for m in mapped for row in m.provenance]
        update_provenance(self.provenance_path, provenance)
        log.info("적재 완료: financials %d행, financials_fin %d행, 검토 %d건, 출처 %s",
                 len(mapped), sum(m.fin_values is not None for m in mapped), len(review), self.provenance_path)

    def fin_symbols(self) -> list[str]:
        mapping = financials.load_mapping(self.mapping_path)
        return [s for s in self.symbols if s in mapping.fin_symbols]

    def bis(self) -> None:
        """금융 종목의 bis_ratio를 disclosure_chunks(읽기 전용)에서 추출해 financials_fin에 UPDATE한다."""
        from sqlalchemy import text

        from .financials_bis import extract_total_capital_ratio
        from .financials_loader import set_ratio

        results: dict[str, dict] = {}
        provenance: list[dict] = []
        for symbol in self.fin_symbols():
            for period_end in self.periods:
                label = f"{symbol} {period_end}"
                with self.engine.connect() as conn:
                    rcept_no = conn.execute(
                        text("SELECT rcept_no FROM disclosures WHERE symbol = :s AND period_end = CAST(:p AS date)"
                             " AND kind IN ('annual', 'half', 'quarterly')"),
                        {"s": symbol, "p": period_end},
                    ).scalar()
                    chunks = [] if rcept_no is None else [
                        tuple(r) for r in conn.execute(
                            text("SELECT chunk_index, section, chunk_text FROM disclosure_chunks"
                                 " WHERE rcept_no = :r AND position('총자본비율' in chunk_text) > 0 ORDER BY chunk_index"),
                            {"r": rcept_no},
                        ).all()
                    ]
                result = extract_total_capital_ratio(chunks, period_end) if chunks else None
                value = result.value if result else None
                source = result.source if result else {"reason": "공시 또는 총자본비율 청크 없음"}
                results[label] = {"value": value, "rcept_no": rcept_no, **{k: source[k] for k in ("column", "chunk_indexes", "provisional", "reason") if k in source}}
                log.info("BIS %s: %s (%s)", label, value if value is not None else "NULL", source.get("column") or source.get("reason"))
                provenance.append({"symbol": symbol, "period_end": period_end, "table": "financials_fin", "column": "bis_ratio",
                                   "value": value, "rcept_no": rcept_no, "source": "disclosure_chunks", **source})
                if self.args.dry_run:
                    continue
                key = {"s": symbol, "p": period_end, "t": financials.period_type(period_end)}
                where = " WHERE symbol = :s AND period_end = CAST(:p AS date) AND period_type = CAST(:t AS report_period)"
                with self.engine.begin() as conn:
                    stored = conn.execute(text("SELECT bis_ratio FROM financials_fin" + where), key).all()
                    if len(stored) != 1:
                        self.failures.append(f"{label}: financials_fin 행이 없습니다 (load 먼저)")
                        continue
                    if value is None and stored[0][0] is not None:
                        # 추출 실패로 검증된 기존 값을 NULL로 덮어쓰지 않는다
                        self.failures.append(f"{label}: BIS 추출 실패 — 기존 값 {stored[0][0]} 유지 ({source.get('reason')})")
                        provenance.pop()
                        continue
                    set_ratio(conn, symbol, period_end, key["t"], "bis_ratio", value, None if value is not None else "extract_failed")
        self.record["bis"] = results
        if not self.args.dry_run:
            update_provenance(self.provenance_path, provenance)

    def validate(self) -> None:
        from .financials_validate import validate

        shares: dict[tuple[str, str], financials.ShareCounts | None] = dict(self.resolved_shares)
        mapping = financials.load_mapping(self.mapping_path)
        for target in self.targets({}):
            if (target.symbol, target.period_end) in shares:
                continue
            path = financials_dart.shares_path(self.shares_dir, target)
            if path.exists():
                shares_data = json.loads(path.read_text(encoding="utf-8"))
                counts = financials.parse_share_counts(shares_data)
                if counts is None or counts.issued is None or counts.treasury is None:
                    chosen = financials_dart.cached_statement(self.statements_dir, target)
                    rcept_no = None
                    if chosen:
                        statement = json.loads(chosen[1].read_text(encoding="utf-8"))
                        rcept_nos = sorted({str(r["rcept_no"]) for r in statement.get("list", []) if r.get("rcept_no")})
                        rcept_no = rcept_nos[0] if len(rcept_nos) == 1 else None
                    fallback, _ = self.resolve_share_fallback(target, mapping, shares_data, rcept_no)
                    counts = fallback
                shares[(target.symbol, target.period_end)] = counts
        with self.engine.connect() as conn:
            result = validate(conn, self.symbols, self.fin_symbols(), self.periods, shares=shares, provenance_path=self.provenance_path)
        self.record["validate"] = result
        for check in result["checks"]:
            mark = "OK " if check["ok"] else {"error": "FAIL", "warning": "WARN", "info": "INFO"}[check["severity"]]
            log.info("validate %s %s: %s", mark, check["name"], json.dumps(check["detail"], ensure_ascii=False, default=str)[:600])
        if not result["ok"]:
            self.failures.append("validate 실패: " + ", ".join(c["name"] for c in result["checks"] if c["severity"] == "error" and not c["ok"]))

    def execute(self) -> int:
        args = self.args
        needs_key = "collect" in self.steps and not args.dry_run
        # bis·validate는 dry-run이어도 DB를 읽는다 (쓰기는 하지 않음)
        needs_db = not args.dry_run or any(step in self.steps for step in ("bis", "validate")) or self.needs_share_fallback_db()
        if needs_key or needs_db:
            load_env(self.root)
        if needs_key:
            self.api_key = os.environ.get("DART_API_KEY") or None
            if not self.api_key:
                print("DART_API_KEY가 설정되지 않았습니다 (collect 단계). --dry-run이나 --steps로 collect를 빼면 키 없이 실행됩니다.", file=sys.stderr)
                return EXIT_NO_KEY
            REDACTOR.add(self.api_key)
        if needs_db and self.engine is None:
            from ..common.db import get_engine

            self.engine = get_engine()

        status, error = "failed", None
        try:
            for step in self.steps:
                getattr(self, step)()
            status = "failed" if self.failures else "success"
        except (DartRateLimitError, financials_dart.DartAuthError) as exc:
            error = f"DART 수집 중단: {exc}"
            self.failures.append(error)
            log.error(error)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.failures.append(error)
            log.exception("실행 실패")
        finally:
            self.record["failures"] = [REDACTOR.redact(f) for f in self.failures]
            self.record["status"] = status
            self.record["finished_at"] = datetime.now(KST).isoformat(timespec="seconds")
            ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
            log_path = self.logs_dir / f"financials_{ts}.json"
            _write_json(log_path, json.loads(REDACTOR.redact(json.dumps(self.record, ensure_ascii=False, default=str))))
            log.info("실행 기록: %s", log_path)
        if self.failures:
            print("실패 목록:", file=sys.stderr)
            for failure in self.failures:
                print(f"  - {REDACTOR.redact(failure)}", file=sys.stderr)
            return EXIT_FAILURES
        return EXIT_OK


def main(argv: list[str] | None = None, *, engine=None, session=None) -> int:
    args = build_arg_parser().parse_args(argv)
    setup_logging()
    config = load_config(args.config)
    return Run(args, config, engine=engine, session=session).execute()


if __name__ == "__main__":
    raise SystemExit(main())
