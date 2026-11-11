"""AI 업데이트 매일 실행 (2026-11-11). 대상: AI가 켜진 일반 메모의 active 항목 (공용 DB, --allow-shared-write).

    PYTHONPATH=backend python -m pipelines.updates.daily --allow-shared-write    # 타이머가 부르는 명령 (06:30)
    PYTHONPATH=backend python -m pipelines.updates.daily                         # 로컬 테스트 DB 리허설 (TEST_DATABASE_URL)

- 중복 실행 방지: Postgres advisory lock (daily.lock_key). 잠금을 못 잡으면 status=locked로 끝낸다(종료 코드 0).
- 하루 비용 한도: usage_log.jsonl에서 오늘(한국 날짜) job=daily 실행 비용을 더해, 남은 금액을 experiment --max-usd로 준다.
  한도에 닿으면 남은 항목은 건너뛰고(확인 시각 그대로) 다음 실행에서 처리한다. 남은 금액이 없으면 실행하지 않는다(skipped_budget).
- 실패 알림: logs/updates_daily/latest.json(마지막 실행)과 logs/updates_daily/<run_id>.json, 표준 오류 로그. 실패면 종료 코드 1.
- 빠진 날: 타이머 Persistent=true로 켜질 때 한 번 돌고, 새 자료 기준이 '마지막 확인 하루 전부터·최대 14일'이라 그 사이 자료를 이어 받는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
LOG_DIR = "logs/updates_daily"


def spent_today(log_path: Path, today: str) -> float:
    """오늘(한국 날짜) job=daily 실행의 LLM 비용 합."""
    if not log_path.exists():
        return 0.0
    total = 0.0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("job") == "daily" and str(r.get("run_at", ""))[:10] == today:
            total += (r.get("total") or {}).get("usd") or 0.0
    return total


def last_daily_since(log_path: Path, started_at: str) -> dict | None:
    """이번 매일 실행이 남긴 usage_log 줄 (started_at 이후의 마지막 job=daily 줄)."""
    if not log_path.exists():
        return None
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            r = json.loads(line)
            if r.get("job") == "daily" and str(r.get("run_at", "")) >= started_at:
                return r
    return None


def write_status(log_dir: Path, status: dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(status, ensure_ascii=False, indent=1, default=str)
    (log_dir / f"{status['started_at'][:19].replace(':', '').replace('-', '')}.json").write_text(text, encoding="utf-8")
    tmp = log_dir / "latest.json.tmp"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, log_dir / "latest.json")


def lock_connection(shared: bool):
    """advisory lock을 잡을 연결 (공용 DB는 읽기 계정으로 충분, 테스트 DB는 TEST_DATABASE_URL)."""
    import psycopg

    from ..common.db import get_read_dsn
    from .db_store import check_test_target
    if shared:
        return psycopg.connect(get_read_dsn(), autocommit=True)
    dsn = os.environ.get("TEST_DATABASE_URL", "")
    check_test_target(dsn)
    return psycopg.connect(dsn, autocommit=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 업데이트 매일 실행 (잠금·하루 비용 한도·상태 파일)")
    ap.add_argument("--allow-shared-write", action="store_true", help="공용 DB에 쓴다 (없으면 로컬 테스트 DB 리허설)")
    ap.add_argument("--max-usd-per-day", type=float, help="하루 비용 한도 (기본: 설정 daily.max_usd_per_day)")
    ap.add_argument("--symbols", default="ALL")
    ap.add_argument("--config", default="configs/updates.yaml")
    args = ap.parse_args(argv)

    from ..common.config import load_config, resolve_path
    from .usage import LOG_PATH

    cfg = (load_config(args.config).get("daily") or {})
    limit = args.max_usd_per_day if args.max_usd_per_day is not None else float(cfg.get("max_usd_per_day", 1.0))
    started = datetime.now(SEOUL)
    log_dir, usage_log = resolve_path(LOG_DIR), resolve_path(LOG_PATH)
    status = {"started_at": started.isoformat(timespec="seconds"), "shared": args.allow_shared_write,
              "symbols": args.symbols, "max_usd_per_day": limit, "status": "running"}
    lock = None
    try:
        lock = lock_connection(args.allow_shared_write)
        key = int(cfg.get("lock_key", 581094101))
        if not lock.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[0]:
            status.update(status="locked", detail="다른 매일 실행이 돌고 있어 건너뜀")
            print(status["detail"])
            return 0
        spent = spent_today(usage_log, started.date().isoformat())
        remaining = round(limit - spent, 4)
        status.update(spent_before=round(spent, 4), remaining=remaining)
        if remaining <= 0:
            status.update(status="skipped_budget", detail=f"오늘 쓴 비용 ${spent:.3f}이 한도 ${limit}에 닿음")
            print(status["detail"])
            return 0
        from .experiment import main as experiment_main
        argv2 = ["--llm", "openai", "--store", "db", "--symbols", args.symbols, "--max-usd", str(remaining), "--job", "daily"]
        if args.allow_shared_write:
            argv2.append("--allow-shared-write")
        code = experiment_main(argv2)
        usage = last_daily_since(usage_log, status["started_at"]) or {}
        status.update(status="success" if code == 0 else "failed", exit_code=code, run_dir=usage.get("run_dir"),
                      run_id=usage.get("run_id"), items=usage.get("items"), cards=usage.get("cards"),
                      usd=(usage.get("total") or {}).get("usd"), budget_stopped=usage.get("budget_stopped"),
                      skipped_items=usage.get("skipped_items"))
        if usage.get("budget_stopped"):
            status["status"] = "budget_stopped"
        return 0 if code == 0 else 1
    except (Exception, SystemExit) as exc:                      # 실패(experiment의 SystemExit 포함): 상태 파일·표준 오류, 종료 코드 1
        status.update(status="failed", error=f"{type(exc).__name__}: {str(exc)[:500]}", traceback=traceback.format_exc()[-4000:])
        print(f"매일 실행 실패: {status['error']}", file=sys.stderr)
        return 1
    finally:
        status["finished_at"] = datetime.now(SEOUL).isoformat(timespec="seconds")
        write_status(log_dir, status)
        if lock is not None:
            lock.close()                                        # 연결을 닫으면 advisory lock도 풀린다


if __name__ == "__main__":
    raise SystemExit(main())
