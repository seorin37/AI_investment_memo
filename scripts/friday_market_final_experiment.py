"""금요일 데이터 최종 실증 실험 (거래일 2026-11-20). DB에는 아무것도 쓰지 않는다.

  saturday-krx  토 08:00  KRX stk_bydd_trd 조회 → Capture 대상 완전성 검증 → EPS/BPS 결합 dry-run
  saturday-krx-recovery  2026-11-20 장애 복구 전용 지연 수집(1회 요청, 기존 정상 산출물 보호)
  monday-kis    월 08:00  Capture 대상 전 종목 KIS 원시·수정 일봉 → 토요일 KRX와 전수 비교
  monday-kis-delayed-recovery  2026-11-23 WSL 종료 장애에 한정한 월요일 KIS 지연 실행
  report        저장된 파일만으로 비교·요약을 다시 만든다 (API 호출 없음)

재사용: pipelines.market.krx.fetch_kospi_daily / parse_number, metadata.normalize_market_metadata,
kis.KisClient.daily_page / normalize_daily_row, kis_fundamentals.capture_target_symbols / load_snapshot /
normalize_staged_fundamentals / analysis_ratios, daily_refresh.daily_refresh_lock.
결과 파일은 한 번만 쓴다(O_EXCL). 예약 시각 창을 벗어나면 실행하지 않고 'missed'만 기록한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import types
from contextlib import contextmanager, nullcontext
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import requests

from pipelines.common.db import load_env
from pipelines.market import krx as krx_module
from pipelines.market.kis import KisClient, normalize_daily_row
from pipelines.market.kis_fundamentals import (
    RAW_SNAPSHOT_ROOT,
    FundamentalsSnapshotError,
    analysis_ratios,
    capture_target_symbols,
    load_snapshot,
    normalize_staged_fundamentals,
)
from pipelines.market.krx import KRX_URL, fetch_kospi_daily, parse_number
from pipelines.market.metadata import normalize_market_metadata

SEOUL = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRADE_DATE = date(2026, 11, 20)
OUT_ROOT = PROJECT_ROOT / "logs" / "diagnostics" / "friday_market_final_experiment"
SAT_DIRNAME, MON_DIRNAME = "20261120", "20261123"
# (시작 허용 시작, 시작 허용 끝) — 이 창을 벗어난 실행은 '과거 데이터인 척' 하지 않고 중단
SAT_WINDOW = (datetime(2026, 11, 21, 7, 59, tzinfo=SEOUL), datetime(2026, 11, 21, 8, 30, tzinfo=SEOUL))
MON_WINDOW = (datetime(2026, 11, 23, 7, 59, tzinfo=SEOUL), datetime(2026, 11, 23, 8, 15, tzinfo=SEOUL))
MON_DEADLINE = datetime(2026, 11, 23, 8, 45, tzinfo=SEOUL)  # Morning 09:00 전 여유. 이후 새 요청 없음
MON_DELAYED_RUN_DATE = date(2026, 11, 23)
MON_DELAYED_MAX_RUNTIME = timedelta(minutes=45)
EXPECTED_INTERVAL = 0.5
REQUEST_CAP_EXTRA = 200  # 2N + 재시도 여유
MONDAY_ALLOWED_NO_KRX = {TRADE_DATE: {"417310"}}  # 11/20 상장폐지. 이 실험에만 한정
GUARDED_SERVICES = (
    "memos-market-refresh-morning.service",
    "memos-market-refresh-evening.service",
    "memos-kis-two-stage-capture.service",
    "memos-kis-two-stage-finalize.service",
    "memos-adjusted-price-check.service",
)
KRX_FIELDS = {  # 정규화 이름: (KRX 필드, 정수 여부)
    "open": ("TDD_OPNPRC", False), "high": ("TDD_HGPRC", False), "low": ("TDD_LWPRC", False),
    "close": ("TDD_CLSPRC", False), "volume": ("ACC_TRDVOL", True), "trade_value": ("ACC_TRDVAL", False),
    "market_cap": ("MKTCAP", False), "listed_shares": ("LIST_SHRS", True),
}
OHLCV = ("open", "high", "low", "close", "volume")


# ───────────────────────── 공통 ─────────────────────────
def now_kst() -> datetime:
    return datetime.now(SEOUL)


def iso(dt: datetime) -> str:
    return dt.astimezone(SEOUL).isoformat()


def jdump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str).encode("utf-8")


class Store:
    """한 실행 디렉터리. 모든 파일은 새로 만들기만 한다(덮어쓰기 금지)."""

    def __init__(self, root: Path):
        self.root = root
        self.written: list[Path] = []

    def write(self, rel: str, data: bytes | dict | list) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = data if isinstance(data, bytes) else jdump(data)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        self.written.append(path)
        return path

    def checksums(self) -> Path:
        lines = []
        for path in sorted(p for p in self.root.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(self.root)}")
        return self.write("SHA256SUMS", ("\n".join(lines) + "\n").encode())


def claim_run(root: Path, name: str, started: datetime) -> Store:
    """같은 단계가 두 번 실행되지 않도록 run 마커를 O_EXCL로 만든다."""
    store = Store(root)
    store.write(f"{name}_run_started.json", {"started_at_kst": iso(started), "pid": os.getpid()})
    return store


def active_services(runner: Callable = subprocess.run) -> list[str]:
    active = []
    for service in GUARDED_SERVICES:
        result = runner(["systemctl", "--user", "is-active", "--quiet", service], check=False,
                        capture_output=True, text=True)
        if result.returncode == 0:
            active.append(service)
        elif result.returncode not in (3, 4):  # 3=inactive, 4=unit 없음
            raise RuntimeError(f"systemd 상태를 확인하지 못했습니다: {service}")
    return active


@contextmanager
def guarded_lock(wait_until: datetime, *, lock_factory=None, services=active_services, now=now_kst):
    """다른 수집 서비스가 끝나고 daily_refresh advisory lock을 잡을 때까지 wait_until까지만 기다린다."""
    if lock_factory is None:
        from pipelines.daily_refresh import daily_refresh_lock as lock_factory
    checks = []
    while True:
        busy = services()
        if not busy:
            with lock_factory() as acquired:
                checks.append({"at": iso(now()), "active_services": busy, "lock_acquired": acquired})
                if acquired:
                    yield {"checks": checks, "lock_acquired": True}
                    return
        else:
            checks.append({"at": iso(now()), "active_services": busy, "lock_acquired": None})
        if now() >= wait_until:
            yield {"checks": checks, "lock_acquired": False}
            return
        time.sleep(30)


def frozen_targets(capture_root: Path, trade_date: date) -> dict:
    """금요일 Capture가 고정한 대상. 실패하면 예외 그대로 (토요일 작업 중단 사유)."""
    summary_path = capture_root / trade_date.isoformat() / "capture_summary.json"
    symbols = capture_target_symbols(capture_root, trade_date)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "capture_summary_path": str(summary_path),
        "capture_summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "capture_summary_mtime_kst": iso(datetime.fromtimestamp(summary_path.stat().st_mtime, SEOUL)),
        "target_count": len(symbols),
        "captured": len(summary.get("captured_symbols", [])),
        "skipped": len(summary.get("skipped_symbols", [])),
        "failed": len(summary.get("failed_symbols", [])),
        "errors": summary.get("errors", {}),
        "target_symbols": list(symbols),
    }


def capture_snapshot_stats(capture_root: Path, trade_date: date, symbols: Iterable[str]) -> dict:
    """Capture JSON 파일들의 수집 시각 범위와 EPS/BPS/PER/PBR 보유 현황."""
    times, have = [], {"eps": 0, "bps": 0, "per": 0, "pbr": 0}
    missing_files, invalid_files = [], []
    for symbol in symbols:
        try:
            snap = load_snapshot(capture_root, trade_date, symbol)
        except FundamentalsSnapshotError:
            exists = (capture_root / trade_date.isoformat() / f"{symbol}.json").exists()
            (invalid_files if exists else missing_files).append(symbol)
            continue
        times.append(snap["collected_at"])
        for key in have:
            if str(snap["raw_output"].get(key, "")).strip() not in ("", "-"):
                have[key] += 1
    return {
        "snapshot_files": len(times),
        "missing_files": missing_files,
        "invalid_files": invalid_files,
        "collected_at_first_kst": iso(min(times)) if times else None,
        "collected_at_last_kst": iso(max(times)) if times else None,
        "fields_present": have,
    }


# ───────────────────────── 토요일: KRX ─────────────────────────
@contextmanager
def recorded_krx_http(log: list[dict]):
    """krx 모듈 안의 requests.get만 감싸 응답 원본을 남긴다. 요청 헤더(AUTH_KEY)는 기록하지 않는다."""
    real = krx_module.requests

    def get(url, **kwargs):
        started = now_kst()
        entry = {"url": url, "params": kwargs.get("params"), "started_at_kst": iso(started)}
        try:
            response = real.get(url, **kwargs)
        except Exception as exc:
            entry.update(received_at_kst=iso(now_kst()), error_type=type(exc).__name__)
            log.append(entry)
            raise
        entry.update(received_at_kst=iso(now_kst()), status=response.status_code,
                     elapsed_ms=round(response.elapsed.total_seconds() * 1000),
                     content_type=response.headers.get("Content-Type"), bytes=len(response.content),
                     _content=response.content)
        log.append(entry)
        return response

    krx_module.requests = types.SimpleNamespace(
        get=get, Timeout=real.Timeout, ConnectionError=real.ConnectionError, HTTPError=real.HTTPError)
    try:
        yield
    finally:
        krx_module.requests = real


def normalize_krx_row(row: dict) -> dict:
    """원본은 그대로 두고 파싱 결과와 판정만 덧붙인다. O/H/L을 종가로 바꾸는 등의 보정은 하지 않는다."""
    out = {"symbol": str(row.get("ISU_CD") or "").strip(), "name": row.get("ISU_NM"),
           "market": row.get("MKT_NM"), "bas_dd": row.get("BAS_DD"), "parse_errors": [], "raw": row}
    for name, (field, integer) in KRX_FIELDS.items():
        try:
            value = parse_number(row.get(field), integer=integer)
            out[name] = None if value is None else str(value)
        except ValueError as exc:
            out[name] = None
            out["parse_errors"].append(f"{field}:{exc}")
    try:
        meta = normalize_market_metadata(row)
        out["metadata_ok"] = True
        out["metadata_trade_date"] = meta["trade_date"].isoformat()
    except ValueError as exc:
        out["metadata_ok"] = False
        out["metadata_error"] = str(exc)[:200]
    p = {k: (Decimal(out[k]) if out.get(k) is not None else None) for k in ("open", "high", "low", "close")}
    vol = int(out["volume"]) if out.get("volume") is not None else None
    out["zero_volume"] = vol == 0
    out["volume_negative"] = vol is not None and vol < 0
    out["ohlc_has_zero"] = any(v == 0 for v in p.values() if v is not None)
    out["ohlc_missing"] = any(v is None for v in p.values())
    if out["ohlc_missing"] or out["ohlc_has_zero"]:
        out["ohlc_valid"] = False
    else:
        out["ohlc_valid"] = (p["high"] >= max(p.values()) and p["low"] <= min(p.values()) and min(p.values()) > 0)
    return out


def completeness(norm_rows: list[dict], targets: list[str], trade_date: date) -> dict:
    expected = trade_date.strftime("%Y%m%d")
    codes = [r["symbol"] for r in norm_rows]
    dup = sorted({c for c in codes if codes.count(c) > 1})
    by = {r["symbol"]: r for r in norm_rows}
    kospi = {r["symbol"] for r in norm_rows if r.get("market") == "KOSPI"}
    tset = set(targets)
    in_targets = [by[s] for s in targets if s in by]
    return {
        "response_rows": len(norm_rows),
        "markets": {m: sum(1 for r in norm_rows if r.get("market") == m) for m in sorted({str(r.get("market")) for r in norm_rows})},
        "bas_dd_values": sorted({str(r.get("bas_dd")) for r in norm_rows}),
        "all_rows_bas_dd_ok": all(r.get("bas_dd") == expected for r in norm_rows) and bool(norm_rows),
        "duplicate_symbols": dup,
        "target_count": len(targets),
        "targets_present": len(in_targets),
        "missing_targets": sorted(tset - set(by)),
        "targets_present_non_kospi_market": sorted(s for s in targets if s in by and by[s].get("market") != "KOSPI"),
        "extra_kospi_symbols": sorted(kospi - tset),
        "parse_error_symbols": sorted(r["symbol"] for r in in_targets if r["parse_errors"]),
        "ohlc_invalid_traded": sorted(r["symbol"] for r in in_targets if not r["ohlc_valid"] and not r["zero_volume"]),
        "ohlc_invalid_zero_volume": sorted(r["symbol"] for r in in_targets if not r["ohlc_valid"] and r["zero_volume"]),
        "volume_negative": sorted(r["symbol"] for r in in_targets if r["volume_negative"]),
        "zero_volume_symbols": sorted(r["symbol"] for r in in_targets if r["zero_volume"]),
        "zero_volume_ohlc_patterns": _zero_patterns(r for r in in_targets if r["zero_volume"]),
        "market_cap_present": sum(1 for r in in_targets if r.get("market_cap") not in (None, "0")),
        "listed_shares_present": sum(1 for r in in_targets if r.get("listed_shares") not in (None, "0")),
        "metadata_normalize_failed": sorted(r["symbol"] for r in in_targets if not r["metadata_ok"]),
    }


def _zero_patterns(rows) -> dict:
    patterns: dict[str, int] = {}
    for r in rows:
        key = "O/H/L=" + "/".join("0" if r.get(k) in ("0", None) else ("C" if r.get(k) == r.get("close") else "x")
                                  for k in ("open", "high", "low")) + (" C>0" if r.get("close") not in ("0", None) else " C=0")
        patterns[key] = patterns.get(key, 0) + 1
    return patterns


def fundamentals_dry_run(targets: list[str], by_symbol: dict, capture_root: Path, trade_date: date) -> dict:
    rows, counts = {}, {"analysis_per": 0, "analysis_pbr": 0, "per_null": 0, "pbr_null": 0,
                        "join_failed": 0, "calc_error": 0, "reference_price_ne_krx_close": 0}
    null_reasons = {"eps_missing": 0, "eps_nonpositive": 0, "bps_missing": 0, "bps_nonpositive": 0}
    for symbol in targets:
        krx = by_symbol.get(symbol)
        try:
            snapshot = load_snapshot(capture_root, trade_date, symbol)
        except FundamentalsSnapshotError as exc:
            counts["join_failed"] += 1
            rows[symbol] = {"status": "join_failed", "reason": f"capture:{exc}"[:200]}
            continue
        if krx is None or krx.get("close") is None:
            counts["join_failed"] += 1
            rows[symbol] = {"status": "join_failed", "reason": "krx_row_or_close_missing"}
            continue
        try:
            final_daily = {"symbol": symbol, "trade_date": trade_date, "close": Decimal(krx["close"]),
                           "volume": int(krx["volume"]) if krx.get("volume") is not None else None}
            row, warnings = normalize_staged_fundamentals(snapshot, final_daily)
            ratios = analysis_ratios(row)
        except Exception as exc:  # 종목별 격리
            counts["calc_error"] += 1
            rows[symbol] = {"status": "calc_error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            continue
        for kind, ratio, base in (("per", "analysis_per", "eps"), ("pbr", "analysis_pbr", "bps")):
            if ratios[ratio] is None:
                counts[f"{kind}_null"] += 1
                null_reasons[f"{base}_missing" if row.get(base) is None else f"{base}_nonpositive"] += 1
            else:
                counts[ratio] += 1
        if "stck_prpr:final_close_mismatch" in warnings:
            counts["reference_price_ne_krx_close"] += 1
        rows[symbol] = {
            "status": "ok", "eps": row["eps"], "bps": row["bps"], "kis_per": row["per"], "kis_pbr": row["pbr"],
            "reference_price_capture": row["reference_price"], "final_close_krx": row["final_close"],
            "analysis_per": ratios["analysis_per"], "analysis_pbr": ratios["analysis_pbr"],
            "capture_collected_at": row["collected_at"], "warnings": warnings,
        }
    return {"counts": counts, "null_reasons": null_reasons, "rows": rows}


def run_saturday(out_dir: Path, *, trade_date: date = TRADE_DATE, capture_root: Path = RAW_SNAPSHOT_ROOT,
                 fetcher: Callable[[date], list[dict]] = fetch_kospi_daily, window=SAT_WINDOW,
                 lock_kwargs: dict | None = None, now=now_kst, recovery: bool = False,
                 max_attempts: int = 3) -> int:
    started = now()
    out_dir.mkdir(parents=True, exist_ok=True)
    if recovery and trade_date != TRADE_DATE:
        print("ABORT: 지연 복구는 거래일 2026-11-20에만 허용됨")
        return 10
    if not recovery and not (window[0] <= started <= window[1]):
        Store(out_dir).write(f"saturday_missed_{started.strftime('%Y%m%dT%H%M%S')}.json",
                             {"status": "missed", "started_at_kst": iso(started), "window": [iso(w) for w in window],
                              "note": "예약 창 밖이라 KRX를 호출하지 않음"})
        print("MISSED: 예약 창 밖 실행 — 아무것도 호출하지 않음"); return 2
    if recovery:
        completed_outputs = [
            "saturday_summary.json", "krx_normalized.json", "krx_completeness.json",
            "fundamentals_dry_run.json", "SHA256SUMS",
        ]
        existing = [name for name in completed_outputs if (out_dir / name).exists()]
        if existing:
            print("ABORT: 기존 KRX 정상/검증 산출물 보호 — " + ", ".join(existing))
            return 11
    store = claim_run(out_dir, "saturday_recovery" if recovery else "saturday", started)
    meta = {"trade_date": trade_date.isoformat(), "started_at_kst": iso(started), "db_writes": 0,
            "delayed_recovery": recovery, "max_attempts": max_attempts}
    try:
        targets_info = frozen_targets(capture_root, trade_date)
    except Exception as exc:
        meta.update(status="aborted_no_capture_targets", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        store.write("saturday_summary.json", meta); store.checksums()
        print("ABORT: 금요일 Capture 대상 목록 없음 —", meta["error"]); return 3
    targets = targets_info["target_symbols"]
    capture_targets_path = out_dir / "capture_targets.json"
    if recovery and capture_targets_path.exists():
        saved_targets = json.loads(capture_targets_path.read_text(encoding="utf-8"))
        if (saved_targets.get("capture_summary_sha256") != targets_info["capture_summary_sha256"]
                or saved_targets.get("target_symbols") != targets_info["target_symbols"]):
            meta.update(status="aborted_capture_targets_changed")
            store.write("saturday_summary.json", meta); store.checksums()
            print("ABORT: 기존 토요일 Capture 대상 또는 summary 해시가 현재 원본과 다름")
            return 12
    else:
        store.write("capture_targets.json", targets_info)
    meta["capture"] = {k: v for k, v in targets_info.items() if k != "target_symbols"}
    meta["capture"]["snapshots"] = capture_snapshot_stats(capture_root, trade_date, targets)

    http_log: list[dict] = []
    with guarded_lock(window[1] + timedelta(minutes=10), now=now, **(lock_kwargs or {})) as guard:
        meta["preflight"] = guard
        if not guard["lock_acquired"]:
            meta["status"] = "aborted_lock_or_services_busy"
            store.write("saturday_summary.json", meta); store.checksums()
            print("ABORT: 수집 서비스 실행 중이거나 lock 획득 실패"); return 4
        fetch_error = None
        with recorded_krx_http(http_log) if fetcher is fetch_kospi_daily else nullcontext():
            try:
                rows = (fetcher(trade_date, max_attempts=max_attempts)
                        if fetcher is fetch_kospi_daily else fetcher(trade_date))
            except Exception as exc:
                rows, fetch_error = None, f"{type(exc).__name__}: {str(exc)[:300]}"
    for n, entry in enumerate(http_log, 1):
        content = entry.pop("_content", None)
        if content is not None:
            entry["saved_as"] = f"krx_raw_response_attempt{n}.json"
            entry["sha256"] = hashlib.sha256(content).hexdigest()
            store.write(entry["saved_as"], content)
    meta["krx_request"] = {"endpoint": KRX_URL, "params": {"basDd": trade_date.strftime("%Y%m%d")},
                           "http_requests": len(http_log), "attempts": http_log}
    if rows is None:
        meta.update(status="krx_fetch_failed", error=fetch_error)
        store.write("saturday_summary.json", meta); store.checksums()
        print("FAIL: KRX 조회 실패 —", fetch_error); return 5
    if fetcher is not fetch_kospi_daily:  # 테스트용 fetcher: 원본 대신 받은 rows를 보존
        store.write("krx_raw_response_attempt1.json", {"OutBlock_1": rows})
    norm = [normalize_krx_row(r) for r in rows if isinstance(r, dict)]
    store.write("krx_normalized.json", {"trade_date": trade_date.isoformat(), "rows": norm})
    comp = completeness(norm, targets, trade_date)
    store.write("krx_completeness.json", comp)
    by_symbol = {r["symbol"]: r for r in norm if r.get("market") == "KOSPI"}
    fund = fundamentals_dry_run(targets, by_symbol, capture_root, trade_date)
    store.write("fundamentals_dry_run.json", fund)
    ok = (bool(norm) and comp["all_rows_bas_dd_ok"] and not comp["duplicate_symbols"] and not comp["missing_targets"]
          and not comp["parse_error_symbols"] and not comp["ohlc_invalid_traded"] and not comp["volume_negative"])
    meta.update(status="complete" if ok else ("empty_response" if not norm else "incomplete"),
                finished_at_kst=iso(now()), completeness={k: (v if not isinstance(v, list) or len(v) <= 50 else f"{len(v)}건")
                                                          for k, v in comp.items()},
                fundamentals=fund["counts"], fundamentals_null_reasons=fund["null_reasons"])
    store.write("saturday_summary.json", meta)
    store.checksums()
    print(json.dumps({k: meta[k] for k in ("status", "completeness", "fundamentals")}, ensure_ascii=False, default=str, indent=1))
    return 0 if ok else 6


# ───────────────────────── 월요일: KIS ─────────────────────────
class RecordingSession(requests.Session):
    """KisClient에 주입. 시세 GET의 응답 본문만 기록하고, 상한을 넘으면 즉시 중단. 토큰 응답은 기록하지 않는다."""

    def __init__(self, cap: int):
        super().__init__()
        self.cap, self.gets, self.records = cap, 0, []

    def get(self, url, **kwargs):
        if self.gets >= self.cap:
            raise RequestCapExceeded(f"KIS 시세 요청 상한 {self.cap}회 도달")
        self.gets += 1
        started = now_kst()
        entry = {"path": url.split(".com:9443")[-1], "params": kwargs.get("params"), "started_at_kst": iso(started)}
        try:
            response = super().get(url, **kwargs)
        except Exception as exc:
            entry.update(received_at_kst=iso(now_kst()), error_type=type(exc).__name__)
            self.records.append(entry); raise
        entry.update(received_at_kst=iso(now_kst()), status=response.status_code, body=response.text)
        self.records.append(entry)
        return response

    def post(self, url, **kwargs):  # 토큰 발급: 본문(토큰)은 남기지 않음
        response = super().post(url, **kwargs)
        self.records.append({"path": "token", "status": response.status_code, "at_kst": iso(now_kst())})
        return response


class RequestCapExceeded(RuntimeError):
    pass


class MondayInputError(RuntimeError):
    pass


def _verify_sha256_manifest(root: Path, required: set[str]) -> dict[str, str]:
    manifest_path = root / "SHA256SUMS"
    if not manifest_path.is_file():
        raise MondayInputError("KRX SHA256SUMS가 없습니다.")
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, rel = line.partition("  ")
        if not separator or len(digest) != 64 or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise MondayInputError("KRX SHA256SUMS 형식이 올바르지 않습니다.")
        path = root / rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise MondayInputError(f"KRX SHA-256 불일치: {rel}")
        entries[rel] = digest
    missing = sorted(required - set(entries))
    if missing:
        raise MondayInputError(f"KRX SHA256SUMS 필수 항목 누락: {missing}")
    return entries


def validate_monday_inputs(sat_dir: Path, targets_info: dict, trade_date: date) -> dict:
    """KIS 요청 전에 토요일 원본·검증 결과를 고정 조건으로 확인한다."""
    expected_bas_dd = trade_date.strftime("%Y%m%d")
    targets = targets_info["target_symbols"]
    allowed_missing = MONDAY_ALLOWED_NO_KRX.get(trade_date, set())
    if trade_date != TRADE_DATE or len(targets) != 936:
        raise MondayInputError("거래일 또는 Capture 936종목 조건이 다릅니다.")

    required = {"capture_targets.json", "saturday_summary.json", "krx_raw_response_attempt1.json",
                "krx_normalized.json", "krx_completeness.json", "fundamentals_dry_run.json"}
    manifest = _verify_sha256_manifest(sat_dir, required)
    saved_targets = json.loads((sat_dir / "capture_targets.json").read_text(encoding="utf-8"))
    if (saved_targets.get("capture_summary_sha256") != targets_info["capture_summary_sha256"]
            or saved_targets.get("target_symbols") != targets):
        raise MondayInputError("금요일 Capture 대상 또는 summary SHA-256이 토요일 입력과 다릅니다.")

    summary = json.loads((sat_dir / "saturday_summary.json").read_text(encoding="utf-8"))
    attempts = (summary.get("krx_request") or {}).get("attempts") or []
    if (summary.get("trade_date") != trade_date.isoformat()
            or (summary.get("krx_request") or {}).get("params", {}).get("basDd") != expected_bas_dd
            or (summary.get("krx_request") or {}).get("http_requests") != 1
            or len(attempts) != 1 or attempts[0].get("status") != 200):
        raise MondayInputError("KRX 요청 기준일·요청 수·HTTP 결과가 고정 조건과 다릅니다.")
    raw_name = attempts[0].get("saved_as")
    raw_path = sat_dir / str(raw_name)
    raw_digest = hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.is_file() else None
    if (raw_name != "krx_raw_response_attempt1.json" or attempts[0].get("sha256") != raw_digest
            or manifest.get(raw_name) != raw_digest):
        raise MondayInputError("KRX 원본 SHA-256 기록이 서로 일치하지 않습니다.")

    raw_rows = json.loads(raw_path.read_text(encoding="utf-8")).get("OutBlock_1")
    comp = json.loads((sat_dir / "krx_completeness.json").read_text(encoding="utf-8"))
    norm_rows = json.loads((sat_dir / "krx_normalized.json").read_text(encoding="utf-8")).get("rows")
    if not isinstance(raw_rows, list) or not isinstance(norm_rows, list):
        raise MondayInputError("KRX 원본 또는 정규화 행 형식이 올바르지 않습니다.")
    missing = set(comp.get("missing_targets") or [])
    blocking = {
        "response_rows": comp.get("response_rows") != 935,
        "targets_present": comp.get("targets_present") != 935,
        "target_count": comp.get("target_count") != 936,
        "bas_dd": comp.get("bas_dd_values") != [expected_bas_dd] or not comp.get("all_rows_bas_dd_ok"),
        "duplicates": bool(comp.get("duplicate_symbols")),
        "extras": bool(comp.get("extra_kospi_symbols")),
        "parse_errors": bool(comp.get("parse_error_symbols")),
        "missing": missing != allowed_missing,
        "raw_rows": len(raw_rows) != 935,
        "normalized_rows": len(norm_rows) != 935,
    }
    failed = sorted(name for name, bad in blocking.items() if bad)
    norm_symbols = {r.get("symbol") for r in norm_rows if r.get("market") == "KOSPI"}
    expected_comparable = set(targets) - allowed_missing
    if failed or norm_symbols != expected_comparable:
        detail = failed or ["normalized_symbol_set"]
        raise MondayInputError(f"KRX 935종목 사전검증 실패: {detail}")
    return {
        "capture_targets": len(targets), "kis_query_targets": len(targets),
        "krx_comparison_targets": len(expected_comparable),
        "unverified_no_krx": sorted(allowed_missing), "bas_dd": expected_bas_dd,
        "raw_sha256": raw_digest,
    }


def pick_row(rows: list[dict], trade_date: date) -> dict | None:
    target = trade_date.strftime("%Y%m%d")
    matches = [r for r in rows if r.get("stck_bsop_date") == target]
    return matches[0] if matches else None


def kis_observation(client, symbol: str, trade_date: date, *, adjusted: bool) -> dict:
    try:
        rows = client.daily_page(symbol, trade_date, trade_date, adjusted=adjusted)
    except RequestCapExceeded:
        raise
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    raw = pick_row(rows, trade_date)
    if raw is None:
        return {"status": "no_row", "rows_returned": len(rows)}
    obs = {"status": "ok", "raw": raw, "rows_returned": len(rows),
           **{k: raw.get(f) for k, f in (("open", "stck_oprc"), ("high", "stck_hgpr"), ("low", "stck_lwpr"),
                                          ("close", "stck_clpr"), ("volume", "acml_vol"), ("trade_value", "acml_tr_pbmn"))}}
    try:
        norm = normalize_daily_row(symbol, raw, adjusted=adjusted)
        obs["normalize"] = "ok" if norm is not None else "zero_ohlc_skipped"
    except ValueError as exc:
        obs["normalize"] = f"invalid: {str(exc)[:120]}"
    return obs


def output1_reference(records: list[dict]) -> dict | None:
    """원시 일봉 응답 output1의 현재 기준 상장주식수·시가총액(억원). 11-20 기준값이 아닐 수 있어 참고용."""
    for rec in records:
        if rec.get("params", {}).get("FID_ORG_ADJ_PRC") == "1" and rec.get("body"):
            try:
                o1 = json.loads(rec["body"]).get("output1") or {}
                return {"lstn_stcn": o1.get("lstn_stcn"), "hts_avls": o1.get("hts_avls")}
            except ValueError:
                return None
    return None


def monday_effective_deadline(started: datetime, trade_date: date, *, delayed_recovery: bool,
                              normal_deadline: datetime = MON_DEADLINE) -> datetime:
    """정상 deadline은 고정하고, 승인된 11/20 복구 실행에만 45분 예산을 부여한다."""
    if not delayed_recovery:
        return normal_deadline
    if trade_date != TRADE_DATE or started.astimezone(SEOUL).date() != MON_DELAYED_RUN_DATE:
        raise MondayInputError("KIS 지연 복구는 2026-11-23에 거래일 2026-11-20만 허용됩니다.")
    return started + MON_DELAYED_MAX_RUNTIME


def run_monday(out_dir: Path, sat_dir: Path, *, trade_date: date = TRADE_DATE, capture_root: Path = RAW_SNAPSHOT_ROOT,
               client_factory=None, window=MON_WINDOW, deadline=MON_DEADLINE, lock_kwargs: dict | None = None,
               now=now_kst, delayed_recovery: bool = False) -> int:
    started = now()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        effective_deadline = monday_effective_deadline(
            started, trade_date, delayed_recovery=delayed_recovery, normal_deadline=deadline)
    except MondayInputError as exc:
        print("ABORT:", exc)
        return 14
    if not delayed_recovery and not (window[0] <= started <= window[1]):
        Store(out_dir).write(f"monday_missed_{started.strftime('%Y%m%dT%H%M%S')}.json",
                             {"status": "missed", "started_at_kst": iso(started), "window": [iso(w) for w in window],
                              "note": "예약 창 밖이라 KIS를 호출하지 않음 — 별도 일정으로 연기 필요"})
        print("MISSED: 예약 창 밖 실행 — 아무것도 호출하지 않음"); return 2
    meta = {"trade_date": trade_date.isoformat(), "started_at_kst": iso(started),
            "deadline_kst": iso(effective_deadline), "normal_deadline_kst": iso(deadline),
            "scheduled_window_kst": [iso(w) for w in window], "delayed_recovery": delayed_recovery,
            "actual_execution_date_kst": started.astimezone(SEOUL).date().isoformat(), "db_writes": 0}
    try:
        info = frozen_targets(capture_root, trade_date)
    except Exception as exc:
        meta.update(status="aborted_no_capture_targets", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        Store(out_dir).write(f"monday_preflight_failed_{started.strftime('%Y%m%dT%H%M%S')}.json", meta)
        return 3
    try:
        input_validation = validate_monday_inputs(sat_dir, info, trade_date)
    except Exception as exc:
        meta.update(status="aborted_invalid_krx_input", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        Store(out_dir).write(f"monday_preflight_failed_{started.strftime('%Y%m%dT%H%M%S')}.json", meta)
        print("ABORT: KIS 호출 전 KRX 입력 사전검증 실패 —", meta["error"])
        return 13
    store = claim_run(out_dir, "monday_delayed_recovery" if delayed_recovery else "monday", started)
    targets = info["target_symbols"]
    sat_targets = sat_dir / "capture_targets.json"
    meta["targets"] = {"count": len(targets), "capture_summary_sha256": info["capture_summary_sha256"],
                       "same_as_saturday": (json.loads(sat_targets.read_text(encoding="utf-8"))["capture_summary_sha256"]
                                            == info["capture_summary_sha256"]) if sat_targets.exists() else None}
    meta["input_validation"] = input_validation
    cap = 2 * len(targets) + REQUEST_CAP_EXTRA
    est_seconds = 2 * len(targets) * (EXPECTED_INTERVAL + 0.12)
    meta["plan"] = {"expected_quotation_requests": 2 * len(targets), "request_cap": cap,
                    "estimated_seconds": round(est_seconds), "estimated_finish_kst": iso(started + timedelta(seconds=est_seconds)),
                    "fits_before_deadline": started + timedelta(seconds=est_seconds) <= effective_deadline}
    results: dict[str, dict] = {}
    deferred: list[str] = []
    stop_reason = None
    lock_wait_until = started if delayed_recovery else window[1]
    with guarded_lock(lock_wait_until, now=now, **(lock_kwargs or {})) as guard:
        meta["preflight"] = guard
        if not guard["lock_acquired"]:
            meta["status"] = "aborted_lock_or_services_busy"
            store.write("monday_summary.json", meta); store.checksums(); return 4
        if client_factory is None:
            session = RecordingSession(cap)
            client = KisClient(session=session)
        else:
            client, session = client_factory(cap)
        meta["client"] = {"request_interval": getattr(client, "request_interval", None)}
        if meta["client"]["request_interval"] not in (None, EXPECTED_INTERVAL):
            meta["status"] = "aborted_interval_mismatch"
            store.write("monday_summary.json", meta); store.checksums(); return 7
        meta["kis_query_started_at_kst"] = iso(now())
        try:
            for i, symbol in enumerate(targets):
                if now() >= effective_deadline:
                    deferred = targets[i:]; stop_reason = "deadline"; break
                mark = len(session.records)
                before = dict(client.request_metrics()) if hasattr(client, "request_metrics") else {}
                try:
                    raw = kis_observation(client, symbol, trade_date, adjusted=False)
                    adj = kis_observation(client, symbol, trade_date, adjusted=True)
                except RequestCapExceeded as exc:
                    deferred = targets[i:]; stop_reason = str(exc); break
                after = dict(client.request_metrics()) if hasattr(client, "request_metrics") else {}
                recs = session.records[mark:]
                results[symbol] = {"raw": raw, "adjusted": adj, "output1_reference": output1_reference(recs),
                                   "retries": after.get("retries", 0) - before.get("retries", 0),
                                   "rate_limit_errors": after.get("rate_limit_errors", 0) - before.get("rate_limit_errors", 0)}
                store.write(f"kis_raw/{symbol}.json", {"symbol": symbol, "requests": recs})
        finally:
            meta["kis_query_finished_at_kst"] = iso(now())
            if client_factory is None:
                client.close(); session.close()
    meta["metrics"] = client.request_metrics() if hasattr(client, "request_metrics") else {}
    meta["token_requests_seen"] = sum(1 for r in session.records if r.get("path") == "token")
    meta.update(completed_symbols=len(results), deferred_symbols=deferred, stop_reason=stop_reason,
                finished_at_kst=iso(now()))
    store.write("kis_observations.json", results)
    comparison = compare_all(sat_dir, results, targets, trade_date)
    store.write("comparison.json", comparison)
    meta["comparison"] = comparison["summary"]
    meta["status"] = monday_result_status(deferred, stop_reason, meta["comparison"])
    store.write("monday_summary.json", meta)
    store.write("report.md", render_report(sat_dir, out_dir, meta).encode("utf-8"))
    store.checksums()
    print(json.dumps({k: meta[k] for k in ("status", "metrics", "comparison")}, ensure_ascii=False, default=str, indent=1))
    return {"complete": 0, "complete_with_unverified_symbols": 0,
            "complete_with_symbol_failures": 9}.get(meta["status"], 8)


# ───────────────────────── 비교 ─────────────────────────
def _d(value) -> Decimal | None:
    text = str(value if value is not None else "").replace(",", "").strip()
    try:
        return Decimal(text) if text not in ("", "-") else None
    except Exception:
        return None


def compare_symbol(krx: dict | None, raw: dict, adj: dict, ref: dict | None, trade_date: date) -> dict:
    out = {"krx": "ok" if krx else "missing", "kis_raw": raw.get("status"), "kis_adj": adj.get("status")}
    if raw.get("status") == "ok" and adj.get("status") == "ok":
        diffs = {k: [raw.get(k), adj.get(k)] for k in OHLCV if _d(raw.get(k)) != _d(adj.get(k))}
        out["raw_vs_adj_diff"] = diffs
        rc, ac = _d(raw.get("close")), _d(adj.get("close"))
        out["adj_ratio_close"] = str((ac / rc).quantize(Decimal("0.000001"))) if rc and ac else None
        rv, av = _d(raw.get("volume")), _d(adj.get("volume"))
        out["adj_ratio_volume"] = str((av / rv).quantize(Decimal("0.000001"))) if rv and av else None
    if not krx:
        out.update(category="unverified_no_krx", verification_status="unverified_no_krx")
        return out
    if raw.get("status") != "ok":
        out["category"] = "kis_raw_unavailable"
        return out
    fields = {}
    for k in OHLCV:
        kv, xv = _d(raw.get(k)), _d(krx.get(k))
        fields[k] = {"match": kv == xv, "kis": raw.get(k), "krx": krx.get(k)}
    fields["trade_value"] = {"match": _d(raw.get("trade_value")) == _d(krx.get("trade_value")),
                             "kis": raw.get("trade_value"), "krx": krx.get("trade_value")}
    fields["trade_date"] = {"match": krx.get("bas_dd") == trade_date.strftime("%Y%m%d") == (raw.get("raw") or {}).get("stck_bsop_date")}
    if ref:
        ls = _d(ref.get("lstn_stcn")); mc = _d(ref.get("hts_avls")); kmc = _d(krx.get("market_cap"))
        fields["listed_shares_ref"] = {"match": ls == _d(krx.get("listed_shares")), "kis_output1": ref.get("lstn_stcn"), "krx": krx.get("listed_shares")}
        fields["market_cap_ref_100m"] = {"match": (mc is not None and kmc is not None and abs(mc - (kmc / Decimal(10**8))) <= 1),
                                         "kis_output1_100m": ref.get("hts_avls"), "krx": krx.get("market_cap")}
    out["fields"] = fields
    ohlcv_match = all(fields[k]["match"] for k in OHLCV) and fields["trade_date"]["match"]
    out["ohlcv_match"] = ohlcv_match
    if krx.get("zero_volume"):
        out["category"] = "C_zero_volume_match" if ohlcv_match else "C_zero_volume_representation"
        out["zero_volume_close_volume_match"] = fields["close"]["match"] and fields["volume"]["match"]
    else:
        out["category"] = "A_raw_match" if ohlcv_match else "D_traded_raw_mismatch"
    # 무거래 종목은 O/H/L 표현이 원래 달라서(KRX 0, KIS 종가) 종가·거래량만으로 판정
    b_fields = ("close", "volume") if krx.get("zero_volume") else OHLCV
    out["B_adjusted_differs_from_krx"] = (adj.get("status") == "ok" and any(_d(adj.get(k)) != _d(krx.get(k)) for k in b_fields))
    return out


def compare_all(sat_dir: Path, results: dict, targets: list[str], trade_date: date) -> dict:
    norm_path = sat_dir / "krx_normalized.json"
    krx_rows = {}
    if norm_path.exists():
        for r in json.loads(norm_path.read_text(encoding="utf-8"))["rows"]:
            if r.get("market") == "KOSPI":
                krx_rows[r["symbol"]] = r
    per = {s: compare_symbol(krx_rows.get(s), results[s]["raw"], results[s]["adjusted"], results[s].get("output1_reference"), trade_date)
           for s in targets if s in results}
    cats: dict[str, int] = {}
    for c in per.values():
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    both = [c for c in per.values() if "fields" in c]
    traded = [c for c in both if not c["category"].startswith("C_")]
    zero_volume = [c for c in both if c["category"].startswith("C_")]
    unverified = sorted(s for s, c in per.items() if c["category"] == "unverified_no_krx")
    comparable = set(targets) - set(unverified)
    rate = lambda xs, pred: (f"{sum(1 for x in xs if pred(x))}/{len(xs)}" if xs else "0/0")
    def kis_counts(key: str) -> dict[str, int]:
        counts = {"ok": 0, "error": 0, "no_row": 0, "other": 0, "not_queried": len(targets) - len(results)}
        for row in results.values():
            status = (row.get(key) or {}).get("status")
            counts[status if status in ("ok", "error", "no_row") else "other"] += 1
        return counts
    summary = {
        "krx_available": bool(krx_rows), "targets": len(targets), "capture_targets": len(targets),
        "kis_query_targets": len(targets), "kis_completed": len(results),
        "kis_raw_status": kis_counts("raw"), "kis_adjusted_status": kis_counts("adjusted"),
        "krx_comparison_targets": len(set(krx_rows) & set(targets)),
        "categories": cats,
        "ohlcv_exact_all": rate(both, lambda c: c["ohlcv_match"]),
        "krx_ohlcv_match": sum(1 for c in both if c["ohlcv_match"]),
        "krx_ohlcv_mismatch": sum(1 for c in both if not c["ohlcv_match"]),
        "close_match_all": rate(both, lambda c: c["fields"]["close"]["match"]),
        "volume_match_all": rate(both, lambda c: c["fields"]["volume"]["match"]),
        "trade_value_match_all": rate(both, lambda c: c["fields"]["trade_value"]["match"]),
        "ohlcv_exact_traded": rate(traded, lambda c: c["ohlcv_match"]),
        "zero_volume_count": len(zero_volume),
        "zero_volume_ohl_representation_diff": sum(1 for c in zero_volume if c["category"] == "C_zero_volume_representation"),
        "zero_volume_close_volume_match": rate(zero_volume, lambda c: c.get("zero_volume_close_volume_match")),
        "listed_shares_ref_match": rate([c for c in both if "listed_shares_ref" in c["fields"]], lambda c: c["fields"]["listed_shares_ref"]["match"]),
        "market_cap_ref_match_100m": rate([c for c in both if "market_cap_ref_100m" in c["fields"]], lambda c: c["fields"]["market_cap_ref_100m"]["match"]),
        "kis_raw_missing": sorted(s for s, c in per.items() if c["kis_raw"] != "ok"),
        "kis_adj_missing": sorted(s for s, c in per.items() if c["kis_adj"] != "ok"),
        "kis_raw_blocking": sorted(s for s, c in per.items()
                                   if c["kis_raw"] != "ok" and (s in comparable or c["kis_raw"] != "no_row")),
        "kis_adj_blocking": sorted(s for s, c in per.items()
                                   if c["kis_adj"] != "ok" and (s in comparable or c["kis_adj"] != "no_row")),
        "kis_raw_vs_adj_differs": sorted(s for s, c in per.items() if c.get("raw_vs_adj_diff")),
        "B_adjusted_differs_from_krx": sorted(s for s, c in per.items() if c.get("B_adjusted_differs_from_krx")),
        "D_traded_raw_mismatch": sorted(s for s, c in per.items() if c["category"] == "D_traded_raw_mismatch"),
        "unverified_no_krx": unverified,
        "symbols_with_retries": sorted(s for s, r in results.items() if r.get("retries")),
    }
    return {"summary": summary, "per_symbol": per}


def monday_result_status(deferred: list[str], stop_reason: str | None, comparison: dict) -> str:
    if deferred or stop_reason:
        return "partial"
    if comparison.get("kis_raw_blocking") or comparison.get("kis_adj_blocking"):
        return "complete_with_symbol_failures"
    if comparison.get("unverified_no_krx"):
        return "complete_with_unverified_symbols"
    return "complete"


def render_report(sat_dir: Path, mon_dir: Path, mon_meta: dict | None) -> str:
    sat = json.loads((sat_dir / "saturday_summary.json").read_text(encoding="utf-8")) if (sat_dir / "saturday_summary.json").exists() else {}
    lines = ["# 금요일 데이터 최종 실증 — 자동 요약", "",
             f"- 거래일: {TRADE_DATE.isoformat()} · 생성: {iso(now_kst())}", ""]
    lines += ["## 토요일 KRX", "```json", json.dumps({k: sat.get(k) for k in ("status", "started_at_kst", "finished_at_kst", "capture", "krx_request", "completeness", "fundamentals", "fundamentals_null_reasons")}, ensure_ascii=False, indent=1, default=str)[:12000], "```", ""]
    if mon_meta:
        lines += ["## 월요일 KIS", "```json", json.dumps({k: mon_meta.get(k) for k in ("status", "started_at_kst", "finished_at_kst", "delayed_recovery", "kis_query_started_at_kst", "kis_query_finished_at_kst", "targets", "plan", "preflight", "client", "metrics", "token_requests_seen", "completed_symbols", "stop_reason", "comparison")}, ensure_ascii=False, indent=1, default=str)[:16000], "```"]
    return "\n".join(lines) + "\n"


# ───────────────────────── CLI ─────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("saturday-krx", "saturday-krx-recovery", "monday-kis",
                                             "monday-kis-delayed-recovery", "report"))
    args = parser.parse_args(argv)
    load_env()
    sat_dir, mon_dir = OUT_ROOT / SAT_DIRNAME, OUT_ROOT / MON_DIRNAME
    print(f"[{iso(now_kst())}] {args.command} 시작 (trade_date={TRADE_DATE})", flush=True)
    if args.command == "saturday-krx":
        return run_saturday(sat_dir)
    if args.command == "saturday-krx-recovery":
        return run_saturday(sat_dir, recovery=True, max_attempts=1)
    if args.command == "monday-kis":
        return run_monday(mon_dir, sat_dir)
    if args.command == "monday-kis-delayed-recovery":
        return run_monday(mon_dir, sat_dir, delayed_recovery=True)
    # report: 파일만 읽어 다시 비교 (API 호출 없음). 결과는 새 이름으로 저장
    obs_path = mon_dir / "kis_observations.json"
    if not obs_path.exists():
        print("월요일 결과가 아직 없습니다."); return 1
    results = json.loads(obs_path.read_text(encoding="utf-8"))
    targets = json.loads((sat_dir / "capture_targets.json").read_text(encoding="utf-8"))["target_symbols"]
    comparison = compare_all(sat_dir, results, targets, TRADE_DATE)
    stamp = now_kst().strftime("%Y%m%dT%H%M%S")
    Store(mon_dir).write(f"report_rerun_{stamp}/comparison.json", comparison)
    print(json.dumps(comparison["summary"], ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
