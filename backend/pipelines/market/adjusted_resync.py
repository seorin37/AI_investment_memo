"""수정주가 과거 이력 재동기화: 계획(dry-run)과 승인 후 적용.

- 계획: 재조회한 KIS 전체 수정 이력을 DB와 비교·검증해 plan을 만든다. DB에 쓰지 않는다.
- 적용: 승인된 plan(종목·sha256 확인)만, adjusted_prices_daily의 그 종목 기존 행만 UPDATE한다.
  한 트랜잭션 안에서 (1) 행 잠금·계획 당시 상태와 같은지 확인 (2) 원본 백업 파일 기록
  (3) UPDATE (4) 다시 읽어 검증 — 하나라도 실패하면 전체 롤백.
- prices_daily·stock_fundamentals_snapshot·공시 테이블·Capture/Finalize 파일은 건드리지 않는다.
  행을 새로 넣거나 지우지 않는다(날짜 집합이 다르면 계획 단계에서 막는다).
- KIS가 준 값을 그대로 쓴다. 단절을 이어 붙이거나 가격을 계산해 보정하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

from pipelines.market import adjusted_history_diagnostics as diag
from pipelines.market.adjusted_recheck import kis_series_discontinuities
from pipelines.market.kis import ADJUSTMENT_BASIS

KST = timezone(timedelta(hours=9))
PLAN_SCHEMA_VERSION = 1
TARGET_TABLE = "adjusted_prices_daily"
VOLUME_DEVIATION_BLOCK_SHARE = 0.05

# 이 모듈이 실행하는 SQL은 아래 셋뿐이다 (테스트가 대상 테이블을 확인한다)
SELECT_FOR_UPDATE_SQL = """
SELECT trade_date, open, high, low, close, volume, adjustment_basis, source, collected_at
FROM adjusted_prices_daily
WHERE symbol = :symbol
ORDER BY trade_date
FOR UPDATE
"""
UPDATE_SQL = """
UPDATE adjusted_prices_daily
SET open = :open, high = :high, low = :low, close = :close, volume = :volume, collected_at = :collected_at
WHERE symbol = :symbol AND trade_date = :trade_date AND source = 'KIS' AND adjustment_basis = :adjustment_basis
"""
# 복원: 백업에 있던 값·수집 시각으로 되돌린다 (source·adjustment_basis는 백업과 같아야 한다)
RESTORE_UPDATE_SQL = """
UPDATE adjusted_prices_daily
SET open = :open, high = :high, low = :low, close = :close, volume = :volume, collected_at = :collected_at
WHERE symbol = :symbol AND trade_date = :trade_date AND source = :source AND adjustment_basis = :adjustment_basis
"""
SQL_STATEMENTS = (SELECT_FOR_UPDATE_SQL, UPDATE_SQL, RESTORE_UPDATE_SQL)
BACKUP_SCHEMA_VERSION = 2


class PlanRejected(RuntimeError):
    pass


class StalePlan(RuntimeError):
    pass


class ApplyVerificationError(RuntimeError):
    pass


def _q(value, places: str = "0.01") -> str:
    return str(Decimal(str(value)).quantize(Decimal(places)))


def canonical_rows(rows: list[dict]) -> list[dict]:
    """비교·지문용 표준 형식: 가격은 소수 둘째 자리 문자열, 거래량은 정수."""
    return [
        {"trade_date": (r["trade_date"].isoformat() if isinstance(r["trade_date"], date) else str(r["trade_date"])),
         "open": _q(r["open"]), "high": _q(r["high"]), "low": _q(r["low"]), "close": _q(r["close"]),
         "volume": None if r.get("volume") is None else int(r["volume"])}
        for r in sorted(rows, key=lambda x: str(x["trade_date"]))
    ]


def fingerprint(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(canonical_rows(rows), sort_keys=True).encode()).hexdigest()


def plan_hash(plan: dict) -> str:
    body = {k: plan[k] for k in ("symbol", "old_fingerprint", "adjustment_basis", "new_rows", "kis_fetched_at")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _check(name: str, passed: bool, detail=None, *, blocking: bool = True) -> dict:
    return {"name": name, "passed": bool(passed), "blocking": blocking, "detail": detail}


def build_plan(
    symbol: str,
    db_rows: list[dict],
    kis_rows: list[dict],
    *,
    zero_rows: int,
    duplicates: list[str],
    kis_fetched_at: datetime,
    recheck_status: str | None,
    thresholds: diag.Thresholds = diag.Thresholds(),
) -> dict:
    """db_rows: trade_date, raw_close, raw_volume, adj_open..adj_close, adj_volume, adjustment_basis."""
    db = {r["trade_date"]: r for r in db_rows}
    kis = {r["trade_date"]: r for r in kis_rows}
    missing = sorted(d.isoformat() for d in set(db) - set(kis))
    extra = sorted(d.isoformat() for d in set(kis) - set(db))
    checks = [
        _check("recheck_status_is_resync_candidate", recheck_status == "HISTORY_RESYNC_CANDIDATE", recheck_status),
        _check("date_set_equal", not missing and not extra, {"missing_in_kis": missing[:20], "kis_only": extra[:20],
                                                              "missing_count": len(missing), "extra_count": len(extra)}),
        _check("no_duplicate_dates", not duplicates, duplicates[:20]),
        _check("no_zero_ohlc_rows", zero_rows == 0, zero_rows),
        _check("single_adjustment_basis", {r["adjustment_basis"] for r in db_rows} <= {ADJUSTMENT_BASIS},
               sorted({str(r["adjustment_basis"]) for r in db_rows})),
    ]
    bad_prices = [r["trade_date"].isoformat() for r in kis_rows
                  if not (0 < r["low"] <= min(r["open"], r["close"]) <= max(r["open"], r["close"]) <= r["high"])]
    checks.append(_check("kis_prices_valid", not bad_prices, bad_prices[:20]))
    # 수정 거래량: 원시 거래량 0과 수정 거래량 0이 같이 움직이는지, 조정비율과 맞는지
    zero_mismatch, deviations = [], []
    for day, r in db.items():
        k = kis.get(day)
        if k is None:
            continue
        raw_vol, adj_vol = int(r["raw_volume"] or 0), int(k["volume"])
        if (raw_vol == 0) != (adj_vol == 0):
            zero_mismatch.append(day.isoformat())
        elif raw_vol > 0:
            ratio = Decimal(k["close"]) / Decimal(r["raw_close"])
            expected = Decimal(raw_vol) / ratio
            if abs(Decimal(adj_vol) - expected) > max(Decimal(1), ratio, expected * Decimal("0.01")):
                deviations.append(day.isoformat())
    checks.append(_check("volume_zero_consistent", not zero_mismatch, zero_mismatch[:20]))
    share = len(deviations) / max(1, len(kis))
    checks.append(_check("volume_matches_ratio", share <= VOLUME_DEVIATION_BLOCK_SHARE,
                         {"deviating_rows": len(deviations), "share": round(share, 4), "sample": deviations[:10]}))
    ordered_db = sorted(db_rows, key=lambda r: r["trade_date"])
    disc = kis_series_discontinuities([{**r, "symbol": symbol} for r in ordered_db], kis, thresholds)
    checks.append(_check("kis_history_continuous", not disc, disc[:10]))

    changed = []
    for day in sorted(set(db) & set(kis)):
        r, k = db[day], kis[day]
        if any(Decimal(k[f]) != Decimal(r[f"adj_{f}"]) for f in ("open", "high", "low", "close")) or \
                (r["adj_volume"] is None or int(k["volume"]) != int(r["adj_volume"])):
            changed.append(day)
    ratio_levels = lambda source: _ratio_levels(ordered_db, source)
    blocking_failed = [c["name"] for c in checks if c["blocking"] and not c["passed"]]
    if blocking_failed:
        status = "blocked"
    elif not changed:
        status = "no_change"
    else:
        status = "ready"
    old_rows = [{"trade_date": r["trade_date"], "open": r["adj_open"], "high": r["adj_high"], "low": r["adj_low"],
                 "close": r["adj_close"], "volume": r["adj_volume"]} for r in ordered_db]
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "symbol": symbol,
        "status": status,
        "blocking_failures": blocking_failed,
        "checks": checks,
        "adjustment_basis": ADJUSTMENT_BASIS,
        "kis_fetched_at": kis_fetched_at.isoformat(),
        "row_count": len(db_rows),
        "date_range": [ordered_db[0]["trade_date"].isoformat(), ordered_db[-1]["trade_date"].isoformat()] if ordered_db else None,
        "changed_rows": len(changed),
        "changed_range": [changed[0].isoformat(), changed[-1].isoformat()] if changed else None,
        "ratio_levels_db": ratio_levels("db"),
        "ratio_levels_kis": _ratio_levels(ordered_db, "kis", kis),
        "diff_sample": [
            {"trade_date": d.isoformat(),
             "old": canonical_rows([{**db[d], "open": db[d]["adj_open"], "high": db[d]["adj_high"], "low": db[d]["adj_low"],
                                     "close": db[d]["adj_close"], "volume": db[d]["adj_volume"]}])[0],
             "new": canonical_rows([kis[d]])[0]}
            for d in (changed[:5] + changed[-5:] if len(changed) > 10 else changed)
        ],
        "old_fingerprint": fingerprint(old_rows),
        "new_rows": canonical_rows(kis_rows) if status == "ready" else [],
    }
    plan["plan_sha256"] = plan_hash(plan)
    return plan


def _ratio_levels(db_rows: list[dict], source: str, kis: dict | None = None) -> list[dict]:
    """조정비율(수정/원시) 구간 요약: 같은 비율이 이어진 구간."""
    levels: list[dict] = []
    for r in db_rows:
        adj = r["adj_close"] if source == "db" else (kis.get(r["trade_date"]) or {}).get("close")
        if adj is None or not r["raw_close"]:
            continue
        ratio = round(float(Decimal(adj) / Decimal(r["raw_close"])), 4)
        if levels and levels[-1]["ratio"] == ratio:
            levels[-1]["end"] = r["trade_date"].isoformat()
            levels[-1]["rows"] += 1
        else:
            levels.append({"ratio": ratio, "start": r["trade_date"].isoformat(), "end": r["trade_date"].isoformat(), "rows": 1})
    return levels


# ---------------------------------------------------------------- 적용


def validate_for_apply(plan: dict, *, symbol: str, confirm: str, now: datetime, max_age: timedelta) -> None:
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise PlanRejected("지원하지 않는 계획 파일입니다.")
    if plan.get("symbol") != symbol:
        raise PlanRejected(f"계획 종목({plan.get('symbol')})과 승인 종목({symbol})이 다릅니다.")
    if plan.get("status") != "ready":
        raise PlanRejected(f"적용할 수 없는 계획 상태: {plan.get('status')} {plan.get('blocking_failures')}")
    if plan_hash(plan) != plan.get("plan_sha256"):
        raise PlanRejected("계획 파일 내용이 만들어진 뒤 바뀌었습니다.")
    if confirm != plan["plan_sha256"]:
        raise PlanRejected("--confirm 값이 계획의 sha256과 다릅니다.")
    fetched = datetime.fromisoformat(plan["kis_fetched_at"])
    if now - fetched > max_age:
        raise PlanRejected(f"계획이 오래됐습니다 ({fetched.isoformat()}). 다시 resync-plan을 실행하세요.")
    if not plan.get("new_rows"):
        raise PlanRejected("갱신할 행이 없습니다.")


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def backup_rows(rows: list[dict]) -> list[dict]:
    """백업용 행: 표준 가격·거래량 + 복원에 필요한 source·adjustment_basis·collected_at."""
    ordered = sorted(rows, key=lambda x: str(x["trade_date"]))
    return [{**c, "adjustment_basis": r.get("adjustment_basis"), "source": r.get("source"),
             "collected_at": _iso(r.get("collected_at"))}
            for c, r in zip(canonical_rows(ordered), ordered)]


def _payload_sha256(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "payload_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_backup(backup_dir: Path, symbol: str, rows: list[dict], *, now: datetime, reason: str,
                 plan_sha256: str | None = None, expected_after: str | None = None) -> Path:
    """갱신 직전 원본을 파일로 남긴다. 무결성 해시를 넣고, 이미 있는 파일은 덮어쓰지 않는다."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    tag = (plan_sha256 or reason)[:12]
    path = backup_dir / f"{now.astimezone(KST):%Y%m%dT%H%M%S}_{symbol}_{tag}.json"
    brows = backup_rows(rows)
    payload = {
        "schema_version": BACKUP_SCHEMA_VERSION, "table": TARGET_TABLE, "symbol": symbol, "reason": reason,
        "plan_sha256": plan_sha256, "backed_up_at": now.isoformat(), "row_count": len(brows),
        "rows_fingerprint": fingerprint(brows),
        # 이 백업을 만든 갱신이 끝났을 때 DB가 가져야 할 지문 (복원 전 정합성 확인용)
        "expected_after_fingerprint": expected_after,
        "rows": brows,
    }
    payload["payload_sha256"] = _payload_sha256(payload)
    with path.open("x", encoding="utf-8") as handle:  # 이미 있으면 덮어쓰지 않는다
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def apply_plan(
    begin: Callable,
    plan: dict,
    *,
    symbol: str,
    confirm: str,
    backup_dir: Path,
    now: datetime,
    max_age: timedelta = timedelta(hours=24),
    text: Callable = None,
) -> dict:
    """begin(): 트랜잭션 컨텍스트(예: engine.begin). 예외가 나면 컨텍스트가 롤백한다."""
    if text is None:
        from sqlalchemy import text  # noqa: WPS433
    validate_for_apply(plan, symbol=symbol, confirm=confirm, now=now, max_age=max_age)
    new_rows = plan["new_rows"]
    collected_at = datetime.fromisoformat(plan["kis_fetched_at"])
    with begin() as conn:
        current = [dict(r) for r in conn.execute(text(SELECT_FOR_UPDATE_SQL), {"symbol": symbol}).mappings().all()]
        if fingerprint(current) != plan["old_fingerprint"]:
            raise StalePlan("계획 이후 DB 수정주가가 바뀌었습니다. 다시 resync-plan을 실행하세요.")
        if {str(r["trade_date"]) for r in current} != {r["trade_date"] for r in new_rows}:
            raise StalePlan("DB 날짜 집합이 계획과 다릅니다.")
        backup = write_backup(backup_dir, symbol, current, now=now, reason="resync-apply",
                              plan_sha256=plan["plan_sha256"], expected_after=fingerprint(new_rows))
        updated = 0
        for row in new_rows:
            result = conn.execute(text(UPDATE_SQL), {
                **row, "trade_date": date.fromisoformat(row["trade_date"]), "symbol": symbol,
                "collected_at": collected_at, "adjustment_basis": plan["adjustment_basis"],
            })
            if result.rowcount != 1:
                raise ApplyVerificationError(f"{row['trade_date']} 갱신 행 수가 1이 아닙니다: {result.rowcount}")
            updated += 1
        after = [dict(r) for r in conn.execute(text(SELECT_FOR_UPDATE_SQL), {"symbol": symbol}).mappings().all()]
        if canonical_rows(after) != new_rows:
            raise ApplyVerificationError("갱신 후 다시 읽은 값이 계획과 다릅니다.")
        if any(r.get("collected_at") is not None and not _same_instant(_iso(r["collected_at"]), collected_at.isoformat())
               for r in after):
            raise ApplyVerificationError("갱신 후 collected_at이 KIS 조회 시각과 다릅니다.")
        if len(after) != len(current):
            raise ApplyVerificationError("갱신 후 행 수가 바뀌었습니다.")
    return {"symbol": symbol, "updated_rows": updated, "backup_path": str(backup),
            "verified_in_transaction": True, "plan_sha256": plan["plan_sha256"]}


