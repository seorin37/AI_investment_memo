"""발행 → 적재 → 임베딩 시차 (DB 읽기 전용, 화면 출력만). 새 자료 기준(발행 3일 안, 검색 가능해진 시각)을 점검한다.

    PYTHONPATH=backend python -m pipelines.updates.ingest_lag --since 2026-11-01

뉴스: collected_at - published_at, 제목+요약 임베딩 embedded_at - collected_at, 원문 청크 embedded_at - collected_at.
공시: created_at - 접수일 0시(한국 시간), 청크 embedded_at - created_at. 분위수는 시간 단위.
"""

from __future__ import annotations

import argparse
from datetime import date

Q = "percentile_cont(ARRAY[0.5, 0.9, 0.99]) WITHIN GROUP (ORDER BY {x})"
HOURS = "extract(epoch FROM ({a} - {b})) / 3600"

NEWS_SQL = f"""SELECT count(*),
  {Q.format(x=HOURS.format(a="a.collected_at", b="a.published_at"))},
  max({HOURS.format(a="a.collected_at", b="a.published_at")}),
  count(*) FILTER (WHERE a.collected_at - a.published_at > interval '3 days'),
  {Q.format(x=HOURS.format(a="v.embedded_at", b="a.collected_at"))},
  count(*) FILTER (WHERE v.news_id IS NULL)
FROM news_articles a LEFT JOIN news_embedding_variants v ON v.news_id = a.id AND v.variant = %(variant)s
WHERE a.published_at >= %(since)s"""
CHUNK_SQL = f"""SELECT count(*), {Q.format(x=HOURS.format(a="c.done", b="a.collected_at"))}
FROM (SELECT news_id, max(embedded_at) AS done FROM news_chunks GROUP BY news_id) c
JOIN news_articles a ON a.id = c.news_id WHERE a.published_at >= %(since)s AND c.done IS NOT NULL"""
LATE_NEWS_SQL = """SELECT count(*) FROM (SELECT news_id, max(embedded_at) AS done FROM news_chunks GROUP BY news_id) c
JOIN news_articles a ON a.id = c.news_id WHERE a.published_at >= %(since)s AND c.done - a.published_at > interval '3 days'"""
DISC_SQL = f"""SELECT count(*),
  {Q.format(x=HOURS.format(a="d.created_at", b="(d.rcept_dt::timestamp AT TIME ZONE 'Asia/Seoul')"))},
  count(*) FILTER (WHERE d.created_at - (d.rcept_dt::timestamp AT TIME ZONE 'Asia/Seoul') > interval '3 days'),
  count(*) FILTER (WHERE (d.created_at AT TIME ZONE 'Asia/Seoul')::date - d.rcept_dt > 3),
  {Q.format(x=HOURS.format(a="c.done", b="d.created_at"))},
  count(*) FILTER (WHERE c.done IS NULL)
FROM disclosures d LEFT JOIN (SELECT rcept_no, max(embedded_at) AS done FROM disclosure_chunks GROUP BY rcept_no) c
  ON c.rcept_no = d.rcept_no
WHERE d.rcept_dt >= %(since_d)s"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="발행·적재·임베딩 시차 (DB 읽기 전용)")
    ap.add_argument("--since", default="2026-11-01")
    ap.add_argument("--variant", default="hybrid")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn

    day = date.fromisoformat(args.since)
    fmt = lambda qs: " / ".join("-" if q is None else f"{q:.1f}h" for q in (qs or [None] * 3))
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        p = {"since": f"{day} 00:00+09", "since_d": day, "variant": args.variant}
        n, pub, pub_max, late, emb, no_emb = conn.execute(NEWS_SQL, p).fetchone()
        cn, chunk = conn.execute(CHUNK_SQL, p).fetchone()
        dn, dcr, dlate, dmiss, demb, dno = conn.execute(DISC_SQL, p).fetchone()
        late_news = conn.execute(LATE_NEWS_SQL, p).fetchone()[0]
        conn.rollback()
    print(f"뉴스 {n}건 ({day}~ 발행) · 발행→적재 중앙/90%/99% {fmt(pub)} · 최대 {pub_max:.1f}h · 3일 넘게 늦게 적재 {late}건")
    print(f"  적재→제목+요약 임베딩({args.variant}) {fmt(emb)} · 임베딩 없음 {no_emb}건")
    print(f"  적재→원문 청크 임베딩(기사별 마지막) {fmt(chunk)} · 청크 임베딩 있는 기사 {cn}건")
    print(f"  원문 청크가 발행 3일 뒤에야 임베딩된 기사 {late_news}건 (chunks 모드에서 새 자료로 못 받는다)")
    print(f"공시 {dn}건 ({day}~ 접수) · 접수일 0시→적재 {fmt(dcr)} · 3일(72시간) 넘게 늦게 적재 {dlate}건"
          f" · 적재한 날이 접수일보다 3일 넘게 뒤라 새 자료 기준(접수일 3일 안, 날짜 단위)에서 빠지는 공시 {dmiss}건")
    print(f"  적재→청크 임베딩(마지막) {fmt(demb)} · 청크 임베딩 없음 {dno}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
