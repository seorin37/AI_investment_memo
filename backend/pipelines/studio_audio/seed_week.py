"""AI 오디오 시험 데이터 만들기 (2026-11-23): 테스트 사용자 1명 · 4종목 보드 · 일주일치 메모 · 실제 파이프라인 카드.

    # 로컬 테스트 DB (TEST_DATABASE_URL, 127.0.0.1:5433/*test*) — 공시·뉴스·주가가 복사돼 있어야 카드가 나온다
    PYTHONPATH=backend python -m pipelines.studio_audio.seed_week
    # 공용 DB (공시·뉴스·주가가 다 있는 곳). 테스트 사용자·메모·카드만 만든다
    PYTHONPATH=backend python -m pipelines.studio_audio.seed_week --allow-shared-write
    # 메모만 만들고 카드는 나중에 / 기간 바꾸기
    ... --no-cards          ... --end 2026-11-22 --days 7
    # 지우기 (shared_e2e_check와 같은 정리 도구, created.json을 읽는다)
    PYTHONPATH=backend python -m pipelines.updates.db_cleanup results/studio_audio/seed_<시각> --e2e [--execute] [--allow-shared-write]

흐름
1. 테스트 사용자(이메일·이름에 test)와 4종목 보드. 보유/관심은 seed_memos.yaml.
2. 메모 7개를 앱과 같은 길(BoardService.create_memo, AI 켜기)로 저장 → 메모 분석 LLM이 추적 항목을 만든다.
3. 메모·메모 버전·추적 항목 날짜를 '기간 첫날 + day'의 21시로 소급한다 (일주일 동안 쓴 것처럼).
4. 업데이트 파이프라인(experiment --store db, 이 항목들만, 자료는 기간 첫날부터)으로 실제 카드를 만든다 (OpenAI 비용).
5. 카드 생성 시각을 '근거가 나온 다음 날 06:30'으로 소급한다 (매일 실행이 그날그날 만든 것처럼). 메모보다 앞서지 않게,
   지금보다 늦지 않게 맞춘다.
만든 행 id는 results/studio_audio/seed_<시각>/created.json (정리 도구가 읽는 모양).

주의: 카드가 몇 장 나올지는 그 주에 실제로 나온 공시·뉴스와 관련성 판정에 달려 있다. 0장인 종목은 오디오에서 '새 소식 없음'이 된다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
EMAIL = "studio-audio-test@example.invalid"
NAME = "AI 오디오 test"
MEMO_HOUR = time(21, 0)
CARD_TIME = time(6, 30)

BACKDATE_MEMO = """UPDATE memos SET created_at = %(at)s, updated_at = %(at)s, ai_linked_at = %(at)s WHERE id = %(id)s AND user_id = %(uid)s"""
BACKDATE_REVISIONS = "UPDATE memo_revisions SET created_at = %(at)s WHERE memo_id = %(id)s"
BACKDATE_ITEMS = "UPDATE tracking_items SET created_at = %(at)s, updated_at = %(at)s WHERE memo_id = %(id)s"
BACKDATE_ITEM_REVS = """UPDATE tracking_item_revisions SET created_at = %(at)s
WHERE tracking_item_id IN (SELECT id FROM tracking_items WHERE memo_id = %(id)s)"""
CARDS = """
SELECT tu.id, tu.type::text, ti.memo_id, tu.observed_trade_date,
       max(greatest(a.published_at::date, d.rcept_dt)) AS evidence_day