# ---------------------------------------------------------------- 백업 복원


class BackupInvalid(RuntimeError):
    pass


class RestoreRejected(RuntimeError):
    pass


def load_backup(path: Path) -> dict:
    """백업 파일을 읽고 무결성(파일 해시·행 지문·행 수·날짜 중복·대상 테이블)을 확인한다."""
    try:
        backup = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupInvalid(f"백업 파일을 읽을 수 없습니다: {path}") from exc
    if backup.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise BackupInvalid("지원하지 않는 백업 형식입니다.")
    if backup.get("table") != TARGET_TABLE:
        raise BackupInvalid(f"복원 대상 테이블이 {TARGET_TABLE}가 아닙니다: {backup.get('table')}")
    if _payload_sha256(backup) != backup.get("payload_sha256"):
        raise BackupInvalid("백업 파일 내용이 기록 뒤 바뀌었습니다 (payload_sha256 불일치).")
    rows = backup.get("rows") or []
    if len(rows) != backup.get("row_count") or not rows:
        raise BackupInvalid("백업 행 수가 메타데이터와 다릅니다.")
    if fingerprint(rows) != backup.get("rows_fingerprint"):
        raise BackupInvalid("백업 행 지문이 다릅니다.")
    dates = [r["trade_date"] for r in rows]
    if len(set(dates)) != len(dates):
        raise BackupInvalid("백업에 같은 날짜가 두 번 있습니다.")
    if any(not r.get("adjustment_basis") or not r.get("source") for r in rows):
        raise BackupInvalid("백업 행에 source·adjustment_basis가 없습니다.")
    return backup


