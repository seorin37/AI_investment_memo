"""크레딧 관리자 명령 (결제 연동 전 테스트용). 쓰기 대상은 로컬 테스트 DB만, 공용 DB는 --allow-shared-write일 때만.

    PYTHONPATH=backend python -m app.credits.admin usage --user 26
    PYTHONPATH=backend python -m app.credits.admin purchase --user 26 --amount 50 --ref test-001
"""

from __future__ import annotations

import argparse
import json
import os


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="크레딧 사용량 보기·산 크레딧 넣기")
    ap.add_argument("mode", choices=["usage", "purchase"])
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--amount", type=int, default=0)
    ap.add_argument("--ref", help="결제번호 (같은 번호는 한 번만 들어간다)")
    ap.add_argument("--allow-shared-write", action="store_true")
    args = ap.parse_args(argv)
    from . import ledger
    from .daily import _engine
    dsn = os.environ.get("DATABASE_URL" if args.allow_shared_write else "TEST_DATABASE_URL", "")
    engine = _engine(dsn, args.allow_shared_write)
    try:
        with engine.begin() as db:
            if args.mode == "purchase":
                if args.amount <= 0 or not args.ref:
                    raise SystemExit("--amount(>0)와 --ref가 필요합니다")
                gid = ledger.grant_purchase(db, args.user, args.amount, args.ref)
                print("넣음" if gid else "이미 있는 결제번호라 건너뜀", gid)
            print(json.dumps(ledger.usage(db, args.user).to_dict(), ensure_ascii=False))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