FROM tracking_updates tu
JOIN tracking_items ti ON ti.id = tu.tracking_item_id
LEFT JOIN update_sources us ON us.update_id = tu.id
LEFT JOIN news_articles a ON a.id = us.news_id
LEFT JOIN disclosures d ON d.rcept_no = us.disclosure_rcept_no
WHERE ti.memo_id = ANY(%(memos)s)
GROUP BY tu.id, tu.type, ti.memo_id, tu.observed_trade_date"""
BACKDATE_CARD = "UPDATE tracking_updates SET created_at = %(at)s WHERE id = %(id)s"


def sa_url(dsn: str) -> str:
    """SQLAlchemy 주소 (psycopg 3 드라이버)."""
    return re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql+psycopg://", dsn.strip())


def pg_dsn(dsn: str) -> str:
    """psycopg 주소 (드라이버 표시 없이)."""
    return re.sub(r"^postgres(?:ql)?(?:\+\w+)?://", "postgresql://", dsn.strip())


def load_seed(path: Path | None = None) -> dict:
    import yaml
    path = path or Path(__file__).with_name("seed_memos.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def memo_time(start: date, day: int) -> datetime:
    return datetime.combine(start + timedelta(days=day), MEMO_HOUR, SEOUL)


def card_time(evidence_day: date | None, memo_at: datetime, now: datetime) -> datetime:
    """근거가 나온 다음 날 06:30. 메모를 쓴 뒤의 첫 06:30보다 이르지 않게, 지금보다 늦지 않게."""
    first_run = datetime.combine(memo_at.date() + timedelta(days=1), CARD_TIME, SEOUL)
    at = datetime.combine(evidence_day + timedelta(days=1), CARD_TIME, SEOUL) if evidence_day else first_run
    return min(max(at, first_run), now)


def backdate_cards(conn, memo_ids: list[int], memo_at: dict[int, datetime], now: datetime) -> list[dict]:
    """메모들에 붙은 카드의 생성 시각을 근거 다음 날 06:30으로 바꾼다 (커밋은 호출자). 반환: 카드마다 바뀐 시각."""
    out = []
    for cid, ctype, mid, observed, evidence in conn.execute(CARDS, {"memos": memo_ids}).fetchall():
        day = observed if ctype == "price_condition" and observed else evidence
        at = card_time(day, memo_at[mid], now)
        conn.execute(BACKDATE_CARD, {"at": at, "id": cid})
        out.append({"id": cid, "type": ctype, "memo_id": mid, "evidence_day": str(day) if day else None,
                    "created_at": at.isoformat()})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AI 오디오 시험 데이터 (테스트 사용자·4종목·일주일 메모·카드)")
    ap.add_argument("--allow-shared-write", action="store_true", help="공용 DB에 만든다 (없으면 로컬 테스트 DB)")
    ap.add_argument("--end", help="기간 마지막 날 YYYY-MM-DD (기본: 어제)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--no-cards", action="store_true", help="메모만 만들고 업데이트 파이프라인은 돌리지 않는다")
    ap.add_argument("--max-usd", type=float, default=0.5, help="업데이트 파이프라인 LLM 비용 한도")
    ap.add_argument("--seed", help="메모 파일 (기본: seed_memos.yaml)")
    args = ap.parse_args(argv)
    shared = args.allow_shared_write

    import psycopg
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from ..common.config import REPO_ROOT
    from ..common.db import load_env
    from ..updates.db_store import check_conn, check_test_target, finish, seed_test_user, shared_write_dsn

    load_env()
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise SystemExit("메모 분석(추적 항목)과 카드에 OpenAI 키가 필요해요 (.env OPENAI_API_KEY)")
    now = datetime.now(SEOUL)
    end = date.fromisoformat(args.end) if args.end else now.date() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    seed = load_seed(Path(args.seed) if args.seed else None)
    dsn = shared_write_dsn() if shared else os.environ.get("TEST_DATABASE_URL", "")
    if not dsn:
        raise SystemExit("TEST_DATABASE_URL이 없습니다 (공용 DB에 만들려면 --allow-shared-write)")
    target = check_test_target(pg_dsn(dsn), allow_shared=shared)
    out = REPO_ROOT / "results/studio_audio" / f"seed_{now:%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    created: dict = {"target": target, "email": EMAIL, "period": {"start": start.isoformat(), "end": end.isoformat()},
                     "started_at": now.isoformat(timespec="seconds"), "memo_ids": [], "memos": {}}
    save = lambda: (out / "created.json").write_text(json.dumps(created, ensure_ascii=False, indent=1, default=str),
                                                    encoding="utf-8")
    print(f"대상 {target} · 기간 {start} ~ {end} · 기록 {out / 'created.json'}")

    # 1) 테스트 사용자·보드
    symbols = sorted(seed["stocks"])
    conn = psycopg.connect(pg_dsn(dsn))
    created.update(seed_test_user(conn, EMAIL, NAME, symbols, allow_shared=shared))
    uid = created["user_id"]
    old = conn.execute("SELECT count(*) FROM memos WHERE user_id = %s AND deleted_at IS NULL", (uid,)).fetchone()[0]
    if old:
        conn.rollback()
        conn.close()
        raise SystemExit(f"테스트 사용자 {uid}에 메모 {old}개가 이미 있습니다. 앞 시험 데이터를 먼저 지우세요 "
                         f"(pipelines.updates.db_cleanup <앞 seed 폴더> --e2e --execute)")
    for sym, hold in seed["stocks"].items():
        conn.execute("UPDATE user_stocks SET status = %s WHERE user_id = %s AND symbol = %s",
                     ("holding" if hold == "보유" else "watching", uid, sym))
    finish(conn, allow_shared=shared)
    save()
    print(f"[1] 테스트 사용자 {uid} (새로 만듦 {created['created_user']}) · 보드 {symbols}")

    # 2) 메모 저장 (앱과 같은 서비스 → 메모 분석)
    from app.board.repository import BoardRepository
    from app.board.schemas import MemoCreate
    from app.board.service import BoardService
    engine = create_engine(sa_url(dsn), pool_pre_ping=True)
    memos = sorted(seed["memos"], key=lambda m: m["day"])
    with Session(engine) as s:
        check_conn(s.connection().connection.driver_connection, allow_shared=shared)
        service = BoardService(BoardRepository(s))
        for m in memos:
            r = service.create_memo(uid, m["symbol"], MemoCreate(title=m["title"], body=m["body"], color=m.get("color", "yellow"),
                                                                 ai_linked=True))
            a = r.get("analysis") or {}
            mid = int(r["id"])
            created["memo_ids"].append(mid)
            created["memos"][m["key"]] = {"id": mid, "symbol": m["symbol"], "day": m["day"], "analysis": a.get("status"),
                                          "items": [i["description"] for i in a.get("items") or []],
                                          "confirmations": len(a.get("confirmations") or []), "error": a.get("error")}
            save()
            print(f"[2] {m['key']} {m['symbol']} → 메모 {mid} · 분석 {a.get('status')} {a.get('error') or ''} · "
                  f"항목 {[i['description'] for i in a.get('items') or []]} · 확인 질문 {len(a.get('confirmations') or [])}")
    engine.dispose()

    # 3) 날짜 소급
    conn = psycopg.connect(pg_dsn(dsn))
    check_conn(conn, allow_shared=shared)
    memo_at = {}
    for m in memos:
        info = created["memos"][m["key"]]
        at = memo_time(start, int(m["day"]))
        memo_at[info["id"]] = at
        p = {"at": at, "id": info["id"], "uid": uid}
        for sql in (BACKDATE_MEMO, BACKDATE_REVISIONS, BACKDATE_ITEMS, BACKDATE_ITEM_REVS):
            conn.execute(sql, p)
        info["created_at"] = at.isoformat()
    created["item_ids"] = [r[0] for r in conn.execute(
        "SELECT id FROM tracking_items WHERE memo_id = ANY(%s) AND status::text = 'active' ORDER BY id",
        (created["memo_ids"],)).fetchall()]
    finish(conn, allow_shared=shared)
    save()
    print(f"[3] 메모 날짜 소급 · 추적 항목 {len(created['item_ids'])}개 {created['item_ids']}")
    if args.no_cards or not created["item_ids"]:
        print("카드는 만들지 않았습니다" + ("" if args.no_cards else " (추적 항목 없음)"))
        return 0

    # 4) 실제 업데이트 파이프라인 (이 항목들만, 자료는 기간 첫날부터)
    from ..updates.experiment import main as experiment_main
    argv2 = ["--llm", "openai", "--store", "db", "--symbols", ",".join(symbols), "--item-ids",
             ",".join(str(i) for i in created["item_ids"]), "--since", start.isoformat(), "--disclosure-since", start.isoformat(),
             "--max-usd", str(args.max_usd), "--job", "studio_audio_seed"]
    if shared:
        argv2.append("--allow-shared-write")
    code = experiment_main(argv2)
    created["experiment_exit"] = code
    save()
    print(f"[4] 업데이트 파이프라인 종료 코드 {code}")

    # 5) 카드 날짜 소급
    conn = psycopg.connect(pg_dsn(dsn))
    check_conn(conn, allow_shared=shared)
    created["cards"] = backdate_cards(conn, created["memo_ids"], memo_at, now)
    created["tracking_update_ids"] = [c["id"] for c in created["cards"]]
    finish(conn, allow_shared=shared)
    created["finished_at"] = datetime.now(SEOUL).isoformat(timespec="seconds")
    save()
    by_symbol: dict[str, int] = {}
    for c in created["cards"]:
        sym = next(v["symbol"] for v in created["memos"].values() if v["id"] == c["memo_id"])
        by_symbol[sym] = by_symbol.get(sym, 0) + 1
    print(f"[5] 카드 {len(created['cards'])}장 날짜 소급 · 종목별 {by_symbol or '없음'}")
    for c in sorted(created["cards"], key=lambda c: c["created_at"]):
        print(f"    카드 {c['id']} [{c['type']}] 메모 {c['memo_id']} · 근거 {c['evidence_day']} → {c['created_at'][:16]}")
    print(f"\n다음: PYTHONPATH=backend python -m pipelines.studio_audio.run --email {EMAIL} --end {end} "
          f"--days {args.days}{'' if shared else ' --test-db'}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
