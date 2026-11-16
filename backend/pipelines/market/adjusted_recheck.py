"""후보 종목만 KIS 수정 일봉을 짧은 구간으로 다시 받아 DB와 비교한다 (DB 쓰기 없음).

- 기존 KisClient(FHKST03010100, FID_ORG_ADJ_PRC=0)·fetch_daily_range·normalize_daily_row를 그대로 쓴다.
  요청 간격·재시도·토큰 캐시는 KisClient 정책을 따른다.
- BudgetedClient가 요청 상한·허용 종목·수정주가 전용을 강제하고 모든 응답 원본을 남긴다.
- 이전에 받은 응답(같은 구간을 덮고 max_age 안)은 다시 요청하지 않는다.
- 결과 상태: HISTORY_RESYNC_CANDIDATE · SOURCE_DISCONTINUITY · NO_ACTION · REVIEW_REQUIRED.
  상태는 state 파일에 증거 키와 함께 남겨, 같은 증거로는 다시 요청하지 않는다(특히 SOURCE_DISCONTINUITY).
- KIS 수정주가를 다시 계산하거나 보정하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Iterator

from pipelines.common.file_lock import file_lock
from pipelines.market import adjusted_history_diagnostics as diag
from pipelines.market.corporate_actions import (
    HISTORY_RESYNC_CANDIDATE,
    NO_ACTION,
    REVIEW_REQUIRED,
    SOURCE_DISCONTINUITY,
)
from pipelines.market.kis import normalize_daily_row

KST = timezone(timedelta(hours=9))
STATE_SCHEMA_VERSION = 1
PAGE_SIZE = 100
# 기존 타이머: finalize 화~금 08:00, morning 매일 09:00, capture 월~금 20:00 (+ 옛 evening 18:30 코드 경로)
DEFAULT_BLACKOUTS = ((time(7, 30), time(9, 45)), (time(18, 15), time(21, 30)))
DISCONTINUITY_REASONS = ("adjusted_only", "unadjusted_raw_break")
MAX_ERROR_ATTEMPTS = 3
ERROR_RETRY_HOURS = 6


class RequestBudgetExceeded(RuntimeError):
    pass


class RecheckNotAllowed(RuntimeError):
    pass


# ---------------------------------------------------------------- 요청 통제


class BudgetedClient:
    """KisClient를 감싸 요청 수·종목·수정주가 전용을 강제하고 응답 원본을 기록한다."""

    def __init__(self, client, *, max_requests: int, allowed_symbols: Iterable[str],
                 clock: Callable[[], datetime] = lambda: datetime.now(KST)) -> None:
        if max_requests < 0:
            raise ValueError("요청 상한은 0 이상이어야 합니다.")
        self.client = client
        self.max_requests = max_requests
        self.allowed = set(allowed_symbols)
        self.clock = clock
        self.used = 0
        self.log: list[dict] = []

    def daily_page(self, symbol: str, start_date: date, end_date: date, *, adjusted: bool) -> list[dict]:
        if not adjusted:
            raise RecheckNotAllowed("재조회는 수정주가(FID_ORG_ADJ_PRC=0)만 요청합니다.")
        if symbol not in self.allowed:
            raise RecheckNotAllowed(f"허용되지 않은 종목 요청: {symbol}")
        if self.used >= self.max_requests:
            raise RequestBudgetExceeded(f"KIS 요청 상한 {self.max_requests}건에 도달했습니다.")
        self.used += 1
        requested = self.clock()
        page = self.client.daily_page(symbol, start_date, end_date, adjusted=True)
        self.log.append({
            "symbol": symbol,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_ORG_ADJ_PRC": "0",
            "requested_at_kst": requested.isoformat(),
            "received_at_kst": self.clock().isoformat(),
            "rows_returned": len(page),
            "output2": page,
        })
        return page


def in_blackout(moment: datetime, blackouts=DEFAULT_BLACKOUTS) -> bool:
    local = moment.astimezone(KST).time()
    return any(start <= local <= end for start, end in blackouts)


@contextmanager
def market_lock(conn, key: int) -> Iterator[bool]:
    """일일 갱신과 같은 PostgreSQL advisory lock (읽기 전용 연결에서도 잡힌다)."""
    acquired = bool(conn.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[0])
    try:
        yield acquired
    finally:
        if acquired:
            conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
        conn.rollback()


# ---------------------------------------------------------------- 이전 응답 재사용


@dataclass
class CachedPage:
    symbol: str
    start: date
    end: date
    fetched_at: datetime
    output2: list[dict]
    source: str

    def covers(self, symbol: str, start: date, end: date) -> bool:
        if symbol != self.symbol or not (self.start <= start and end <= self.end):
            return False
        dates = [r.get("stck_bsop_date") for r in self.output2 if r.get("stck_bsop_date")]
        # 한 페이지(100행)가 꽉 찼고 시작일까지 내려가지 않았으면 잘린 응답이라 믿지 않는다
        if len(self.output2) >= PAGE_SIZE and dates and min(dates) > self.start.strftime("%Y%m%d"):
            return False
        return True


def load_cached_pages(paths: Iterable[Path]) -> list[CachedPage]:
    """기존 재조회 원본 파일(kis_raw_responses.json 형식: requests[])을 읽는다."""
    pages: list[CachedPage] = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for req in payload.get("requests", []):
            if req.get("error") or req.get("FID_ORG_ADJ_PRC", "0") != "0":
                continue
            pages.append(CachedPage(
                symbol=req["symbol"],
                start=datetime.strptime(req["FID_INPUT_DATE_1"], "%Y%m%d").date(),
                end=datetime.strptime(req["FID_INPUT_DATE_2"], "%Y%m%d").date(),
                fetched_at=datetime.fromisoformat(req.get("received_at_kst") or req["requested_at_kst"]),
                output2=req.get("output2") or [],
                source=str(path),
            ))
    return pages


def rows_from_pages(symbol: str, pages: list[list[dict]], start: date, end: date) -> tuple[list[dict], int, list[str]]:
    """원본 페이지 → 구간 안 정규화 행. 같은 날짜가 두 번 오면 중복으로 기록한다."""
    rows: dict[date, dict] = {}
    zero = 0
    duplicates: list[str] = []
    for page in pages:
        for raw in page:
            value = (raw.get("stck_bsop_date") or "").strip()
            if not value:
                continue
            day = datetime.strptime(value, "%Y%m%d").date()
            if not start <= day <= end:
                continue
            norm = normalize_daily_row(symbol, raw, adjusted=True)
            if norm is None:
                zero += 1
                continue
            if day in rows:
                duplicates.append(day.isoformat())
            rows[day] = norm
    return [rows[d] for d in sorted(rows)], zero, duplicates


# ---------------------------------------------------------------- 비교·분류


def _f(v) -> float | None:
    return None if v is None else float(v)


def kis_series_discontinuities(db_rows: list[dict], adj_by_date: dict[date, dict], t: diag.Thresholds) -> list[dict]:
    """DB 원시 종가와 (주어진) 수정 종가로 만든 시계열에서 수정주가 단절을 찾는다."""
    rows = [
        diag.PriceRow(r["symbol"], r["trade_date"], r["raw_close"],
                      adj_by_date[r["trade_date"]]["close"] if r["trade_date"] in adj_by_date else None,
                      r["raw_volume"], None)
        for r in db_rows
    ]
    observations, _ = diag.build_observations(rows)
    out = []
    for f in diag.detect(observations, t):
        reasons = []
        if diag.ADJUSTED_ONLY in f.types:
            reasons.append("adjusted_only")
        if "unadjusted_raw_break" in f.resync_reasons:
            reasons.append("unadjusted_raw_break")
        if reasons:
            out.append({"trade_date": f.trade_date, "reasons": reasons, "prev_ratio": f.prev_ratio, "ratio": f.ratio,
                        "adj_return": f.adj_return, "raw_return": f.raw_return})
    return out


def compare_window(
    symbol: str,
    start: date,
    end: date,
    db_rows: list[dict],
    kis_rows: list[dict],
    *,
    zero_rows: int = 0,
    duplicates: list[str] | None = None,
    error: str | None = None,
    thresholds: diag.Thresholds = diag.Thresholds(),
) -> dict:
    """한 구간의 DB 대 KIS 비교와 상태 판정. db_rows: symbol, trade_date, raw_close, raw_volume, adj_*."""
    db_in = [r for r in db_rows if start <= r["trade_date"] <= end]
    kis = {r["trade_date"]: r for r in kis_rows if start <= r["trade_date"] <= end}
    db_dates = {r["trade_date"] for r in db_in}
    missing = sorted(d.isoformat() for d in db_dates - set(kis))
    extra = sorted(d.isoformat() for d in set(kis) - db_dates)
    rows, changed = [], []
    for r in db_in:
        k = kis.get(r["trade_date"])
        item = {
            "trade_date": r["trade_date"].isoformat(),
            "db_raw_close": _f(r["raw_close"]), "db_raw_volume": r["raw_volume"],
            "db_adj": {f: _f(r[f"adj_{f}"]) for f in ("open", "high", "low", "close")} | {"volume": r["adj_volume"]},
            "kis_adj": None if k is None else {f: _f(k[f]) for f in ("open", "high", "low", "close")} | {"volume": k["volume"]},
        }
        item["db_ratio"] = None if not r["raw_close"] else round(float(Decimal(r["adj_close"]) / Decimal(r["raw_close"])), 6)
        item["kis_ratio"] = None if k is None or not r["raw_close"] else round(float(Decimal(k["close"]) / Decimal(r["raw_close"])), 6)
        if k is not None:
            differs = [f for f in ("open", "high", "low", "close") if Decimal(k[f]) != Decimal(r[f"adj_{f}"])]
            if r["adj_volume"] is None or int(k["volume"]) != int(r["adj_volume"]):
                differs.append("volume")
            item["changed_fields"] = differs
            if differs:
                changed.append(item["trade_date"])
        rows.append(item)
    db_adj = {r["trade_date"]: {"close": r["adj_close"]} for r in db_in}
    kis_disc = kis_series_discontinuities(db_in, kis, thresholds)
    db_disc = kis_series_discontinuities(db_in, db_adj, thresholds)
    reasons: list[str] = []
    if error:
        status = REVIEW_REQUIRED
        reasons.append(f"KIS 응답 오류: {error}")
    elif not db_in:
        status = REVIEW_REQUIRED
        reasons.append("구간에 DB 행이 없음")
    elif missing or extra or zero_rows or duplicates:
        status = REVIEW_REQUIRED
        reasons.append(f"날짜 불일치 missing={missing[:5]} extra={extra[:5]} zero={zero_rows} dup={(duplicates or [])[:5]}")
    elif changed and not kis_disc:
        status = HISTORY_RESYNC_CANDIDATE
        reasons.append("DB와 현재 KIS 수정주가가 다르고 현재 KIS 이력은 구간 안에서 연속적 → 전체 이력 확인 필요")
    elif changed:
        status = REVIEW_REQUIRED
        reasons.append("DB와 다르지만 현재 KIS 이력에도 단절이 있음")
    elif kis_disc:
        status = SOURCE_DISCONTINUITY
        reasons.append("현재 KIS를 다시 받아도 같은 단절이 재현됨 (재수집으로 해결되지 않음)")
    else:
        status = NO_ACTION
        reasons.append("DB와 현재 KIS가 같고 단절 없음")
    kis_ratios = sorted({x["kis_ratio"] for x in rows if x["kis_ratio"] is not None})
    return {
        "symbol": symbol, "start": start.isoformat(), "end": end.isoformat(), "status": status, "reasons": reasons,
        "db_rows": len(db_in), "kis_rows": len(kis), "changed_dates": changed, "missing_in_kis": missing,
        "kis_only_dates": extra, "zero_ohlc_rows": zero_rows, "duplicate_dates": duplicates or [],
        "kis_discontinuities": kis_disc, "db_discontinuities": db_disc,
        "kis_ratio_levels": kis_ratios, "db_ratio_levels": sorted({x["db_ratio"] for x in rows if x["db_ratio"] is not None}),
        "rows": rows,
    }


STATUS_PRIORITY = {REVIEW_REQUIRED: 3, HISTORY_RESYNC_CANDIDATE: 2, SOURCE_DISCONTINUITY: 1, NO_ACTION: 0}


def combine_windows(results: list[dict]) -> str:
    """여러 구간 결과 → 종목 상태. 하나라도 검토 필요면 검토, 그다음 재동기화 후보 우선."""
    if not results:
        return REVIEW_REQUIRED
    return max((r["status"] for r in results), key=lambda s: STATUS_PRIORITY[s])


# ---------------------------------------------------------------- 상태·중복 억제


def evidence_key(item: dict) -> str:
    """같은 증거인지 판단하는 키: 비정보성 가격 탐지 날짜·판정 + 공시 묶음 최신 접수번호·지난 기준 날짜.

    정정공시가 새로 들어오거나 다음 기준 날짜(효력발생일 등)가 지나면 키가 바뀌어 다시 확인한다.
    """
    price = sorted(f"{f['trade_date']}:{f['assessment']}" for f in item.get("price_findings", []) if f.get("severity") != "info")
    disc = sorted(f"{c['group_id']}:{c['latest_rcept_no']}:{','.join(c.get('triggered_dates') or [])}"
                  for c in item.get("disclosure_candidates", []) if c.get("recheck_recommended"))
    return hashlib.sha256(json.dumps([price, disc]).encode()).hexdigest()[:16]


def empty_state() -> dict:
    return {"schema_version": STATE_SCHEMA_VERSION, "symbols": {}}


def load_state(path: Path) -> dict:
    if not path.exists():
        return empty_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("지원하지 않는 수정주가 관리 상태 파일입니다.")
    return payload


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path.with_suffix(".lock")):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, path)


def is_held(entry: dict | None) -> bool:
    return bool(entry and entry.get("hold"))


def set_hold(state: dict, symbol: str, *, reason: str, now: datetime, by: str) -> dict:
    """보류: 자동 재조회·재동기화 계획·적용 대상에서 뺀다. 해제는 release_hold(명시적 승인)로만."""
    if not reason.strip():
        raise ValueError("보류 사유가 필요합니다.")
    entry = state["symbols"].setdefault(symbol, {})
    entry["hold"] = {"reason": reason.strip(), "set_at": now.isoformat(), "set_by": by}
    entry.setdefault("hold_history", []).append({"action": "hold", **entry["hold"]})
    return entry


def release_hold(state: dict, symbol: str, *, approved_by: str, note: str, now: datetime) -> dict:
    entry = state["symbols"].get(symbol) or {}
    if not entry.get("hold"):
        raise ValueError(f"{symbol}은 보류 상태가 아닙니다.")
    if not approved_by.strip() or not note.strip():
        raise ValueError("보류 해제에는 승인자와 근거가 필요합니다.")
    entry.setdefault("hold_history", []).append(
        {"action": "release", "approved_by": approved_by.strip(), "note": note.strip(), "released_at": now.isoformat(),
         "previous": entry["hold"]})
    entry["hold"] = None
    return entry


def should_recheck(entry: dict | None, key: str, now: datetime,
                   finding_dates: Iterable[str] = (), has_disclosure_trigger: bool = False) -> tuple[bool, str]:
    """이미 같은 증거로 확인한 종목은 다시 요청하지 않는다. 오류는 제한된 횟수만 다시 시도한다.

    보류 종목은 어떤 증거가 와도 요청하지 않는다. SOURCE_DISCONTINUITY는 키가 달라져도
    이미 확인한 단절 날짜만 다시 잡혔고 새 공시 기준 날짜가 없으면 요청하지 않는다.
    """
    if is_held(entry):
        return False, "on_hold"
    if not entry or not entry.get("status"):
        return True, "new"
    if (entry.get("status") == SOURCE_DISCONTINUITY and entry.get("evidence_key") != key
            and not has_disclosure_trigger and set(finding_dates) <= set(entry.get("verified_dates") or [])):
        return False, "suppressed:same_source_discontinuity"
    if entry.get("evidence_key") != key:
        return True, "new_evidence"
    status = entry.get("status")
    if status in (SOURCE_DISCONTINUITY, NO_ACTION, HISTORY_RESYNC_CANDIDATE):
        return False, f"suppressed:{status}"
    if entry.get("error"):
        if entry.get("attempts", 0) >= MAX_ERROR_ATTEMPTS:
            return False, "error_attempts_exhausted"
        retry_after = entry.get("retry_after")
        if retry_after and now < datetime.fromisoformat(retry_after):
            return False, "retry_later"
        return True, "retry_after_error"
    return False, "suppressed:review_required"


# ---------------------------------------------------------------- 실행


@dataclass
class RecheckTarget:
    symbol: str
    windows: list[tuple[date, date]]
    evidence_key: str
    reason: str
    priority: int = 0
    finding_dates: list[str] = field(default_factory=list)


def select_targets(items: list[dict], state: dict, *, now: datetime, max_symbols: int,
                   latest_db_date: date | None = None, symbols: set[str] | None = None) -> tuple[list[RecheckTarget], list[dict]]:
    """감지 결과에서 재조회할 종목을 고른다 (정상 조정·종료 종목·억제 대상 제외)."""
    chosen: list[RecheckTarget] = []
    skipped: list[dict] = []
    ordered = sorted(
        (it for it in items if it.get("recheck_recommended")),
        key=lambda it: (-max([2 if f.get("severity") == "high" else 0 for f in it.get("price_findings", [])] + [1]),
                        it["symbol"]),
    )
    for it in ordered:
        if symbols is not None and it["symbol"] not in symbols:
            continue
        if it.get("terminal_status"):
            skipped.append({"symbol": it["symbol"], "reason": "terminal"})
            continue
        key = evidence_key(it)
        dates = sorted({f["trade_date"] for f in it.get("price_findings", []) if f.get("severity") != "info"})
        trigger = any(c.get("recheck_recommended") for c in it.get("disclosure_candidates", []))
        ok, why = should_recheck(state["symbols"].get(it["symbol"]), key, now, dates, trigger)
        if not ok:
            skipped.append({"symbol": it["symbol"], "reason": why})
            continue
        windows = []
        for a, b in it.get("recheck_windows") or []:
            lo, hi = date.fromisoformat(a), date.fromisoformat(b)
            if latest_db_date:
                hi = min(hi, latest_db_date)
            if lo <= hi:
                windows.append((lo, hi))
        if not windows:
            skipped.append({"symbol": it["symbol"], "reason": "no_window_yet"})
            continue
        if len(chosen) >= max_symbols:
            skipped.append({"symbol": it["symbol"], "reason": "max_symbols"})
            continue
        chosen.append(RecheckTarget(it["symbol"], windows, key, why, finding_dates=dates))
    return chosen, skipped


def recheck_symbol(
    target: RecheckTarget,
    *,
    load_db_rows: Callable[[str, date, date], list[dict]],
    fetch: Callable[[str, date, date], tuple[list[dict], int, list[str]]],
    cache: list[CachedPage],
    cache_max_age: timedelta,
    now: datetime,
    thresholds: diag.Thresholds = diag.Thresholds(),
) -> dict:
    """한 종목의 모든 구간 재조회·비교. fetch는 BudgetedClient를 쓰는 함수(상한 초과 시 예외)."""
    results = []
    error = None
    for start, end in target.windows:
        db_rows = load_db_rows(target.symbol, start, end)
        hit = next((p for p in cache if p.covers(target.symbol, start, end) and now - p.fetched_at <= cache_max_age), None)
        try:
            if hit:
                kis_rows, zero, dup = rows_from_pages(target.symbol, [hit.output2], start, end)
                origin = {"source": "cache", "path": hit.source, "fetched_at": hit.fetched_at.isoformat()}
            else:
                kis_rows, zero, dup = fetch(target.symbol, start, end)
                origin = {"source": "kis_api"}
            result = compare_window(target.symbol, start, end, db_rows, kis_rows, zero_rows=zero, duplicates=dup,
                                    thresholds=thresholds)
        except RequestBudgetExceeded:
            raise
        except Exception as exc:  # 응답 오류는 기록하고 다른 값으로 대체하지 않는다
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
            origin = {"source": "kis_api"}
            result = compare_window(target.symbol, start, end, db_rows, [], error=error, thresholds=thresholds)
        result["origin"] = origin
        results.append(result)
    status = combine_windows(results)
    return {"symbol": target.symbol, "status": status, "evidence_key": target.evidence_key, "error": error,
            "checked_at": now.isoformat(), "windows": results, "finding_dates": target.finding_dates,
            "next_step": {HISTORY_RESYNC_CANDIDATE: "resync-plan (전체 이력 조회는 승인 후)",
                          SOURCE_DISCONTINUITY: "재조회 반복 금지, 원천 단절로 기록",
                          NO_ACTION: "조치 없음",
                          REVIEW_REQUIRED: "수동 검토"}[status]}


def update_state(state: dict, result: dict, *, result_path: str, now: datetime) -> None:
    prev = state["symbols"].get(result["symbol"]) or {}
    attempts = prev.get("attempts", 0) + 1 if result["error"] else 0
    state["symbols"][result["symbol"]] = {
        # 보류·적용·복원 기록은 재조회 결과로 지우지 않는다
        **{k: prev[k] for k in ("hold", "hold_history", "applied_at", "applied_plan", "backup_path",
                                "restored_at", "restored_from", "pre_restore_backup") if k in prev},
        "status": result["status"],
        "verified_dates": sorted(set(result.get("finding_dates") or []) | set(prev.get("verified_dates") or []))
        if result["status"] == SOURCE_DISCONTINUITY else result.get("finding_dates") or [],
        "evidence_key": result["evidence_key"],
        "checked_at": result["checked_at"],
        "windows": [[w["start"], w["end"]] for w in result["windows"]],
        "result_path": result_path,
        "error": result["error"],
        "attempts": attempts,
        "retry_after": (now + timedelta(hours=ERROR_RETRY_HOURS)).isoformat() if result["error"] else None,
    }
