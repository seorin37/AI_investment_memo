"""뉴스 파이프라인 실행기.

  python -m backend.pipelines.news.pipeline hourly                       # RSS 수집 1회
  python -m backend.pipelines.news.pipeline hourly --embed --loop 1800   # 30분마다 수집 + 새 기사 임베딩(전체 기사)을 계속 반복
  python -m backend.pipelines.news.pipeline daily --variant hybrid       # 전날분 네이버 수집 -> 종목 태깅 -> 임베딩 -> 오래된 기사 정리
  python -m backend.pipelines.news.pipeline daily --variant hybrid --skip-embed   # 태깅/정리만 (임베딩은 각자 따로)
  python -m backend.pipelines.news.pipeline daily --date 2026-10-20      # 특정 날짜(KST) 다시 처리
설정은 .env(DATABASE_URL 또는 POSTGRES_*)에서 읽는다.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time as clock
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import naver, rss
from ..common.db import finish_run, get_dsn, load_env, start_run
from .repository import load_feeds_from_db
from .tagger import load_stocks, load_title_only, tag_window

log = logging.getLogger("pipeline")
KST, UTC = rss.KST, rss.UTC
RETENTION_DAYS = 30   # 종목 연결이 없는 기사의 보관 일수. 평가용 기사가 지워지지 않도록 넉넉히 둔다. 0이면 지우지 않는다.


def day_range(target: date):
    start = datetime.combine(target, time.min, tzinfo=KST)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


# 종목 연결도, 추적 매칭·업데이트 근거 참조도 없는 오래된 기사만 지운다.
CLEANUP_SQL = """
DELETE FROM news_articles a
WHERE a.published_at < now() - make_interval(days => %s)
  AND NOT EXISTS (SELECT 1 FROM news_stocks s WHERE s.news_id = a.id)
  AND NOT EXISTS (SELECT 1 FROM tracking_matches m WHERE m.news_id = a.id)
  AND NOT EXISTS (SELECT 1 FROM update_sources u WHERE u.news_id = a.id)
