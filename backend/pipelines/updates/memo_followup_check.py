"""한 사용자가 메모를 쓰고 → 이어 쓰고 → 고칠 때 추적 항목과 AI 카드가 따라가는지 공용 DB에서 끝까지 확인 (2026-11-12).

    PYTHONPATH=backend python -m pipelines.updates.memo_followup_check --allow-shared-write
    PYTHONPATH=backend python -m pipelines.updates.memo_followup_check --allow-shared-write --scenario my_scenario.json

흐름 (메모 버전마다): API로 메모 저장(PATCH body) → 분석(유지·done·새 항목) → 그 메모 항목만 카드 생성
(experiment --store db --item-ids, 다른 사용자 항목은 건드리지 않음) → timeline API로 카드·근거 날짜·자료 범위 확인.
- 매일 실행기(daily)는 부르지 않는다: 종목 단위라 같은 종목의 다른 항목까지 처리하고 logs/updates_daily/latest.json을 덮어쓴다.
- 카드 길이: --long-card(기본 켬)면 설정을 복사해 사실 문장 5개·문장 90자·연결 이유 120자로 늘린 파일을 실행 폴더에만 만든다.
  configs/updates.yaml(06:30 실행)은 바꾸지 않는다.
- 만든 행은 실행 폴더 created.json에 남긴다. 지우기: python -m pipelines.updates.db_cleanup <실행 폴더> --e2e --allow-shared-write
  (사용자·메모를 지우면 항목·카드·근거가 함께 지워진다. 카드 생성 실행 폴더(run_*)는 created.json의 card_runs).
- 임베딩은 CPU로 (실시간 수집 서비스·백필 적재와 GPU를 나누지 않게). 비밀값·접근 토큰은 출력하지 않는다.
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

EMAIL = "memo-followup-test@example.invalid"          # 이메일·이름에 test (db_cleanup이 이 표시를 확인한다)
NAME = "메모 이어쓰기 test"

# 기본 시나리오: SK하이닉스 메모 하나를 세 번 저장한다. v2는 이어 쓰기, v3는 첫 문장을 다른 관심사로 바꾼다.
SCENARIO = {
    "symbol": "000660",
    "title": "[점검] 메모 이어쓰기",
    "versions": [
        {"label": "v1 처음 작성",
         "body": "HBM 때문에 SK하이닉스 샀음.\n엔비디아에 HBM3E 공급하는 소식 나오면 알려줘."},
        {"label": "v2 이어 쓰기",
         "body": "HBM 때문에 SK하이닉스 샀음.\n엔비디아에 HBM3E 공급하는 소식 나오면 알려줘.\n"
                 "그리고 3분기 실적 나오면 영업이익이 작년보다 얼마나 늘었는지도 알려줘."},
        {"label": "v3 고쳐 쓰기",
         "body": "HBM은 이제 됐고 낸드 가격이 오른다는 소식이 궁금해.\n"
                 "그리고 3분기 실적 나오면 영업이익이 작년보다 얼마나 늘었는지도 알려줘."},
    ],
}

LONG_CARD = {"max_sentences": 5, "sentence_max_chars": 90, "reason_max": 120}
LONG_RULE = ("facts에는 근거에 적힌 수치·날짜·주체(누가, 무엇을, 얼마나)를 빠뜨리지 않고 씁니다. 근거에 사실이 여러 개 있으면 "
             "한 문장에 몰아 쓰지 말고 문장을 나눠 쓰되, 근거에 없는 내용으로 문장 수를 채우지 않습니다.")


def long_card_config(base_path: Path, out_path: Path) -> Path:
    """configs/updates.yaml을 읽어 카드 길이만 늘린 설정 파일을 out_path에 쓴다 (06:30 설정은 그대로)."""
    import yaml
    cfg = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    cfg["topic"].update(LONG_CARD)
    cfg["topic"]["extra_rules"] = list(cfg["topic"].get("extra_rules") or []) + [LONG_RULE]
    out_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out_path


def card_lines(entry: dict) -> list[str]:
    """timeline의 update 항목 → 보고용 줄 (카드 제목·날짜·사실·연결·자료 범위·근거 발행일)."""
    u = entry["update"]
    card = u.get("card") or {}
    out = [f"    카드 {u.get('id')} [{u.get('type')}] {u.get('headline') or u.get('title')}"
           f" · when {card.get('when')} · 대표 근거 발행 {str(u.get('published_at'))[:10]} · 만든 시각 {str(u.get('created_at'))[:16]}"
           f" · 메모 버전 {u.get('memo_version')}"]
    for f in card.get("facts") or []:
        out.append(f"      - {f.get('text')}  ({f.get('ref') or '근거 없음'})")
    if card.get("memo_link"):
        out.append(f"      연결: {card['memo_link']}")
    if card.get("coverage"):
        out.append(f"      자료 범위: {card['coverage']}")
    for s in u.get("sources") or []:
        out.append(f"      근거: {s.get('kind')} {str(s.get('published_at'))[:10]} {s.get('source', '')} {s.get('title', '')[:50]}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="메모 작성·이어쓰기·수정에 따른 추적·카드 확인 (공용 DB, 테스트 사용자 1명)")
    ap.add_argument("--allow-shared-write", action="store_true")
    ap.add_argument("--scenario", help="시나리오 JSON ({symbol, title, versions: [{label, body}]}). 없으면 기본 SK하이닉스 시나리오")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--max-usd", type=float, default=0.5, help="카드 생성 한 번의 LLM 비용 상한")
    ap.add_argument("--long-card", action=argparse.BooleanOptionalAction, default=True,
                    help="카드 길이를 늘린 설정으로 (기본 켬, --no-long-card면 configs/updates.yaml 그대로)")
    args = ap.parse_args(argv)
    if not args.allow_shared_write:
        raise SystemExit("공용 DB에 쓰므로 --allow-shared-write가 필요합니다")

    import httpx
    import psycopg

    from ..common.config import REPO_ROOT, resolve_path
    from ..common.db import load_env
    from .db_store import check_conn, check_test_target, finish, seed_test_user, shared_write_dsn
    from .usage import LOG_PATH

    usage_log = resolve_path(LOG_PATH)

    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8")) if args.scenario else SCENARIO
    load_env()
    check_defaults = {"AUTH_WEB_RETURN_URLS": "http://localhost:8081", "AUTH_MOBILE_RETURN_URLS": "memos://auth"}
    filled = [k for k, v in check_defaults.items() if not os.environ.get(k) and not os.environ.__setitem__(k, v)]
    dsn = shared_write_dsn()
    target = check_test_target(dsn, allow_shared=True)
    out_dir = REPO_ROOT / "results/updates" / f"memo_followup_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True)
    created: dict = {"target": target, "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                     "check_only_env_defaults": filled, "scenario": scenario, "card_runs": [], "versions": []}
    save = lambda: (out_dir / "created.json").write_text(json.dumps(created, ensure_ascii=False, indent=1, default=str),
                                                        encoding="utf-8")
    config = (long_card_config(REPO_ROOT / "configs/updates.yaml", out_dir / "updates_longcard.yaml")
              if args.long_card else REPO_ROOT / "configs/updates.yaml")
    created["config"] = str(config)
    print(f"공용 DB: {target} · 기록: {out_dir / 'created.json'} · 카드 설정 {config.name}"
          + (f" ({LONG_CARD})" if args.long_card else ""))

    # 1) 테스트 사용자·종목 보드
    symbol = scenario["symbol"]
    conn = psycopg.connect(dsn)
    created.update(seed_test_user(conn, EMAIL, NAME, [symbol], allow_shared=True))
    created["email"] = EMAIL
    finish(conn, allow_shared=True)
    save()
    print(f"[1] 테스트 사용자 {created['user_id']} (새로 만듦 {created['created_user']}) · 종목 보드 {created['user_stock_symbols']}")

    # 2) 로그인 세션 (토큰은 출력하지 않음)
    from app.auth.config import AuthSettings
    from app.auth.repository import AuthRepository
    from app.auth.service import AuthService
    from app.db import get_session
    with get_session() as s:
        svc = AuthService(AuthRepository(s), AuthSettings.from_env())
        tokens = svc.issue_session(svc.repo.get_user(int(created["user_id"])), user_agent="memo-followup-check")
    created["auth_session_id"] = str(tokens.session_id)
    save()
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    # 3) 서버 (CPU 임베딩)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend"), "CUDA_VISIBLE_DEVICES": ""}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(args.port)],
                              cwd=str(REPO_ROOT / "backend"), env=env, stdout=open(out_dir / "server.log", "w"),
                              stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{args.port}"
    try:
        for _ in range(90):
            try:
                if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise SystemExit("서버가 뜨지 않았습니다 (server.log 확인)")
        c = httpx.Client(base_url=f"{base}/api/v1", headers=headers, timeout=300)
        print(f"[2] 세션 {created['auth_session_id']} · 서버 {base}")

        memo_id = None
        seen_cards: set = set()
        for n, ver in enumerate(scenario["versions"], 1):
            print(f"\n=== {ver['label']} ===")
            for line in ver["body"].splitlines():
                print(f"  | {line}")
            # 메모 저장 → 분석
            if memo_id is None:
                r = c.post(f"/stocks/{symbol}/memos", json={"title": scenario["title"], "body": ver["body"], "ai_linked": True})
                if r.status_code == 201:
                    memo_id = int(r.json()["id"])
                    created["memo_ids"] = [memo_id]
                    save()
            else:
                r = c.patch(f"/board-items/{memo_id}", json={"body": ver["body"]})
            body = r.json()
            a = body.get("analysis") or {}
            print(f"[메모] {r.status_code} · 분석 {a.get('status')} {a.get('error') or ''} · 새 항목 {a.get('created')} · done {a.get('done')}"
                  f" · 확인 질문 {len(a.get('confirmations') or [])} · 범위 밖 {a.get('out_of_scope')}")
            if r.status_code not in (200, 201) or memo_id is None:
                raise SystemExit(f"메모 저장 실패: {r.status_code} {str(body)[:300]}")

            # 항목 상태 (읽기)
            with psycopg.connect(dsn) as rc:
                rc.read_only = True
                check_conn(rc, allow_shared=True)
                items = rc.execute("""SELECT ti.id, ti.type::text, ti.status::text,
                      COALESCE((SELECT r.description FROM tracking_item_revisions r WHERE r.tracking_item_id = ti.id
                                ORDER BY r.revision_no DESC LIMIT 1), ti.description), ti.last_checked_at
                    FROM tracking_items ti WHERE ti.memo_id = %s ORDER BY ti.id""", (memo_id,)).fetchall()
                rc.rollback()
            for iid, typ, st, desc, checked in items:
                print(f"  항목 {iid} [{typ}] {st:6} {desc} · 마지막 확인 {str(checked)[:16] if checked else '없음(첫 확인)'}")
            active = [str(i[0]) for i in items if i[2] == "active"]
            vrec = {"label": ver["label"], "status_code": r.status_code, "analysis": a,
                    "items": [{"id": i[0], "type": i[1], "status": i[2], "description": i[3], "last_checked_at": i[4]} for i in items]}

            # 카드 생성 (이 메모 항목만)
            if active:
                before = {p.name for p in (REPO_ROOT / "results/updates").glob("run_*")}
                t0 = time.time()
                cmd = [sys.executable, "-m", "pipelines.updates.experiment", "--llm", "openai", "--store", "db",
                       "--allow-shared-write", "--symbols", symbol, "--item-ids", ",".join(active),
                       "--config", str(config), "--max-usd", str(args.max_usd), "--job", "memo_followup_check"]
                d = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
                (out_dir / f"cards_{n}.log").write_text(d.stdout + d.stderr, encoding="utf-8")
                runs = sorted({p.name for p in (REPO_ROOT / "results/updates").glob("run_*")} - before)
                created["card_runs"] += runs
                vrec["card_run"] = runs
                print(f"[카드 생성] 종료 {d.returncode} · {round(time.time() - t0)}초 · 실행 {runs}")
                for run in runs:
                    resp = REPO_ROOT / "results/updates" / run / "responses.jsonl"
                    if resp.is_file():
                        for line in resp.read_text(encoding="utf-8").splitlines():
                            j = json.loads(line)
                            print(f"  응답 항목 {j.get('item_id')} → {j.get('type')} {j.get('reason') or ''}"
                                  f" {j.get('fail_codes') or ''}"[:200])
                    for line in usage_log.read_text(encoding="utf-8").splitlines() if usage_log.is_file() else []:
                        u = json.loads(line)
                        if Path(u.get("run_dir") or "").name == run:
                            vrec["usd"] = (u.get("total") or {}).get("usd")
                            print(f"  비용 ${vrec['usd']}")
                if d.returncode != 0:
                    print("  카드 생성 실패: " + (d.stderr.strip().splitlines() or ["?"])[-1][:300])
            save()

            # timeline (이번 버전에서 새로 생긴 카드만 자세히)
            t = c.get(f"/memos/{memo_id}/timeline").json()
            ups = [e for e in t.get("entries", []) if e.get("kind") == "update"]
            new = [e for e in ups if e["update"].get("id") not in seen_cards]
            print(f"[timeline] 항목 {[e['kind'] for e in t.get('entries', [])]} · 카드 전체 {len(ups)} · 이번에 새로 {len(new)}")
            for e in new:
                seen_cards.add(e["update"].get("id"))
                for line in card_lines(e):
                    print(line)
            vrec["new_cards"] = [e["update"] for e in new]
            created["versions"].append(vrec)
            save()
        s = c.get("/ai-updates/summary").json()
        print("\n[summary] " + json.dumps([{"stock": x["stock_code"], "new": x["new_count"]} for x in s], ensure_ascii=False))
    finally:
        server.terminate()
        server.wait(timeout=20)
        created["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        save()
    from .memo_followup_report import main as report_main
    report_main([str(out_dir)])                                 # 한 페이지 보고서 report.html
    print(f"\n기록: {out_dir / 'created.json'} · 지우기: python -m pipelines.updates.db_cleanup {out_dir} --e2e --allow-shared-write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
