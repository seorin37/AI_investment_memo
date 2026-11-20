"""새 API의 조회 로직을 실제 스키마에서 읽기 전용 세션으로 한 번씩 돌려 본다 (쓰기 없음, 인증 없음).

실행 (backend 폴더, 공용 DB .env 를 쓰려면 --env-file):
    python -m pipelines.devtools.readonly_api_check --env-file ~/projects/AI_investment_memo/.env
    python -m pipelines.devtools.readonly_api_check --env-file ... --include-unpinned

--include-unpinned: 고정 메모가 하나도 없을 때, 고정 조건만 빼고 같은 쿼리·응답 변환을 확인한다.
개인 정보(제목·본문·이메일)는 출력하지 않고 키·개수·타입만 보여 준다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _shape(value):
    if isinstance(value, dict):
        return {k: type(v).__name__ for k, v in value.items()}
    return type(value).__name__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path)
    ap.add_argument("--include-unpinned", action="store_true")
    args = ap.parse_args(argv)
    if args.env_file:
        from dotenv import dotenv_values

        os.environ.update({k: v for k, v in dotenv_values(args.env_file).items() if v is not None})

    from sqlalchemy import text

    from app.board.repository import BoardRepository
    from app.board.service import BoardService
    from app.db import get_read_session

    failures = 0
    with get_read_session() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        users = [r[0] for r in db.execute(text("SELECT DISTINCT user_id FROM user_stocks WHERE deleted_at IS NULL"))]
        print(f"사용자 {len(users)}명")

        repo = BoardRepository(db)
        if args.include_unpinned:  # 같은 SQL 에서 고정 조건만 뺀다
            repo.list_pinned = lambda user_id: _without_pinned_filter(repo, user_id)  # type: ignore[method-assign]
        service = BoardService(repo, llm_factory=lambda: None)
        for uid in users:
            try:
                items = service.list_pinned(uid)
                positions = [(i["stock_code"], i["position"]) for i in items]
                print(f"  pinned{'(+고정 안 된 것)' if args.include_unpinned else ''}: {len(items)}건, "
                      f"(종목, position) = {positions[:10]}")
                if items:
                    print(f"    키: {sorted(items[0])}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  pinned 실패: {type(exc).__name__}: {exc}")
        db.rollback()

    # 홈 위젯·/updates·투자 기록 조회 (사용자마다 개수와 첫 항목 키만)
    from app.home.repository import HomeRepository
    from app.home.service import HomeService
    from app.updates.repository import UpdatesRepository
    from app.updates.service import UpdatesService

    checks = {
        "checklist-items": lambda db, uid: HomeService(HomeRepository(db)).list_checklist(uid),
        "price-conditions": lambda db, uid: HomeService(HomeRepository(db)).list_price_conditions(uid),
        "updates": lambda db, uid: UpdatesService(UpdatesRepository(db)).market_updates(uid),
    }
    try:
        from app.journal.repository import JournalRepository
        from app.journal.service import JournalService

        checks["journal"] = lambda db, uid: JournalService(JournalRepository(db)).list(uid)
    except ImportError:
        pass
    for name, run in checks.items():
        with get_read_session() as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            for uid in users:
                try:
                    items = run(db, uid)
                    print(f"  {name}: {len(items)}건" + (f", 키 {sorted(items[0])}" if items else ""))
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    print(f"  {name} 실패: {type(exc).__name__}: {exc}")
            db.rollback()

    failures += _explain_writes()
    return 1 if failures else 0


# 쓰기 SQL 은 실행하지 않고, 읽기 전용 트랜잭션에서 EXPLAIN 으로 문법·권한·컬럼만 확인한다.
def _explain_writes() -> int:
    import inspect
    import re

    import psycopg

    from app.db import write_database_url

    modules = []
    for path in ("app.home.repository", "app.journal.repository", "app.account.repository", "app.trash.repository"):
        try:
            modules.append(__import__(path, fromlist=["*"]))
        except ImportError:
            continue
    statements = []
    for module in modules:
        for block in re.findall(r'"""(.*?)"""', inspect.getsource(module), re.S):
            if re.match(r"\s*(INSERT|UPDATE|DELETE)\b", block) and "{" not in block:
                statements.append((module.__name__, block))
    params = {
        "user_id": -1, "memo_id": -1, "item_id": -1, "entry_id": -1, "checklist_id": -1, "symbol": "000000",
        "label": "x", "status": "paused", "title": "x", "body": "x", "layout": "{}", "pinned": False,
        "kind": "note", "entry_status": "draft",
    }
    failures = 0
    url = write_database_url().replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        conn.read_only = True
        for module, sql in statements:
            names = set(re.findall(r"(?<!:):(\w+)", sql))
            bound = re.sub(r"(?<!:):(\w+)", r"%(\1)s", sql)
            try:
                conn.execute("EXPLAIN " + bound, {n: params.get(n, "x") for n in names})
                print(f"  EXPLAIN ok  {module}: {' '.join(sql.split())[:60]}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                conn.rollback()
                print(f"  EXPLAIN 실패 {module}: {' '.join(sql.split())[:60]} → {type(exc).__name__}: {exc}")
        conn.rollback()
    return failures


def _without_pinned_filter(repo, user_id):
    from sqlalchemy import text

    import inspect
    import re

    src = inspect.getsource(type(repo).list_pinned)
    sql = re.search(r'f"""(.*?)"""', src, re.S).group(1).replace("{self._BOARD_ORDER}", repo._BOARD_ORDER)
    sql = sql.replace("AND ranked.is_pinned", "")
    rows = repo.db.execute(text(sql), {"user_id": user_id}).mappings().all()
    out = []
    for row in rows:
        item = dict(row)
        item["position"] = item.pop("board_position")
        item.pop("stock_added_at", None)
        out.append(item)
    return out


if __name__ == "__main__":
    sys.exit(main())