"""


def cleanup(conn, days: int = RETENTION_DAYS) -> int:
    """오래된 기사를 지운다. 기사를 지우면 그 기사의 임베딩도 함께 지워진다. days가 0 이하면 아무것도 지우지 않는다."""
    if days <= 0:
        return 0
    with conn.cursor() as cur:
        cur.execute(CLEANUP_SQL, (days,))
        return cur.rowcount


class LazyEncoder:
    """처음 필요할 때 한 번만 BGE-M3를 불러 오고, 이후에는 같은 모델을 재사용한다."""

    def __init__(self, variant: str):
        self.variant = variant
        self._encode = None

    def __call__(self, texts):
        if self._encode is None:
            from .embedder import make_bge_m3_encoder
            self._encode = make_bge_m3_encoder(self.variant)
        return self._encode(texts)


def embed_recent(dsn: str, encoder, variant: str, days: int, stocks_path: Path) -> int:
    """최근 days일 발행분 중 아직 처리하지 않은 기사를 태깅하고 임베딩한다.

    홈 위젯은 이 단계와 무관하게 news_articles를 바로 읽는다. 임베딩 대상은 종목 태그와
    상관없이 전체 기사이고, 종목 태깅은 참고용 표시로만 남긴다.
    """
    import psycopg
    from .embedder import embed_window
    until = datetime.now(UTC) + timedelta(hours=1)   # 발행 시각이 약간 앞선 기사도 포함
    since = until - timedelta(days=days)
    with psycopg.connect(dsn, autocommit=True) as conn:
        scanned, links = tag_window(conn, load_stocks(stocks_path), since, until, load_title_only(stocks_path))
        embedded = embed_window(conn, variant, encoder, since, until, include_untagged=True)
    log.info("태깅: 훑은 기사 %d건, 새 연결 %d건 / 임베딩(%s): %d건", scanned, links, variant, embedded)
    return embedded


def run_hourly(dsn: str, embed: bool = False, variant: str = "hybrid", embed_days: int = 3,
               stocks_path: Path | None = None, encoder=None) -> int:
    rc = _collect_rss(dsn)
    if embed:
        # 임베딩이 실패해도 수집한 기사는 이미 저장돼 있고, 홈 위젯에는 영향이 없다.
        try:
            embed_recent(dsn, encoder or LazyEncoder(variant), variant, embed_days,
                         stocks_path or Path(__file__).with_name("stocks.yaml"))
        except Exception:
            log.exception("임베딩 실패. 수집한 기사는 저장됐고, 다음 주기에 다시 시도합니다.")
    return rc


def loop_hourly(dsn: str, interval: int, embed: bool, variant: str, embed_days: int,
                stocks_path: Path, keep_days: int) -> int:
    """interval초마다 수집(+임베딩)을 반복한다. 모델은 한 번만 불러 온다. Ctrl+C로 멈춘다."""
    import psycopg
    encoder = LazyEncoder(variant)
    last_cleanup = None
    log.info("반복 실행 시작: %d초 간격, 임베딩 %s", interval, "켬" if embed else "끔")
    while True:
        started = clock.monotonic()
        try:
            run_hourly(dsn, embed, variant, embed_days, stocks_path, encoder)
            today = datetime.now(KST).date()
            if last_cleanup != today:   # 하루 한 번만 오래된 기사 정리
                with psycopg.connect(dsn, autocommit=True) as conn:
                    log.info("정리: %d건 삭제", cleanup(conn, keep_days))
                last_cleanup = today
        except KeyboardInterrupt:
            raise
        except Exception:
            log.exception("반복 실행 중 오류. 다음 주기에 다시 시도합니다.")
        clock.sleep(max(1.0, interval - (clock.monotonic() - started)))


def _collect_rss(dsn: str) -> int:
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        feeds = load_feeds_from_db(cur)
    if not feeds:
        log.error("news_feeds에 활성 피드가 없습니다. backend/pipelines/news/seed.sql을 적용했는지 확인하세요.")
        return 1
    articles, stats = rss.collect(feeds)
    failed = sum(1 for s in stats if s["error"])
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            run_id = start_run(cur, "news", None)
        inserted, skipped = rss.save_to_db(articles, conn)
        err = "모든 피드 실패" if failed == len(stats) else (f"실패 피드 {failed}/{len(stats)}" if failed else None)
        with conn.cursor() as cur:
            finish_run(cur, run_id, len(articles), err)
    log.info("수집 %d건 중 신규 %d건, 실패 피드 %d/%d", len(articles), inserted, failed, len(stats))
    return 1 if failed == len(stats) else 0


def run_daily(dsn: str, target: date, variant: str, skip_embed: bool, stocks_path: Path,
              skip_naver: bool = False, include_untagged: bool = False,
              keep_days: int = RETENTION_DAYS) -> int:
    import psycopg
    since, until = day_range(target)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            run_id = start_run(cur, "news", target)
        try:
            if not skip_naver:
                res = naver.run_naver(conn, since, until)
                log.info("네이버 수집: %s", res)
            scanned, links = tag_window(conn, load_stocks(stocks_path), since, until, load_title_only(stocks_path))
            log.info("태깅: 훑은 기사 %d건, 새 연결 %d건", scanned, links)
            embedded = 0
            if not skip_embed:
                from .embedder import embed_window, make_bge_m3_encoder
                embedded = embed_window(conn, variant, make_bge_m3_encoder(variant), since, until,
                                        include_untagged=include_untagged)
                log.info("임베딩(%s): %d건", variant, embedded)
            removed = cleanup(conn, keep_days)
            log.info("정리: %d건 삭제", removed)
        except Exception as exc:
            with conn.cursor() as cur:
                finish_run(cur, run_id, 0, f"{type(exc).__name__}: {exc}")
            raise
        with conn.cursor() as cur:
            finish_run(cur, run_id, embedded or links)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["hourly", "daily"])
    ap.add_argument("--variant", choices=["dense", "hybrid"], default="hybrid")
    ap.add_argument("--date", type=date.fromisoformat, help="처리할 날짜(KST). 기본: 어제")
    ap.add_argument("--skip-embed", action="store_true")
    ap.add_argument("--skip-naver", action="store_true", help="네이버 API 수집 단계를 건너뜀")
    ap.add_argument("--include-untagged", action="store_true",
                    help="종목이 연결되지 않은 기사도 임베딩한다 (평가용 후보 풀을 넓힐 때)")
    ap.add_argument("--stocks", type=Path, default=Path(__file__).with_name("stocks.yaml"))
    ap.add_argument("--embed", action="store_true",
                    help="hourly: 수집 직후 최근 기사 중 임베딩이 없는 것을 모두 임베딩한다 (홈 위젯과 무관)")
    ap.add_argument("--embed-days", type=int, default=3, help="hourly --embed가 훑을 최근 일수 (기본 3)")
    ap.add_argument("--loop", type=int, metavar="SECONDS",
                    help="hourly: 이 간격(초)으로 계속 반복한다. 모델을 한 번만 불러 온다 (예: 1800)")
    ap.add_argument("--keep-days", type=int, default=RETENTION_DAYS,
                    help=f"종목 연결이 없는 기사를 보관할 일수 (기본 {RETENTION_DAYS}). hourly --loop과 daily 모두에 적용. "
                         "0이면 정리하지 않는다 (평가용 기사를 지키고 싶을 때)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
    if args.job == "hourly":
        if args.loop:
            try:
                return loop_hourly(dsn, args.loop, args.embed, args.variant, args.embed_days,
                                   args.stocks, args.keep_days)
            except KeyboardInterrupt:
                log.info("반복 실행을 멈췄습니다.")
                return 0
        return run_hourly(dsn, args.embed, args.variant, args.embed_days, args.stocks)
    target = args.date or (datetime.now(KST).date() - timedelta(days=1))
    return run_daily(dsn, target, args.variant, args.skip_embed, args.stocks, args.skip_naver,
                     args.include_untagged, args.keep_days)


if __name__ == "__main__":
    sys.exit(main())
