"""DB가 연결을 받을 때까지 기다린다. systemd 유닛의 ExecStartPre용.

  python -m backend.pipelines.common.wait_db --timeout 600

- 접속 정보는 .env(DATABASE_URL 또는 POSTGRES_*)에서 읽는다. 수집기와 같은 대상을 본다.
- 재부팅 직후 PostgreSQL이 "the database system is starting up"을 돌려주는 동안에는 접속 + SELECT 1이
  성공할 때까지 --interval초마다 다시 시도한다.
- 종료 코드: 0 준비됨, 1 접속 정보 없음, 2 --timeout 안에 준비되지 않음
  (Restart=always 서비스는 RestartSec 뒤 다시 시작하고, timer의 oneshot은 그 회차만 실패한다).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from .db import get_dsn, load_env

log = logging.getLogger("wait_db")


def wait_for_db(dsn: str, timeout: float, interval: float = 5.0, connect=None,
                sleep=time.sleep, clock=time.monotonic) -> bool:
    """dsn에 접속해 SELECT 1이 될 때까지 기다린다. timeout초 안에 되면 True."""
    if connect is None:
        import psycopg

        def connect():
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                conn.execute("SELECT 1")

    deadline = clock() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            connect()
        except Exception as exc:  # OperationalError(시작 중·접속 거부) 등
            left = deadline - clock()
            if left <= 0:
                log.error("DB가 %g초 안에 준비되지 않았습니다 (%d회 시도): %s", timeout, attempt, exc)
                return False
            log.info("DB 대기 중 (%d회째): %s", attempt, str(exc).strip().splitlines()[0][:200])
            sleep(min(interval, left))
            continue
        if attempt > 1:
            log.info("DB 준비됨 (%d회째 시도)", attempt)
        return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DB가 연결을 받을 때까지 기다린다 (systemd ExecStartPre용)")
    ap.add_argument("--timeout", type=float, default=600, help="최대 대기 초 (기본 600)")
    ap.add_argument("--interval", type=float, default=5, help="재시도 간격 초 (기본 5)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
    return 0 if wait_for_db(dsn, args.timeout, args.interval) else 2


if __name__ == "__main__":
    sys.exit(main())
