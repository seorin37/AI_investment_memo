"""공시 임베딩 파이프라인 실행 (run_dense / run_hybrid 공통).

단계: collect → parse → chunk → load → embed → validate. 단계 사이 산출물은 파일에 남아 일부 단계만 다시 돌릴 수 있다.
  collect  data/raw/dart/{종목}_{접수번호}.zip, data/raw/dart/reports.json, corpCode.xml 캐시, stocks.dart_corp_code
  parse    data/parsed/{rcept_no}.json
  chunk    data/chunks/{rcept_no}.jsonl, data/chunks/manifest.jsonl
  load     disclosures, disclosure_chunks(embedding NULL) — 문서당 트랜잭션 1개, fingerprint가 같으면 건너뜀
  embed    disclosure_chunks.embedding (+ hybrid: data/embeddings/sparse/{rcept_no}.jsonl)
  validate 완료 조건 자동 검사
실행 기록: ingest_runs 1행, logs/run_{mode}_{ts}.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Callable

from app.dart_reports import DartRateLimitError
from app.targets import TARGET_SYMBOLS

from ..common.config import REPO_ROOT, data_path, load_config, resolve_path
from ..common.logging import REDACTOR, get_logger, setup_logging
from . import chunker as chunker_mod
from . import dart, parser, sparse_store
from .loader import KST


log = get_logger("disclosures.pipeline")

STEPS = ["collect", "parse", "chunk", "load", "embed", "validate"]
EXIT_OK, EXIT_FAILURES, EXIT_NO_KEY = 0, 1, 2


class StepError(RuntimeError):
    pass


def build_arg_parser(mode: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=f"DART 정기보고서 BGE-M3 임베딩 파이프라인 ({mode})")
    ap.add_argument("--config", default="configs/common.yaml")
    ap.add_argument("--mode-config", default=f"configs/{mode}.yaml")
    ap.add_argument("--steps", default=",".join(STEPS), help="쉼표 구분: " + ",".join(STEPS))
    ap.add_argument("--symbols", default="", help="쉼표 구분 종목코드 (기본: TARGET_SYMBOLS)")
    ap.add_argument("--limit", type=int, default=None, help="처리할 문서 수 상한 (시험용)")
    ap.add_argument("--from-zip", action="append", default=[], help="DART 호출 없이 이 ZIP({종목}_{접수번호}.zip)만 처리. 여러 번 줄 수 있음")
    ap.add_argument("--dry-run", action="store_true", help="다운로드·DB 쓰기·임베딩 없이 목록·파싱·청킹 결과만 확인")
    ap.add_argument("--offline", action="store_true", help="HF_HUB_OFFLINE=1 (모델은 로컬 캐시에서만)")
    ap.add_argument("--allow-cpu", action="store_true", help="CUDA가 없으면 CPU로 실행 (기본은 중단)")
    return ap


def parse_steps(value: str) -> list[str]:
    steps = [s.strip() for s in value.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        raise SystemExit(f"알 수 없는 단계: {', '.join(unknown)}")
    return [s for s in STEPS if s in steps]


def get_api_key() -> str | None:
    """os.environ을 먼저 보고, 없으면 load_dotenv()를 시도한다. 값은 출력하지 않는다."""
    key = os.environ.get("DART_API_KEY")
    if not key:
        try:
            from dotenv import load_dotenv

            load_dotenv(REPO_ROOT / ".env")
        except ImportError:  # pragma: no cover
            pass
        key = os.environ.get("DART_API_KEY")
    return key or None


# ── 파일 산출물 ─────────────────────────────────────────
def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    os.replace(temp, path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(temp, path)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def update_manifest(manifest_path: Path, replace: dict[str, list[dict]], drop: set[str] = frozenset()) -> None:
    """문서 단위로 매니페스트 행을 교체한다. (rcept_no, chunk_index) 순으로 다시 쓴다."""
    rows = [r for r in _read_jsonl(manifest_path) if r["rcept_no"] not in replace and r["rcept_no"] not in drop]
    for new_rows in replace.values():
        rows.extend(new_rows)
    rows.sort(key=lambda r: (r["rcept_no"], r["chunk_index"]))
    _write_jsonl(manifest_path, rows)


def load_chunk_file(path: Path) -> list[chunker_mod.Chunk]:
    return [chunker_mod.Chunk(**row) for row in _read_jsonl(path)]


def chunk_summary(chunks: list[chunker_mod.Chunk]) -> dict:
    if not chunks:
        return {"chunks": 0}
    tokens = [c.token_count for c in chunks]
    types = Counter(c.block_type for c in chunks)
    top_sections = Counter(c.section.split(" > ")[0] for c in chunks)
    second_sections = Counter(" > ".join(c.section.split(" > ")[:2]) for c in chunks)
    return {
        "chunks": len(chunks),
        "table": types.get("table", 0),
        "text": types.get("text", 0),
        "table_ratio": round(types.get("table", 0) / len(chunks), 3),
        "max_tokens": max(tokens),
        "mean_tokens": round(mean(tokens), 1),
        "min_tokens": min(tokens),
        "by_top_section": dict(sorted(top_sections.items())),
        "by_section": dict(sorted(second_sections.items())),
    }


# ── 실행 ─────────────────────────────────────────────
class Run:
    def __init__(self, mode: str, args, config: dict, token_counter_factory: Callable | None, encoder_factory: Callable | None):
        self.mode = mode
        self.args = args
        self.config = config
        self.steps = parse_steps(args.steps)
        self.raw_dir = data_path(config, "raw_dir")
        self.parsed_dir = data_path(config, "parsed_dir")
        self.chunks_dir = data_path(config, "chunks_dir")
        self.sparse_dir = data_path(config, "sparse_dir") if mode == "hybrid" else None
        self.logs_dir = data_path(config, "logs_dir")
        self.manifest_path = self.chunks_dir / "manifest.jsonl"
        self.companies = {str(k): v for k, v in config["targets"]["companies"].items()}
        self.periods = [str(p) for p in config["targets"]["periods"]]
        self.symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] or list(TARGET_SYMBOLS)
        self.failures: list[str] = []
        self.timings: dict[str, float] = {}
        self.record: dict = {
            "mode": mode,
            "started_at": datetime.now(KST).isoformat(timespec="seconds"),
            "argv": sys.argv[1:],
            "steps": self.steps,
            "model": {k: config["model"].get(k) for k in ("name", "revision", "use_fp16", "devices", "max_length", "query_max_length", "batch_size")},
            "chunk": config.get("chunk"),
            "search": config.get("search"),
            "hybrid": config.get("hybrid"),
            "versions": {"parser": parser.PARSER_VERSION, "chunker": chunker_mod.CHUNKER_VERSION},
        }
        self._token_counter_factory = token_counter_factory
        self._encoder_factory = encoder_factory
        self._token_counter = None
        self.engine = None
        self.run_id = None
        self.api_key: str | None = None
        self.zip_paths: dict[str, Path] = {}

    # 공통 도구
    def token_counter(self):
        if self._token_counter is None:
            if self._token_counter_factory is not None:
                self._token_counter = self._token_counter_factory()
            else:
                from .embedder import load_tokenizer, resolve_model_path

                path = resolve_model_path(self.config["model"]["name"], self.config["model"]["revision"], self.args.offline)
                self._token_counter = chunker_mod.HFTokenCounter(load_tokenizer(path))
        return self._token_counter

    def timed(self, name: str, fn, *args):
        started = time.perf_counter()
        try:
            return fn(*args)
        finally:
            self.timings[name] = round(time.perf_counter() - started, 2)

    # 단계
    def resolve_refs(self) -> list[dart.ReportRef]:
        if self.args.from_zip:
            refs = []
            for value in self.args.from_zip:
                path = resolve_path(value)
                if not path.exists():
                    raise StepError(f"--from-zip 파일이 없습니다: {value}")
                rcept_no = path.stem.split("_", 1)[-1]
                # 메타(문서명·기간)만 읽는다. 구조 품질 검사는 parse 단계에서 문서별 실패로 처리한다.
                meta = parser.read_meta(parser.read_main_xml(path, rcept_no))
                ref = dart.ref_from_zip(path, meta["document_name"], meta["period_to"])
                self.zip_paths[ref.rcept_no] = path
                refs.append(ref)
        elif "collect" in self.steps:
            refs = self.collect()
        else:
            reports_path = self.raw_dir / "reports.json"
            if not reports_path.exists():
                raise StepError(f"{reports_path}가 없습니다. collect 단계를 먼저 실행하세요.")
            refs = dart.load_reports(reports_path)
        refs = [r for r in refs if r.symbol in self.symbols or self.args.from_zip]
        if self.args.limit is not None:
            refs = refs[: self.args.limit]
        return refs

    def collect(self) -> list[dart.ReportRef]:
        api_key = self.api_key
        dart_cfg = self.config["dart"]
        session = dart.PoliteSession(
            interval=float(dart_cfg.get("request_interval_sec", 0.2)),
            attempts=int(dart_cfg.get("max_attempts", 3)),
            base_delay=float(dart_cfg.get("backoff_base_sec", 1.0)),
        )
        result = dart.collect(
            self.symbols,
            self.periods,
            api_key,
            self.raw_dir,
            bgn_de=str(dart_cfg.get("list_bgn_de", "20240101")),
            end_de=datetime.now(KST).strftime("%Y%m%d"),
            corp_cache_days=float(dart_cfg.get("corp_code_cache_days", 7)),
            session=session,
            download=not self.args.dry_run,
        )
        self.failures.extend(result.failures)
        if not self.args.dry_run:
            known = {r.rcept_no: r for r in (dart.load_reports(self.raw_dir / "reports.json") if (self.raw_dir / "reports.json").exists() else [])}
            for ref in result.reports:
                known = {k: v for k, v in known.items() if not (v.symbol == ref.symbol and v.period_end == ref.period_end)}
                known[ref.rcept_no] = ref
            dart.save_reports(self.raw_dir / "reports.json", list(known.values()))
            from .loader import update_corp_codes

            with self.engine.begin() as conn:
                changed = update_corp_codes(conn, result.corp_codes)
            log.info("stocks.dart_corp_code 갱신 %d행", changed)
        self.record["collected"] = [r.to_dict() for r in result.reports]
        return result.reports

    def parse(self, ref: dart.ReportRef) -> parser.ParsedDocument:
        xml = parser.read_main_xml(self.zip_paths.get(ref.rcept_no, self.raw_dir / ref.zip_name()), ref.rcept_no)
        parse_cfg = self.config["parse"]
        chunk_cfg = self.config.get("chunk", {})
        quality_log = self.record.setdefault("parse_quality", {})
        try:
            doc = parser.parse_xml(
                xml,
                ref.rcept_no,
                parse_cfg["exclude_title_patterns"],
                int(chunk_cfg.get("caption_max_chars", 100)),
                int(chunk_cfg.get("caption_max_blocks", 4)),
                max_recover_errors=parse_cfg.get("max_recover_errors", 0),
            )
        except parser.ParseError as exc:
            quality_log[ref.rcept_no] = {**exc.quality, "failed": True}  # 실패 문서도 진단 지표를 남긴다
            raise
        quality_log[ref.rcept_no] = doc.quality
        if doc.quality.get("escaped_tag_names"):
            log.warning("%s: 태그처럼 생긴 본문 글자를 글자로 처리 %s", ref.rcept_no, doc.quality["escaped_tag_names"])
        dart.check_xml_period(ref, doc.period_to)
        if not self.args.dry_run:
            _write_json(self.parsed_dir / f"{ref.rcept_no}.json", doc.to_dict())
        return doc

    def chunk(self, ref: dart.ReportRef, doc: parser.ParsedDocument | None) -> list[chunker_mod.Chunk]:
        if doc is None:
            path = self.parsed_dir / f"{ref.rcept_no}.json"
            with path.open(encoding="utf-8") as handle:
                doc = parser.ParsedDocument.from_dict(json.load(handle))
        company = self.companies.get(ref.symbol)
        if not company:
            raise StepError(f"configs의 targets.companies에 {ref.symbol} 기업명이 없습니다.")
        chunks = chunker_mod.chunk_blocks(
            ref.rcept_no, doc.blocks, company, ref.period_end, self.token_counter(), chunker_mod.ChunkSettings.from_config(self.config)
        )
        if not self.args.dry_run:
            _write_jsonl(self.chunks_dir / f"{ref.rcept_no}.jsonl", [c.to_dict() for c in chunks])
        return chunks

    def load(self, ref: dart.ReportRef, chunks: list[chunker_mod.Chunk]) -> bool:
        from .loader import load_chunks, upsert_disclosure

        with self.engine.begin() as conn:
            replaced = upsert_disclosure(conn, ref)
            reloaded = load_chunks(conn, ref.rcept_no, chunks)
        for old in replaced:
            log.info("정정본 교체: %s → %s", old, ref.rcept_no)
            (self.chunks_dir / f"{old}.jsonl").unlink(missing_ok=True)
            (self.parsed_dir / f"{old}.json").unlink(missing_ok=True)
            if self.sparse_dir is not None:
                sparse_store.remove(self.sparse_dir, old)
            update_manifest(self.manifest_path, {}, drop={old})
        if reloaded and self.sparse_dir is not None:
            sparse_store.remove(self.sparse_dir, ref.rcept_no)  # 청크가 바뀌었으니 이전 sparse는 무효
        return reloaded

    def embed(self, rcept_nos: list[str]) -> dict:
        if self._encoder_factory is not None:
            encoder, model_info = self._encoder_factory()
        else:
            from .embedder import load_encoder

            encoder, model_info = load_encoder(self.config["model"], self.args.offline, self.args.allow_cpu)
        from .embedder import embed_pending, environment_info

        self.record["environment"] = {**environment_info(), **model_info}
        report = embed_pending(
            self.engine.begin,
            encoder,
            rcept_nos,
            sparse_dir=self.sparse_dir,
            commit_every=int(self.config.get("load", {}).get("commit_every", 256)),
        )
        stats = report.stats
        result = {"pending": report.pending, "embedded": report.embedded, "failed": report.failed}
        if stats is not None:
            result.update(
                seconds=round(stats.seconds, 2),
                chunks_per_sec=round(report.embedded / max(stats.seconds, 1e-9), 2),
                max_gpu_memory_gib=round(stats.max_memory_bytes / 2**30, 3),
                truncated=stats.truncated,
                oom_events=stats.oom_events,
                final_batch_size=stats.batch_size,
            )
        if report.failed:
            self.failures.append(f"임베딩 품질 검사 실패 {report.failed}청크")
        return result

    def validate(self, rcept_nos: list[str], full_scope: bool) -> dict:
        from .validate import validate

        expected = {s: len(self.periods) for s in self.symbols} if full_scope else None
        with self.engine.connect() as conn:
            result = validate(
                conn, rcept_nos, manifest_path=self.manifest_path, sparse_dir=self.sparse_dir, expected_per_symbol=expected, periods=self.periods
            )
        for check in result["checks"]:
            log.info("validate %s %s: %s", "OK " if check["ok"] else "FAIL", check["name"], check["detail"])
        for rcept_no, fingerprint in sorted(result["fingerprints"].items()):
            log.info("doc_fingerprint %s %s", rcept_no, fingerprint)
        if not result["ok"]:
            self.failures.append("validate 실패: " + ", ".join(c["name"] for c in result["checks"] if not c["ok"]))
        return result

    def execute(self) -> int:
        args = self.args
        needs_db = not args.dry_run and any(s in self.steps for s in ("collect", "load", "embed", "validate"))
        if "collect" in self.steps and not args.from_zip:
            self.api_key = get_api_key()
            if not self.api_key:
                print("DART_API_KEY가 설정되지 않았습니다 (collect 단계). --from-zip이나 --steps로 collect를 빼면 키 없이 실행됩니다.", file=sys.stderr)
                return EXIT_NO_KEY
            REDACTOR.add(self.api_key)
        if needs_db:
            from ..common.db import get_engine
            from .loader import PreflightError, preflight, start_run

            self.engine = get_engine()
            try:
                with self.engine.connect() as conn:
                    preflight(conn, self.symbols if not args.from_zip else sorted({Path(p).name[:6] for p in args.from_zip}))
            except PreflightError as exc:
                print(f"DB 시작 전 점검 실패 → 중단: {exc}", file=sys.stderr)
                return EXIT_FAILURES
            self.run_id = start_run(self.engine)

        status, error, docs = "failed", None, []
        try:
            refs = self.timed("collect", self.resolve_refs)
            self.record["documents"] = [r.to_dict() for r in refs]
            chunk_stats: dict[str, dict] = {}
            fingerprints: dict[str, str] = {}
            manifest_updates: dict[str, list[dict]] = {}
            all_chunks: list[chunker_mod.Chunk] = []
            started = time.perf_counter()
            for ref in refs:
                if args.dry_run and "parse" in self.steps and not self.zip_paths.get(ref.rcept_no, self.raw_dir / ref.zip_name()).exists():
                    log.info("dry-run: %s %s %s ZIP이 없어 목록만 확인 (다운로드하지 않음)", ref.symbol, ref.period_end, ref.rcept_no)
                    continue
                try:
                    doc = self.parse(ref) if "parse" in self.steps else None
                    chunks = None
                    if "chunk" in self.steps:
                        chunks = self.chunk(ref, doc)
                        manifest_updates[ref.rcept_no] = [c.manifest_row() for c in chunks]
                    elif "load" in self.steps:
                        chunks = load_chunk_file(self.chunks_dir / f"{ref.rcept_no}.jsonl")
                        if not chunks:
                            raise StepError(f"{ref.rcept_no}: 청크 파일이 없습니다. chunk 단계를 먼저 실행하세요.")
                    if chunks is not None:
                        chunk_stats[ref.rcept_no] = chunk_summary(chunks)
                        fingerprints[ref.rcept_no] = chunker_mod.doc_fingerprint([c.chunk_hash for c in chunks])
                        all_chunks.extend(chunks)
                        log.info("%s %s %s: %d청크, fingerprint %s", ref.symbol, ref.period_end, ref.rcept_no, len(chunks), fingerprints[ref.rcept_no][:16])
                    if "load" in self.steps and not args.dry_run:
                        reloaded = self.load(ref, chunks)
                        log.info("%s 적재: %s", ref.rcept_no, "교체 적재" if reloaded else "fingerprint 동일 → 건너뜀")
                    docs.append(ref.rcept_no)
                except DartRateLimitError:
                    raise
                except Exception as exc:  # 실패 문서는 건너뛰고 계속
                    message = REDACTOR.redact(f"{ref.symbol} {ref.period_end} {ref.rcept_no}: {type(exc).__name__}: {exc}")
                    self.failures.append(message)
                    log.error(message)
            self.timings["parse_chunk_load"] = round(time.perf_counter() - started, 2)
            if manifest_updates and not args.dry_run:
                update_manifest(self.manifest_path, manifest_updates)
            self.record["chunk_stats"] = chunk_stats
            if all_chunks:
                self.record["chunk_summary"] = chunk_summary(all_chunks)
            self.record["doc_fingerprints"] = fingerprints

            if "embed" in self.steps and not args.dry_run and docs:
                self.record["embed"] = self.timed("embed", self.embed, docs)
            if "validate" in self.steps and not args.dry_run and docs:
                full_scope = not args.from_zip and args.limit is None and not args.symbols
                self.record["validate"] = self.timed("validate", self.validate, docs, full_scope)

            if not refs:
                status = "empty"
            else:
                status = "failed" if self.failures else "success"
        except DartRateLimitError as exc:
            error = f"DART 요청 한도 초과(020)로 중단: {exc}"
            self.failures.append(error)
            log.error(error)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.failures.append(error)
            log.exception("실행 실패")
        finally:
            self.record["timings"] = self.timings
            self.record["failures"] = [REDACTOR.redact(f) for f in self.failures]
            self.record["status"] = status
            self.record["finished_at"] = datetime.now(KST).isoformat(timespec="seconds")
            ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
            log_path = self.logs_dir / f"run_{self.mode}_{ts}.json"
            _write_json(log_path, json.loads(REDACTOR.redact(json.dumps(self.record, ensure_ascii=False, default=str))))
            log.info("실행 기록: %s", log_path)
            if self.engine is not None and self.run_id is not None:
                from .loader import finish_run

                finish_run(self.engine, self.run_id, status, len(docs), "\n".join(self.failures) if self.failures else error)
        if self.failures:
            print("실패 목록:", file=sys.stderr)
            for failure in self.failures:
                print(f"  - {REDACTOR.redact(failure)}", file=sys.stderr)
            return EXIT_FAILURES
        return EXIT_OK


def main(mode: str, argv: list[str] | None = None, *, token_counter_factory=None, encoder_factory=None) -> int:
    args = build_arg_parser(mode).parse_args(argv)
    if args.offline:
        from .embedder import set_offline

        set_offline(True)  # huggingface_hub import 전에 설정
    setup_logging()
    config = load_config(args.config, args.mode_config)
    if config.get("mode") != mode:
        print(f"모드 설정이 {mode}가 아닙니다: {args.mode_config} (mode={config.get('mode')})", file=sys.stderr)
        return EXIT_FAILURES
    return Run(mode, args, config, token_counter_factory, encoder_factory).execute()
