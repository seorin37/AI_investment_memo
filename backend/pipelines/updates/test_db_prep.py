"""로컬 테스트 DB 준비 (2026-11-11): 행 수 보기(status)와, 공용 DB(읽기 전용)에서 시범 메모 검증에 필요한 행을 복사하는 계획(plan)·복사(copy).

    PYTHONPATH=backend python -m pipelines.updates.test_db_prep status
    PYTHONPATH=backend python -m pipelines.updates.test_db_prep plan     # 시범 메모 5개(M02·M03·M04·M07·M12, 항목 10개)
    (복사는 계획을 확인한 뒤에 따로 만든다. 쓰기 코드는 db_store.py에만 둔다 — ReadOnlyGuardTest)

- 테스트 DB 주소는 환경변수 TEST_DATABASE_URL (값은 출력하지 않고 host:port/db만). 로컬 테스트 DB(127.0.0.1:5433, 이름에 test)가 아니면 멈춘다.
- 공용 DB는 get_read_dsn()으로 읽기만 한다.
"""

from __future__ import annotations

import argparse
import os

STATUS_TABLES = ("users", "stocks", "memos", "memo_revisions", "tracking_items", "tracking_item_revisions",
                 "news_sources", "news_articles", "news_stocks", "news_embedding_variants", "news_article_bodies", "news_chunks",
                 "disclosures", "disclosure_chunks", "disclosure_events", "prices_daily", "financials",
                 "tracking_updates", "update_sources", "tracking_matches", "tracking_usage_events", "price_events")


def test_conn():
    import psycopg

    from .db_store import check_test_target
    dsn = os.environ.get("TEST_DATABASE_URL", "")
    if not dsn:
        raise SystemExit("환경변수 TEST_DATABASE_URL이 없습니다")
    target = check_test_target(dsn)
    return psycopg.connect(dsn), target


def counts(conn, tables=STATUS_TABLES) -> dict[str, int | str]:
    out = {}
    for t in tables:
        try:
            out[t] = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        except Exception as exc:                                  # 테이블이 없으면 이름만
            conn.rollback()
            out[t] = f"없음({type(exc).__name__})"
    return out


def columns(conn, table: str) -> list[tuple]:
    return conn.execute("""SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns
                           WHERE table_name = %s ORDER BY ordinal_position""", (table,)).fetchall()


DEFAULT_MEMOS = ("M02", "M03", "M04", "M07", "M12")      # 4종목, 항목 10개 (주제 8 · 가격 2)
SINCE = "2025-11-09"                                       # experiment --since·--disclosure-since와 같게
PRICE_SINCE = "2025-09-01"                                 # 52주 고저점·시장 거래일 여유

# 공용 DB에서 복사할 행 (읽기만). (테이블, 세는 SQL). %(syms)s = 시범 종목, %(since)s·%(price_since)s
NEWS_IDS = """SELECT DISTINCT ns.news_id FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
WHERE ns.symbol = ANY(%(syms)s) AND a.published_at >= %(since)s"""
PLAN = [
    ("stocks", "SELECT count(*) FROM stocks"),
    ("news_sources", "SELECT count(*) FROM news_sources"),
    ("news_articles", f"SELECT count(*) FROM ({NEWS_IDS}) x"),
    ("news_stocks", f"SELECT count(*) FROM news_stocks WHERE symbol = ANY(%(syms)s) AND news_id IN ({NEWS_IDS})"),
    ("news_embedding_variants", f"SELECT count(*) FROM news_embedding_variants WHERE news_id IN ({NEWS_IDS})"),
    ("news_article_bodies", f"SELECT count(*) FROM news_article_bodies WHERE news_id IN ({NEWS_IDS})"),
    ("news_chunks", f"SELECT count(*) FROM news_chunks WHERE news_id IN ({NEWS_IDS})"),
    ("disclosures", "SELECT count(*) FROM disclosures WHERE symbol = ANY(%(syms)s) AND rcept_dt >= %(since)s"),
    ("disclosure_chunks", """SELECT count(*) FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no
        WHERE d.symbol = ANY(%(syms)s) AND d.rcept_dt >= %(since)s"""),
    ("disclosure_events", """SELECT count(*) FROM disclosure_events e JOIN disclosures d ON d.rcept_no = e.rcept_no
        WHERE d.symbol = ANY(%(syms)s) AND d.rcept_dt >= %(since)s"""),
    ("prices_daily", "SELECT count(*) FROM prices_daily WHERE symbol = ANY(%(syms)s) AND trade_date >= %(price_since)s"),
    ("financials", "SELECT count(*) FROM financials WHERE symbol = ANY(%(syms)s)"),
]


