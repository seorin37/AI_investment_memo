"""공용 DB 끝까지 확인 (2026-11-11, 사용자가 이번 확인에 한해 공용 DB 쓰기를 허용).

    PYTHONPATH=backend python -m pipelines.updates.shared_e2e_check --allow-shared-write

테스트 사용자 1명 · 종목 보드 4개 · 로그인 세션 1개 · 시범 메모 5개(AI 켜기)와 그로 인해 생기는 항목·카드만 만든다.
흐름: 서버(uvicorn, 포트 8000) → 테스트 사용자·세션 → API로 메모 저장(analysis) → memos·tracking_items → 매일 실행기 1회
→ tracking_updates·update_sources → timeline·ai-updates·summary API → 읽음 처리. 만든 행 id는 실행 폴더 created.json에 남긴다.
비밀값(.env)은 출력하지 않는다. 접근 토큰도 출력하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

EMAIL = "updates-e2e-test@example.invalid"           # 이메일·이름에 test (정리 스크립트가 이 표시를 확인한다)
NAME = "AI 업데이트 test"
MEMOS = ("M02", "M03", "M04", "M07", "M12")      # 4종목, 정답 항목 10개 (test_db_prep와 같다)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공용 DB 끝까지 확인 (테스트 사용자·시범 메모 5개)")
    ap.add_argument("--allow-shared-write", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    if not args.allow_shared_write:
        raise SystemExit("공용 DB에 쓰므로 --allow-shared-write가 필요합니다")

    import httpx
    import psycopg

    from ..common.config import REPO_ROOT
    from ..common.db import load_env
    from .db_store import check_conn, check_test_target, finish, seed_test_user, shared_write_dsn
    from .test_db_prep import gold_memos

    load_env()
    # 소셜 로그인 복귀 주소는 비밀값이 아니고 이 점검은 소셜 로그인을 쓰지 않는다. .env에 없으면 이 실행(과 점검 서버)에서만 개발용 값
    check_defaults = {"AUTH_WEB_RETURN_URLS": "http://localhost:8081", "AUTH_MOBILE_RETURN_URLS": "memos://auth"}
    filled = [k for k, v in check_defaults.items() if not os.environ.get(k) and not os.environ.__setitem__(k, v)]
    dsn = shared_write_dsn()
    target = check_test_target(dsn, allow_shared=True)          # 공용 DB(허용 목록)만
    out_dir = REPO_ROOT / "results/updates" / f"shared_e2e_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True)
    created: dict = {"target": target, "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                     "check_only_env_defaults": filled}
    save = lambda: (out_dir / "created.json").write_text(json.dumps(created, ensure_ascii=False, indent=1, default=str),
                                                        encoding="utf-8")
    print(f"공용 DB: {target} · 기록: {out_dir / 'created.json'}")

    # 1) 테스트 사용자·종목 보드
    memos = gold_memos(MEMOS)
    conn = psycopg.connect(dsn)
    created.update(seed_test_user(conn, EMAIL, NAME, sorted({m["symbol"] for m in memos}), allow_shared=True))
    created["email"] = EMAIL
    for prev in sorted((REPO_ROOT / "results/updates").glob("shared_e2e_*/created.json")):   # 앞 점검이 만든 사용자·보드는 이어받는다
        p = json.loads(prev.read_text(encoding="utf-8"))
        if prev.parent != out_dir and p.get("user_id") == created["user_id"] and p.get("target") == target:
            created["created_user"] = created["created_user"] or bool(p.get("created_user"))
            created["user_stock_symbols"] = sorted(set(created["user_stock_symbols"]) | set(p.get("user_stock_symbols") or []))
            created.setdefault("previous_runs", []).append(prev.parent.name)
    finish(conn, allow_shared=True)
    save()
    print(f"[1] 테스트 사용자 {created['user_id']} (새로 만듦 {created['created_user']}) · 종목 보드 {created['user_stock_symbols']}")

    # 2) 로그인 세션 (서버와 같은 키로 접근 토큰 발급, 토큰은 출력하지 않음)
    from app.auth.config import AuthSettings
    from app.auth.repository import AuthRepository
    from app.auth.service import AuthService
    from app.db import get_session
    with get_session() as s:
        svc = AuthService(AuthRepository(s), AuthSettings.from_env())
        user = svc.repo.get_user(int(created["user_id"]))
        tokens = svc.issue_session(user, user_agent="updates-e2e-check")
    created["auth_session_id"] = str(tokens.session_id)
    save()
    headers = {"Authorization": f"Bearer {tokens.access_token}"}
    print(f"[2] 세션 {created['auth_session_id']} (토큰은 출력하지 않음)")

    # 3) 서버
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(args.port)],
                              cwd=str(REPO_ROOT / "backend"), env=env, stdout=open(out_dir / "server.log", "w"),
                              stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{args.port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(1)
        else:
            raise SystemExit("서버가 뜨지 않았습니다 (server.log 확인)")
        c = httpx.Client(base_url=f"{base}/api/v1", headers=headers, timeout=120)
        me = httpx.get(f"{base}/api/v1/auth/me", headers=headers, timeout=10)
        print(f"[3] 서버 {base} · /auth/me {me.status_code} (사용자 {me.json().get('id') if me.status_code == 200 else '-'})")

        # 4) 메모 저장 → analysis
        created["memo_ids"] = []
        for m in memos:
            r = c.post(f"/stocks/{m['symbol']}/memos", json={"title": f"[점검] {m['memo_id']}", "body": m["text"], "ai_linked": True})
            body = r.json()
            a = body.get("analysis") or {}
            if r.status_code == 201:
                created["memo_ids"].append(int(body["id"]))
                save()
            print(f"[4] {m['memo_id']} {m['symbol']} → {r.status_code} · analysis {a.get('status')} {a.get('error') or ''} · 항목 "
                  f"{[i['description'] for i in a.get('items') or []]} · 확인 질문 {len(a.get('confirmations') or [])} · "
                  f"범위 밖 {a.get('out_of_scope')} · next_update_at {a.get('next_update_at')}")

        # 5) memos·tracking_items (읽기)
        with psycopg.connect(dsn) as rc:
            rc.read_only = True
            check_conn(rc, allow_shared=True)
            items = rc.execute("""SELECT ti.id, ti.memo_id, ti.type::text, ti.description, ti.status::text FROM tracking_items ti
                WHERE ti.memo_id = ANY(%s) ORDER BY ti.id""", (created["memo_ids"],)).fetchall()
            created["tracking_item_ids"] = [i[0] for i in items]
            created["memo_revision_ids"] = [r[0] for r in rc.execute(
                "SELECT id FROM memo_revisions WHERE memo_id = ANY(%s)", (created["memo_ids"],)).fetchall()]
            created["tracking_item_revision_ids"] = [r[0] for r in rc.execute(
                "SELECT id FROM tracking_item_revisions WHERE tracking_item_id = ANY(%s)", (created["tracking_item_ids"],)).fetchall()]
            rc.rollback()
        save()
        print(f"[5] memos {len(created['memo_ids'])} · tracking_items {len(items)} (" +
              ", ".join(f"{t}:{sum(1 for i in items if i[2] == t)}" for t in ("topic", "price_below", "price_above")) + ")")

        # 6) 매일 실행기 1회
        t0 = time.time()
        d = subprocess.run([sys.executable, "-m", "pipelines.updates.daily", "--allow-shared-write"], cwd=str(REPO_ROOT),
                           env=env, capture_output=True, text=True)
        (out_dir / "daily.log").write_text(d.stdout + d.stderr, encoding="utf-8")
        latest = json.loads((REPO_ROOT / "logs/updates_daily/latest.json").read_text(encoding="utf-8"))
        created["daily"] = {k: latest.get(k) for k in ("status", "run_id", "run_dir", "items", "cards", "usd", "error")}
        save()
        print(f"[6] 매일 실행 {d.returncode} · {round(time.time() - t0)}초 · " + json.dumps(created["daily"], ensure_ascii=False))

        # 7) tracking_updates·update_sources (읽기)
        with psycopg.connect(dsn) as rc:
            rc.read_only = True
            ups = rc.execute("""SELECT tu.id, tu.tracking_item_id, tu.type::text, tu.title, tu.price_state,
                (SELECT count(*) FROM update_sources us WHERE us.update_id = tu.id), tu.details->>'run_id'
                FROM tracking_updates tu WHERE tu.tracking_item_id = ANY(%s) ORDER BY tu.id""", (created["tracking_item_ids"],)).fetchall()
            created["tracking_update_ids"] = [u[0] for u in ups]
            created["update_source_ids"] = [r[0] for r in rc.execute(
                "SELECT id FROM update_sources WHERE update_id = ANY(%s)", (created["tracking_update_ids"],)).fetchall()]
            created["tracking_match_ids"] = [r[0] for r in rc.execute(
                "SELECT id FROM tracking_matches WHERE tracking_item_id = ANY(%s)", (created["tracking_item_ids"],)).fetchall()]
            rc.rollback()
        save()
        print(f"[7] tracking_updates {len(ups)} · update_sources {len(created['update_source_ids'])} · "
              f"tracking_matches {len(created['tracking_match_ids'])}")
        for u in ups:
            print(f"    카드 {u[0]} 항목 {u[1]} [{u[2]}] {u[3]}" + (f" ({u[4]})" if u[4] else "") + f" · 근거 {u[5]} · {u[6]}")

        # 8) 카드 조회 API · 읽음 처리
        for mid in created["memo_ids"]:
            t = c.get(f"/memos/{mid}/timeline")
            tj = t.json()
            print(f"[8] timeline {mid} → {t.status_code} · {[e['kind'] for e in tj.get('entries', [])]} · 항목 확인 시각 "
                  f"{sorted({str(i['last_checked_at'])[:16] for i in tj.get('tracking_items', [])})}")
        for sym in sorted({m["symbol"] for m in memos}):
            r = c.get(f"/stocks/{sym}/ai-updates")
            print(f"[8] ai-updates {sym} → {r.status_code} · {[(u['type'], u['headline'], u['read']) for u in r.json()]}")
        summary = c.get("/ai-updates/summary").json()
        print(f"[8] summary → " + json.dumps([{"stock": s["stock_code"], "new": s["new_count"]} for s in summary], ensure_ascii=False))
        if created["tracking_update_ids"]:
            first = created["tracking_update_ids"][0]
            r = c.post(f"/ai-updates/{first}/read")
            after = c.get("/ai-updates/summary").json()
            print(f"[8] read {first} → {r.status_code} · summary 뒤 "
                  + json.dumps([{"stock": s["stock_code"], "new": s["new_count"]} for s in after], ensure_ascii=False))
    finally:
        server.terminate()
        server.wait(timeout=20)
        created["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        save()
    print(f"\n만든 행 기록: {out_dir / 'created.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
