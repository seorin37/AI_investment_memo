"""실행 한 번이 DB에 넣거나 바꾼 행만 지우거나 되돌린다 (2026-11-11). 실행 폴더의 db_rows.json(manifest)과 details.run_id로 찾는다.

    PYTHONPATH=backend python -m pipelines.updates.db_cleanup results/updates/run_<시각>            # 지울 행 수만 보여 준다
    PYTHONPATH=backend python -m pipelines.updates.db_cleanup results/updates/run_<시각> --execute  # 확인을 받고 실행
    (공용 DB에서 만든 실행이면 --allow-shared-write도 줘야 한다)

- tracking_updates: manifest의 id 중 details.run_id가 이 실행인 행만 지운다 (update_sources는 ON DELETE CASCADE로 함께).
- tracking_matches: 이번 실행이 새로 넣은 행은 지우고, 기존 행을 바꿨으면 바뀌기 전 판정(similarity·decision·decided_at)으로 되돌린다.
- tracking_items.last_checked_at: 지금 값이 이번 실행이 적은 값과 같을 때만 바뀌기 전 값으로 되돌린다 (그 뒤 다른 실행이 갱신했으면 그대로).
- --execute면 지울·되돌릴 행 수를 보여 주고 "yes"를 입력받는다 (--yes로 건너뛸 수 있다). 한 트랜잭션.
- 쓰기 대상 확인은 db_store.check_test_target·check_conn과 같다 (로컬 테스트 DB, 공용 DB는 --allow-shared-write일 때만).
- 이 파일은 ReadOnlyGuardTest의 두 번째 예외다: DELETE·UPDATE만 쓰고 스키마 변경 SQL은 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

COUNT_UPDATES = """SELECT count(*) FROM tracking_updates WHERE id = ANY(%(ids)s) AND details->>'run_id' = %(run)s"""
COUNT_SOURCES = """SELECT count(*) FROM update_sources us JOIN tracking_updates tu ON tu.id = us.update_id
WHERE tu.id = ANY(%(ids)s) AND tu.details->>'run_id' = %(run)s"""
DELETE_UPDATES = """DELETE FROM tracking_updates WHERE id = ANY(%(ids)s) AND details->>'run_id' = %(run)s"""
DELETE_MATCHES = "DELETE FROM tracking_matches WHERE id = ANY(%(ids)s)"
RESTORE_MATCH = """UPDATE tracking_matches SET similarity = %(similarity)s, decision = %(decision)s, decided_at = %(decided_at)s
WHERE id = %(id)s"""
RESTORE_CHECKED = """UPDATE tracking_items SET last_checked_at = %(prev)s WHERE id = %(item_id)s AND last_checked_at = %(set)s"""
COUNT_CHECKED = """SELECT count(*) FROM tracking_items t JOIN unnest(%(items)s::bigint[], %(sets)s::timestamptz[]) AS k(i, s)
ON t.id = k.i AND t.last_checked_at = k.s"""


def load_manifest(run_dir: Path) -> dict:
    path = run_dir / "db_rows.json"
    if not path.is_file():
        raise SystemExit(f"{path}이 없습니다 (--store db로 돈 실행 폴더인지 확인하세요)")
    return json.loads(path.read_text(encoding="utf-8"))


def plan(conn, m: dict) -> dict:
    ids, run = m["tracking_updates"], m["run_id"]
    lc = m["last_checked"]
    return {"tracking_updates": conn.execute(COUNT_UPDATES, {"ids": ids, "run": run}).fetchone()[0],
            "update_sources(함께 지워짐)": conn.execute(COUNT_SOURCES, {"ids": ids, "run": run}).fetchone()[0],
            "tracking_matches 지움": conn.execute("SELECT count(*) FROM tracking_matches WHERE id = ANY(%(ids)s)",
                                                {"ids": m["tracking_matches_inserted"]}).fetchone()[0],
            "tracking_matches 되돌림": len(m["tracking_matches_updated"]),
            "last_checked_at 되돌림": conn.execute(COUNT_CHECKED, {
                "items": [r["item_id"] for r in lc],
                "sets": [datetime.fromisoformat(r["set"]) for r in lc]}).fetchone()[0] if lc else 0}


def execute(conn, m: dict) -> None:
    conn.execute(DELETE_UPDATES, {"ids": m["tracking_updates"], "run": m["run_id"]})
    conn.execute(DELETE_MATCHES, {"ids": m["tracking_matches_inserted"]})
    for r in m["tracking_matches_updated"]:
        conn.execute(RESTORE_MATCH, r)
    for r in m["last_checked"]:
        conn.execute(RESTORE_CHECKED, {"item_id": r["item_id"], "prev": r["prev"], "set": datetime.fromisoformat(r["set"])})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실행 한 번이 DB에 쓴 행만 지우기·되돌리기 (기본은 행 수만 보기)")
    ap.add_argument("run_dir")
    ap.add_argument("--execute", action="store_true", help="실제로 지운다 (행 수를 보여 주고 yes를 입력받는다)")
    ap.add_argument("--yes", action="store_true", help="--execute의 확인 입력을 건너뛴다 (이미 행 수를 확인했을 때만)")
    ap.add_argument("--allow-shared-write", action="store_true", help="공용 DB에서 만든 실행을 정리할 때")
    args = ap.parse_args(argv)

    import psycopg

    from .db_store import check_conn, check_test_target, finish, shared_write_dsn

    m = load_manifest(Path(args.run_dir))
    shared = args.allow_shared_write
    dsn = shared_write_dsn() if shared else os.environ.get("TEST_DATABASE_URL", "")
    if not dsn:
        raise SystemExit("환경변수 TEST_DATABASE_URL이 없습니다")
    target = check_test_target(dsn, shared)
    if target != m["target"]:
        raise SystemExit(f"이 실행은 {m['target']}에 썼습니다. 지금 연결 대상은 {target}입니다")
    conn = psycopg.connect(dsn)
    check_conn(conn, shared)
    counts = plan(conn, m)
    print(f"대상 {target} · run_id {m['run_id']}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    if not args.execute:
        conn.rollback()
        conn.close()
        print("행 수만 봤습니다. 지우려면 --execute")
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            conn.close()
            raise SystemExit("확인 입력을 받을 수 없습니다 (행 수를 확인했으면 --yes)")
        if input("위 행을 지우거나 되돌릴까요? yes를 입력하세요: ").strip() != "yes":
            conn.close()
            print("취소했습니다")
            return 1
    execute(conn, m)
    finish(conn, shared)
    print("정리했습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