def gold_memos(memo_ids, path: str = "eval/memo_eval_v0/memo_eval_v0.jsonl") -> list[dict]:
    import json

    from ..common.config import resolve_path
    memos = [json.loads(l) for l in resolve_path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [m for m in memos if m["memo_id"] in memo_ids]


def gold_items(memo: dict) -> list[dict]:
    return [it for s in memo["sentences"] for it in s["items"] if it["type"] in ("topic", "price_below", "price_above")]


def plan(memo_ids=DEFAULT_MEMOS) -> int:
    import psycopg

    from ..common.db import get_read_dsn
    memos = gold_memos(memo_ids)
    syms = sorted({m["symbol"] for m in memos})
    items = [(m["memo_id"], it["type"], it["description"]) for m in memos for it in gold_items(m)]
    tconn, target = test_conn()
    with tconn:
        tconn.read_only = True
        have = counts(tconn, [t for t, _ in PLAN])
        have_stocks = {s.strip() for (s,) in tconn.execute("SELECT symbol FROM stocks").fetchall()}
        have_sources = {i for (i,) in tconn.execute("SELECT id FROM news_sources").fetchall()}
        tconn.rollback()
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True                                   # 공용 DB는 읽기만
        p = {"syms": syms, "since": f"{SINCE} 00:00+09", "price_since": PRICE_SINCE}
        p_disc = {**p, "since": SINCE}
        src = {t: conn.execute(sql, p_disc if t.startswith(("disclosure", "financials")) else p).fetchone()[0]
               for t, sql in PLAN}
        all_stocks = {s.strip() for (s,) in conn.execute("SELECT symbol FROM stocks").fetchall()}
        all_sources = {i for (i,) in conn.execute("SELECT id FROM news_sources").fetchall()}
        conn.rollback()
    src["stocks"] = len(all_stocks - have_stocks)
    src["news_sources"] = len(all_sources - have_sources)
    print(f"복사 대상: {target} (지금 비어 있는 테이블에 넣는다. 이미 있는 행은 건너뜀)")
    print(f"시범 메모 {len(memos)}개 · 종목 {syms} · 항목 {len(items)}개")
    for mid, typ, desc in items:
        print(f"  {mid} {typ} {desc}")
    print("\n| 테이블 | 테스트 DB 지금 | 공용 DB에서 읽어 넣을 행 |")
    print("|---|---|---|")
    for t, _ in PLAN:
        print(f"| {t} | {have[t]} | {src[t]} |")
    print(f"| users | 0 | 새로 1 (테스트 사용자) |")
    print(f"| memos · memo_revisions | 0 · 0 | 새로 {len(memos)} · {len(memos)} (평가 메모 원문) |")
    print(f"| tracking_items · tracking_item_revisions | 0 · 0 | 새로 {len(items)} · {len(items)} (정답 항목) |")
    print(f"\n조건: 뉴스·공시는 {SINCE} 이후(4종목), 기사는 news_stocks로 4종목에 붙은 것, 종가는 {PRICE_SINCE} 이후. "
          f"stocks·news_sources는 테스트 DB에 없는 것만.")
    return 0


def copy(memo_ids=DEFAULT_MEMOS) -> int:
    """계획대로 공용 DB(읽기 전용)에서 테스트 DB로 복사하고 시범 메모·항목을 넣는다. 한 트랜잭션 (실패하면 아무것도 남지 않음)."""
    import psycopg
    from psycopg import sql

    from ..common.db import get_read_dsn
    from .db_store import _test_columns, copy_table, finish, seed_memos

    memos = gold_memos(memo_ids)
    syms = sorted({m["symbol"] for m in memos})
    lit = sql.Literal
    since_ts, since_d, price_since = lit(f"{SINCE} 00:00+09"), lit(SINCE), lit(PRICE_SINCE)
    news_ids = sql.SQL("""SELECT DISTINCT ns.news_id FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
        WHERE ns.symbol = ANY({syms}) AND a.published_at >= {since}""").format(syms=lit(syms), since=since_ts)
    disc_nos = sql.SQL("SELECT rcept_no FROM disclosures WHERE symbol = ANY({}) AND rcept_dt >= {}").format(lit(syms), since_d)
    dst, target = test_conn()
    have_stocks = [s.strip() for (s,) in dst.execute("SELECT symbol FROM stocks").fetchall()]
    where = {
        "stocks": sql.SQL("symbol <> ALL({})").format(lit(have_stocks)),
        "news_articles": sql.SQL("id IN ({})").format(news_ids),
        "news_stocks": sql.SQL("symbol = ANY({}) AND news_id IN ({})").format(lit(syms), news_ids),
        "news_embedding_variants": sql.SQL("news_id IN ({})").format(news_ids),
        "news_article_bodies": sql.SQL("news_id IN ({})").format(news_ids),
        "news_chunks": sql.SQL("news_id IN ({})").format(news_ids),
        "disclosures": sql.SQL("rcept_no IN ({})").format(disc_nos),
        "disclosure_chunks": sql.SQL("rcept_no IN ({})").format(disc_nos),
        "disclosure_events": sql.SQL("rcept_no IN ({})").format(disc_nos),
        "prices_daily": sql.SQL("symbol = ANY({}) AND trade_date >= {}").format(lit(syms), price_since),
        "financials": sql.SQL("symbol = ANY({})").format(lit(syms)),
    }
    done = {}
    with psycopg.connect(get_read_dsn()) as src:
        src.read_only = True                                    # 공용 DB는 읽기만
        for table, cond in where.items():
            cols = _test_columns(dst, table)
            exprs = [sql.SQL("CASE WHEN corrects IN ({}) THEN corrects END").format(disc_nos) if (table, c) ==
                     ("disclosure_events", "corrects") else sql.Identifier(c) for c in cols]   # 범위 밖 원본은 비운다
            select = sql.SQL("SELECT {} FROM {} WHERE {}").format(sql.SQL(", ").join(exprs), sql.Identifier(table), cond)
            done[table] = copy_table(src, dst, table, select, cols)
            print(f"  {table}: {done[table]}행")
        src.rollback()
    seeded = seed_memos(dst, memos)
    n_items = sum(len(v) for v in seeded.values())
    print(f"  users 1 · memos {len(seeded)} (memo_revisions는 트리거가 만든다) · tracking_items·revisions {n_items}")
    for mid, its in seeded.items():
        for iid, it in its:
            print(f"    {mid} → tracking_items.id {iid} {it['type']} {it['description']}")
    finish(dst)                                                 # 테스트 DB인지 다시 확인하고 확정
    print(f"복사 끝: {target}")
    return 0


def show() -> int:
    """항목별 저장 결과 (읽기만): tracking_items.last_checked_at, tracking_updates, update_sources, tracking_matches."""
    conn, target = test_conn()
    with conn:
        conn.read_only = True
        print(f"테스트 DB: {target}")
        items = conn.execute("""SELECT ti.id, m.title, ti.type::text, ti.description, ti.last_checked_at FROM tracking_items ti
            JOIN memos m ON m.id = ti.memo_id ORDER BY ti.id""").fetchall()
        for iid, memo, typ, desc, checked in items:
            print(f"\n[항목 {iid}] {memo} {typ} {desc} · last_checked_at {checked}")
            for uid, utype, title, state, value, tdate, created, memo_rev, track_rev, cov in conn.execute(
                    """SELECT id, type::text, title, price_state, observed_value, observed_trade_date, created_at,
                    memo_revision_id, tracking_revision_id, details->>'coverage' FROM tracking_updates
                    WHERE tracking_item_id = %s ORDER BY id""", (iid,)).fetchall():
                print(f"  update {uid} [{utype}] {title} · 생성 {created:%H:%M:%S} · memo_rev {memo_rev} · track_rev {track_rev}"
                      + (f" · {state} {value} ({tdate})" if utype == "price_condition" else "") + (f" · 범위 {cov}" if cov else ""))
                for news_id, rcept, quote in conn.execute("""SELECT news_id, disclosure_rcept_no, quote FROM update_sources
                        WHERE update_id = %s ORDER BY id""", (uid,)).fetchall():
                    print(f"    source {'news:' + str(news_id) if news_id else 'disc:' + rcept} · {(quote or '')[:70]}")
            rows = conn.execute("""SELECT decision::text, count(*), round(avg(similarity)::numeric, 3) FROM tracking_matches
                WHERE tracking_item_id = %s GROUP BY 1 ORDER BY 1""", (iid,)).fetchall()
            if rows:
                print("  matches " + " · ".join(f"{d} {n}건(평균 유사도 {s})" for d, n, s in rows))
        print("\n합계:", {t: n for t, n in counts(conn, ("tracking_updates", "update_sources", "tracking_matches")).items()})
        conn.rollback()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="로컬 테스트 DB 준비 (행 수 보기 · 복사 계획 · 복사 · 결과 보기)")
    ap.add_argument("mode", choices=["status", "plan", "copy", "show"])
    args = ap.parse_args(argv)
    if args.mode == "show":
        return show()
    if args.mode == "plan":
        return plan()
    if args.mode == "copy":
        return copy()
    conn, target = test_conn()
    with conn:
        conn.read_only = True
        print(f"테스트 DB: {target}")
        for t, n in counts(conn).items():
            print(f"  {t}: {n}")
        print("tracking_usage_events 열:")
        for c in columns(conn, "tracking_usage_events"):
            print("  ", c)
        print("enum usage:", conn.execute("""SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid WHERE t.typname ~ 'usage|stage|step' GROUP BY 1""").fetchall())
        print("tracking_usage_events 제약:", conn.execute("""SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'tracking_usage_events'::regclass""").fetchall())
        conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