def restore_token(backup: dict, current_fingerprint: str) -> str:
    """복원 승인 값: 이 백업과 '지금의 DB 상태'를 함께 묶는다. DB가 바뀌면 값도 바뀐다."""
    return hashlib.sha256(f"{backup['payload_sha256']}:{current_fingerprint}".encode()).hexdigest()


def plan_restore(backup: dict, current_rows: list[dict], *, symbol: str) -> dict:
    """복원 dry-run. DB에 쓰지 않는다. status: ready | already_restored | blocked."""
    reasons: list[str] = []
    if backup["symbol"] != symbol:
        reasons.append(f"백업 종목({backup['symbol']})과 요청 종목({symbol})이 다름")
    current_fp = fingerprint(current_rows)
    current_dates = {str(r["trade_date"]) for r in current_rows}
    backup_dates = {r["trade_date"] for r in backup["rows"]}
    if current_dates != backup_dates:
        reasons.append(f"날짜 집합이 다름: DB에만 {sorted(current_dates - backup_dates)[:5]}, "
                       f"백업에만 {sorted(backup_dates - current_dates)[:5]}")
    keys = {(r["trade_date"], r["source"], r["adjustment_basis"]) for r in backup["rows"]}
    cur_keys = {(str(r["trade_date"]), r.get("source"), r.get("adjustment_basis")) for r in current_rows}
    if current_dates == backup_dates and keys != cur_keys:
        reasons.append("source·adjustment_basis가 백업과 다른 행이 있음")
    already = current_fp == backup["rows_fingerprint"]
    expected = backup.get("expected_after_fingerprint")
    if not already and expected and current_fp != expected:
        reasons.append("현재 DB가 백업을 만든 갱신 직후 상태와 다름 (그 뒤 다른 변경이 있었음)")
    current_by_date = {str(r["trade_date"]): canonical_rows([r])[0] for r in current_rows}
    changed = [r["trade_date"] for r in backup["rows"]
               if current_by_date.get(r["trade_date"]) != {k: r[k] for k in ("trade_date", "open", "high", "low", "close", "volume")}]
    status = "blocked" if reasons else ("already_restored" if already else "ready")
    return {
        "symbol": symbol, "status": status, "reasons": reasons, "backup_symbol": backup["symbol"],
        "backup_plan_sha256": backup.get("plan_sha256"), "row_count": len(backup["rows"]),
        "rows_to_restore": len(changed), "changed_range": [changed[0], changed[-1]] if changed else None,
        "current_fingerprint": current_fp, "restore_sha256": restore_token(backup, current_fp),
    }


