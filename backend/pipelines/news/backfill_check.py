"""과거 뉴스 백필 확인 도구 (DB 읽기만).

  python -m backend.pipelines.news.backfill_check gap --since 2026-11-11T17:00 --until 2026-11-12T03:00
      # 수집 시각(collected_at) 공백과, 공백 뒤 첫 수집에 들어온 매체별 기사
  python -m backend.pipelines.news.backfill_check stats --date 2026-10-27 [--sources hankyung,mk] [--json]
      # 그 발행일(KST) 기사 수·원문 수·청크/임베딩 수·제목+요약 임베딩 수·4종목 태그 수, DB 용량
  python -m backend.pipelines.news.backfill_check lag [--raw-dir data/news_raw]
      # 실시간 원문 임베딩 지연: 최근 2일 발행분 중 원문을 받은 지 2시간 넘었는데 청크가 없는 기사

- 접속은 --dsn-env(기본 DATABASE_URL)의 주소, 없으면 .env. 세션은 read_only라 쓰기를 DB가 거부한다.
- lag는 backfill_list가 50건마다 부르는 안전장치와 같은 함수(realtime_lag)를 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
RAW_DIR = Path("data/news_raw")
LAG_DAYS = 2              # 최근 며칠 발행분을 볼지
LAG_LIMIT_HOURS = 2.0     # 원문을 받은 지 이보다 오래됐는데 청크가 없으면 지연으로 본다
STOCK_SYMBOLS = ("005930", "000660", "035420", "105560")   # stocks.yaml의 4종목


def connect(dsn: str):
    import psycopg

    conn = psycopg.connect(dsn)
    conn.read_only = True
    return conn


def dsn_from_env(env_name: str | None = None) -> str | None:
    """env_name 환경변수의 주소(psycopg 형식). 없으면 .env를 읽은 뒤 DATABASE_URL."""
    from ..common.db import _psycopg_url, get_dsn, load_env

    load_env()
    if env_name and env_name != "DATABASE_URL":
        url = os.getenv(env_name)
        return _psycopg_url(url) if url else None
    return get_dsn()


def day_window(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=KST)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


# ---------------------------------------------------------------- 실시간 원문 임베딩 지연

def ok_records(raw_dir: Path, days: list[date]) -> list[dict]:
    """data/news_raw/<날짜>.jsonl의 status ok 기록 (news_id·fetched_at·published_at만)."""
    out = []
    for day in days:
        path = raw_dir / f"{day.isoformat()}.jsonl"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") == "ok" and row.get("fetched_at"):
                out.append({"news_id": int(row["news_id"]), "fetched_at": row["fetched_at"],
                            "published_at": row.get("published_at")})
    return out


def lagging(records: list[dict], loaded_ids: set[int], known_ids: set[int], now: datetime,
            limit_hours: float = LAG_LIMIT_HOURS) -> list[tuple[int, float]]:
    """(news_id, 받은 뒤 지난 시간) — 원문을 받은 지 limit_hours가 넘었는데 청크가 없는 기사.
    news_articles에 없는 id(다른 DB에서 받은 기록)는 뺀다. 같은 기사의 여러 기록은 가장 이른 fetched_at 기준."""
    first: dict[int, datetime] = {}
    for r in records:
        at = datetime.fromisoformat(r["fetched_at"])
        if at.tzinfo is None:
            at = at.replace(tzinfo=KST)
        nid = r["news_id"]
        if nid not in first or at < first[nid]:
            first[nid] = at
    out = []
    for nid, at in first.items():
        if nid in loaded_ids or nid not in known_ids:
            continue
        hours = (now - at).total_seconds() / 3600
        if hours > limit_hours:
            out.append((nid, round(hours, 2)))
    return sorted(out, key=lambda x: -x[1])


def realtime_lag(conn, raw_dir: Path = RAW_DIR, now: datetime | None = None, days: int = LAG_DAYS,
                 limit_hours: float = LAG_LIMIT_HOURS) -> dict:
    """{'lagging': 지연 기사 수, 'max_hours': 가장 긴 지연, 'checked': 본 ok 기사 수, 'examples': [...]}"""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    today = now.astimezone(KST).date()
    records = ok_records(raw_dir, [today - timedelta(days=i) for i in range(days)])
    ids = sorted({r["news_id"] for r in records})
    loaded, known = set(), set()
    if ids:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT news_id FROM news_chunks WHERE news_id = ANY(%s)", (ids,))
            loaded = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT id FROM news_articles WHERE id = ANY(%s)", (ids,))
            known = {r[0] for r in cur.fetchall()}
        conn.rollback()
    late = lagging(records, loaded, known, now, limit_hours)
    return {"lagging": len(late), "max_hours": late[0][1] if late else 0.0, "checked": len(ids),
            "examples": late[:5]}


# ---------------------------------------------------------------- 하루 통계

STATS_SQL = """
WITH a AS (
  SELECT a.id, s.code FROM news_articles a JOIN news_sources s ON s.id = a.source_id
  WHERE a.published_at >= %(start)s AND a.published_at < %(end)s AND s.code = ANY(%(codes)s)
)
SELECT a.code,
       count(*) AS articles,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM news_article_bodies b WHERE b.news_id = a.id)) AS bodies,
       (SELECT count(*) FROM news_chunks c JOIN a a2 ON a2.id = c.news_id
         WHERE a2.code = a.code AND c.dense_embedding IS NOT NULL) AS chunks_embedded,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM news_embedding_variants v
                                      WHERE v.news_id = a.id AND v.variant = 'hybrid')) AS title_embedded,
       (SELECT count(*) FROM news_stocks t JOIN a a3 ON a3.id = t.news_id
         WHERE a3.code = a.code AND t.symbol = ANY(%(symbols)s)) AS stock_tags