def apply_restore(
    begin: Callable,
    backup: dict,
    *,
    symbol: str,
    confirm: str,
    backup_dir: Path,
    now: datetime,
    text: Callable = None,
) -> dict:
    """백업 값으로 되돌린다. 한 트랜잭션: 잠금 → dry-run과 같은 상태인지(승인 값) 확인 → 현재 값 백업 →
    UPDATE(값·수집 시각) → 다시 읽어 백업과 같은지 확인. 실패하면 전체 롤백."""
    if text is None:
        from sqlalchemy import text  # noqa: WPS433
    with begin() as conn:
        current = [dict(r) for r in conn.execute(text(SELECT_FOR_UPDATE_SQL), {"symbol": symbol}).mappings().all()]
        check = plan_restore(backup, current, symbol=symbol)
        if check["status"] != "ready":
            raise RestoreRejected(f"복원할 수 없는 상태: {check['status']} {check['reasons']}")
        if confirm != check["restore_sha256"]:
            raise RestoreRejected("--confirm 값이 dry-run의 restore_sha256과 다릅니다 (DB가 바뀌었을 수 있음).")
        pre_restore = write_backup(backup_dir, symbol, current, now=now, reason="pre-restore",
                                   expected_after=backup["rows_fingerprint"])
        restored = 0
        for row in backup["rows"]:
            result = conn.execute(text(RESTORE_UPDATE_SQL), {
                "symbol": symbol, "trade_date": date.fromisoformat(row["trade_date"]),
                "open": row["open"], "high": row["high"], "low": row["low"], "close": row["close"],
                "volume": row["volume"], "source": row["source"], "adjustment_basis": row["adjustment_basis"],
                "collected_at": datetime.fromisoformat(row["collected_at"]) if row.get("collected_at") else None,
            })
            if result.rowcount != 1:
                raise ApplyVerificationError(f"{row['trade_date']} 복원 행 수가 1이 아닙니다: {result.rowcount}")
            restored += 1
        after = [dict(r) for r in conn.execute(text(SELECT_FOR_UPDATE_SQL), {"symbol": symbol}).mappings().all()]
        if fingerprint(after) != backup["rows_fingerprint"] or len(after) != len(current):
            raise ApplyVerificationError("복원 후 다시 읽은 값이 백업과 다릅니다.")
        stamps = {str(r["trade_date"]): _iso(r.get("collected_at")) for r in after}
        if any(_same_instant(stamps[r["trade_date"]], r.get("collected_at")) is False for r in backup["rows"]):
            raise ApplyVerificationError("복원 후 collected_at이 백업과 다릅니다.")
    return {"symbol": symbol, "restored_rows": restored, "pre_restore_backup": str(pre_restore),
            "verified_in_transaction": True, "backup_payload_sha256": backup["payload_sha256"]}


def _same_instant(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a == b
    return datetime.fromisoformat(a) == datetime.fromisoformat(b)