FROM a GROUP BY a.code ORDER BY a.code
"""


def raw_counts(raw_dir: Path, day: date, codes: list[str]) -> dict[str, dict[str, int]]:
    """data/news_raw/<날짜>.jsonl의 매체별 마지막 상태 (ok/skipped/failed) 건수."""
    path = raw_dir / f"{day.isoformat()}.jsonl"
    last: dict[str, tuple[str, str]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                last[row["url"]] = (row["source_code"], row["status"])
    out: dict[str, dict[str, int]] = {c: {"ok": 0, "skipped": 0, "failed": 0} for c in codes}
    for code, status in last.values():
        if code in out:
            out[code][status] = out[code].get(status, 0) + 1
    return out


def day_stats(conn, day: date, codes: list[str], raw_dir: Path = RAW_DIR) -> dict:
    start, end = day_window(day)
    with conn.cursor() as cur:
        cur.execute(STATS_SQL, {"start": start, "end": end, "codes": codes, "symbols": list(STOCK_SYMBOLS)})
        cols = [d.name for d in cur.description]
        rows = {r[0]: dict(zip(cols[1:], r[1:])) for r in cur.fetchall()}
        cur.execute("SELECT pg_database_size(current_database())")
        size = cur.fetchone()[0]
    conn.rollback()
    raw = raw_counts(raw_dir, day, codes)
    for code in codes:
        row = rows.setdefault(code, {"articles": 0, "bodies": 0, "chunks_embedded": 0, "title_embedded": 0,
                                     "stock_tags": 0})
        r = raw.get(code, {})
        tried = r.get("ok", 0) + r.get("failed", 0)
        row["raw_ok"], row["raw_skipped"], row["raw_failed"] = r.get("ok", 0), r.get("skipped", 0), r.get("failed", 0)
        # 실패율 = failed / (ok + failed). 유료·포토·짧은 본문(skipped)은 정책상 제외라 분모에서 뺀다
        row["fail_rate"] = round(r.get("failed", 0) / tried, 4) if tried else 0.0
    return {"date": day.isoformat(), "sources": rows, "db_size_bytes": size}


# ---------------------------------------------------------------- 수집 공백

GAP_SQL = """
SELECT t, lag(t) OVER (ORDER BY t) AS prev FROM (
  SELECT DISTINCT date_trunc('minute', collected_at) AS t FROM news_articles
  WHERE collected_at >= %(since)s AND collected_at < %(until)s) x
ORDER BY t
"""
BATCH_SQL = """
SELECT s.code, count(*), min(a.published_at), max(a.published_at)
FROM news_articles a JOIN news_sources s ON s.id = a.source_id
WHERE date_trunc('minute', a.collected_at) = %(t)s GROUP BY s.code ORDER BY s.code
"""


def gaps(conn, since: datetime, until: datetime, min_minutes: int = 45) -> list[dict]:
    """수집 회차 사이가 min_minutes보다 긴 구간과, 공백 뒤 첫 회차에 들어온 매체별 기사(발행 시각 범위)."""
    out = []
    with conn.cursor() as cur:
        cur.execute(GAP_SQL, {"since": since, "until": until})
        for t, prev in cur.fetchall():
            if prev is None or (t - prev) < timedelta(minutes=min_minutes):
                continue
            with conn.cursor() as c2:
                c2.execute(BATCH_SQL, {"t": t})
                batch = {code: {"new": n, "published_min": lo.astimezone(KST).isoformat(timespec="minutes"),
                                "published_max": hi.astimezone(KST).isoformat(timespec="minutes")}
                         for code, n, lo, hi in c2.fetchall()}
            out.append({"last_before": prev.astimezone(KST).isoformat(timespec="minutes"),
                        "first_after": t.astimezone(KST).isoformat(timespec="minutes"),
                        "minutes": round((t - prev).total_seconds() / 60), "first_batch": batch})
    conn.rollback()
    return out


def _kst(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return (dt if dt.tzinfo else dt.replace(tzinfo=KST)).astimezone(UTC)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="뉴스 백필 확인 (DB 읽기만)")
    ap.add_argument("--dsn-env", default="DATABASE_URL", help="접속 주소를 읽을 환경변수 (기본 DATABASE_URL)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gap")
    g.add_argument("--since", required=True, help="KST 시각 (예: 2026-11-11T17:00)")
    g.add_argument("--until", required=True)
    g.add_argument("--min-minutes", type=int, default=45)
    s = sub.add_parser("stats")
    s.add_argument("--date", required=True, type=date.fromisoformat)
    s.add_argument("--sources", default="hankyung,mk")
    s.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    s.add_argument("--json", action="store_true")
    l = sub.add_parser("lag")
    l.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    l.add_argument("--hours", type=float, default=LAG_LIMIT_HOURS)
    args = ap.parse_args(argv)

    dsn = dsn_from_env(args.dsn_env)
    if not dsn:
        print(f"{args.dsn_env} 접속 정보가 없습니다.")
        return 1
    with connect(dsn) as conn:
        if args.cmd == "gap":
            print(json.dumps(gaps(conn, _kst(args.since), _kst(args.until), args.min_minutes),
                             ensure_ascii=False, indent=2))
        elif args.cmd == "stats":
            codes = [c.strip() for c in args.sources.split(",") if c.strip()]
            st = day_stats(conn, args.date, codes, args.raw_dir)
            if args.json:
                print(json.dumps(st, ensure_ascii=False, default=str))
            else:
                print(f"{st['date']}  DB 용량 {st['db_size_bytes'] / 2**20:.1f}MB")
                print("매체      기사  원문ok 제외 실패 실패율  원문적재  청크임베딩  제목요약임베딩  4종목태그")
                for code, r in st["sources"].items():
                    print(f"{code:9} {r['articles']:5} {r['raw_ok']:6} {r['raw_skipped']:4} {r['raw_failed']:4} "
                          f"{r['fail_rate'] * 100:5.1f}%  {r['bodies']:8} {r['chunks_embedded']:10} "
                          f"{r['title_embedded']:14} {r['stock_tags']:9}")
        else:
            print(json.dumps(realtime_lag(conn, args.raw_dir, limit_hours=args.hours), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
