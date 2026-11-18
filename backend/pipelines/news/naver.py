"""네이버 뉴스 검색 API(NAVER API HUB) 수집기.

종목별 검색어로 기사를 불러와 news_articles에 적재하고 news_stocks로 종목을 연결한다. (스키마 v1.2)
- 검색어(query)가 필수라서 종목 이름 단위로만 수집할 수 있다. (전 섹션 수집은 불가)
- 종목은 검색어에서 이미 정해지므로 news_stocks에 바로 연결한다.
- 응답에 매체명이 없어 원문 URL 도메인으로 news_sources.code를 정한다. 4개 매체 밖 기사는 저장하지 않는다.
- 원문은 저장하지 않는다. 제목, 제공 요약(description), 링크, 발행일시만 저장한다.

환경변수:
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET   (.env는 Git에 커밋하지 않는다)
    NAVER_API_BASE_URL                     (기본값은 문서의 예시 호스트)
    DATABASE_URL                           (dry-run이 아닐 때)

사용 예:
    python -m backend.pipelines.news.naver --dry-run            # 전날 기사, DB 쓰기 없이 확인
    python -m backend.pipelines.news.naver --hours 3            # 최근 3시간 기사
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator
from urllib.parse import urlsplit

import requests
import yaml

from .rss import (
    KST, SUMMARY_MAX_CHARS, UTC, Article, clean_text, normalize_url,
    parse_published, yesterday_range_kst,
)
from ..common.db import finish_run, get_dsn, load_env, start_run
from .repository import content_hash, source_ids

log = logging.getLogger("naver_collector")

DEFAULT_BASE_URL = "https://naverapihub.apigw.ntruss.com"  # 문서의 '예시 호스트'
SEARCH_PATH = "/search/v1/news"
PAGE_SIZE = 100   # display 최대값
MAX_START = 1000  # start 최대값
REQUEST_TIMEOUT = 15
RETRIES = 3

FetchFn = Callable[[str, int], dict]


class NaverApiError(RuntimeError):
    pass


@dataclass
class StockArticle:
    article: Article
    stock_codes: set[str] = field(default_factory=set)


# ---------------------------------------------------------------- API 호출

def make_fetcher(client_id: str, client_secret: str, base_url: str = DEFAULT_BASE_URL) -> FetchFn:
    session = requests.Session()
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }

    def fetch(query: str, start: int) -> dict:
        params = {"query": query, "display": PAGE_SIZE, "start": start, "sort": "date"}
        last_error: Exception | None = None
        for attempt in range(1, RETRIES + 1):
            try:
                resp = session.get(base_url.rstrip("/") + SEARCH_PATH, params=params,
                                   headers=headers, timeout=REQUEST_TIMEOUT)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if resp.status_code == 200:
                    return resp.json()
                last_error = NaverApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code < 500:  # 4xx는 재시도해도 같으므로 바로 중단
                    raise last_error
            time.sleep(attempt)
        raise NaverApiError(f"재시도 {RETRIES}회 실패: {last_error}")

    return fetch


# ---------------------------------------------------------------- 변환

def publisher_for(url: str, publishers: dict[str, str]) -> tuple[str, bool]:
    """(매체 코드, 목록에 있는 매체인지)를 돌려준다. 없으면 도메인을 돌려준다."""
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    for domain, name in publishers.items():
        if host == domain or host.endswith("." + domain):
            return name, True
    return host, False


def mentions(text: str, aliases: list[str]) -> bool:
    lowered = text.casefold()
    return any(alias.casefold() in lowered for alias in aliases)


def parse_item(item: dict, aliases: list[str], publishers: dict[str, str],
               only_listed: bool = False, title_only: bool = False) -> Article | None:
    """검색 결과 한 건을 Article로 바꾼다. 부적합하면 None."""
    title = clean_text(item.get("title"))
    description = clean_text(item.get("description"), SUMMARY_MAX_CHARS)
    url = (item.get("originallink") or item.get("link") or "").strip()
    published_at = parse_published(item.get("pubDate"))
    if not title or not url or published_at is None:
        return None
    if not mentions(title if title_only else f"{title} {description or ''}", aliases):
        return None  # 검색어와 무관하게 걸린 기사
    publisher, listed = publisher_for(url, publishers)
    if only_listed and not listed:
        return None
    return Article(
        source_code=publisher, publisher=publisher, section=None, title=title,
        summary=description, url=url, url_norm=normalize_url(url),
        published_at=published_at, content_hash=content_hash(publisher, title),
    )


# ---------------------------------------------------------------- 수집

def iter_query_items(query: str, since: datetime, fetch: FetchFn) -> Iterator[dict]:
    """sort=date 내림차순으로 페이지를 넘기며 since보다 오래된 구간에 닿으면 멈춘다."""
    start = 1
    while start <= MAX_START:
        items = (fetch(query, start) or {}).get("items") or []
        if not items:
            return
        yield from items
        dates = [d for d in (parse_published(i.get("pubDate")) for i in items) if d]
        if dates and min(dates) < since:
            return
        if len(items) < PAGE_SIZE:
            return
        start += PAGE_SIZE


def collect(stocks: list[dict], since: datetime, until: datetime, fetch: FetchFn,
            publishers: dict[str, str], only_listed: bool = False
            ) -> tuple[list[StockArticle], list[dict]]:
    """종목별 검색어로 수집하고, 같은 기사는 하나로 합쳐 종목 코드를 모은다."""
    merged: dict[str, StockArticle] = {}
    stats: list[dict] = []
    for stock in stocks:
        for query in stock["queries"]:
            stat = {"stock": stock["name"], "query": query, "fetched": 0, "kept": 0, "error": None}
            try:
                for item in iter_query_items(query, since, fetch):
                    stat["fetched"] += 1
                    art = parse_item(item, stock["aliases"], publishers, only_listed, stock.get("title_only", False))
                    if art is None or not (since <= art.published_at < until):
                        continue
                    stat["kept"] += 1
                    entry = merged.setdefault(art.url_norm, StockArticle(art))
                    entry.stock_codes.add(stock["code"])
            except Exception as exc:  # 한 검색어 실패가 전체를 막지 않게 한다
                stat["error"] = f"{type(exc).__name__}: {exc}"
                log.error("검색 실패 %s/%s: %s", stock["name"], query, exc)
            stats.append(stat)
    return list(merged.values()), stats


# ---------------------------------------------------------------- DB 적재

# url 또는 content_hash가 겹치면 건너뛰고(RSS로 먼저 들어온 기사 등), 기존 행의 id로 종목만 연결한다.
INSERT_SQL = """
INSERT INTO news_articles
    (source_id, url, title, summary, section, content_hash, published_at)
VALUES
    (%(source_id)s, %(url_norm)s, %(title)s, %(summary)s, %(section)s,
     %(content_hash)s, %(published_at)s)
ON CONFLICT DO NOTHING
RETURNING id
"""
FIND_SQL = "SELECT id FROM news_articles WHERE url = %s OR content_hash = %s LIMIT 1"
LINK_SQL = """
INSERT INTO news_stocks (news_id, symbol) VALUES (%s, %s)
ON CONFLICT DO NOTHING
"""


def save_to_db(items: list[StockArticle], conn) -> tuple[int, int, int]:
    """(신규 기사 수, 신규 종목 연결 수, 매체 미등록으로 건너뛴 수)."""
    new_articles = new_links = skipped = 0
    with conn.cursor() as cur:
        ids = source_ids(cur)
        for item in items:
            art = item.article
            sid = ids.get(art.source_code)
            if sid is None:
                skipped += 1
                continue
            row = asdict(art)
            row["source_id"] = sid
            cur.execute(INSERT_SQL, row)
            found = cur.fetchone()
            if found:
                news_id = found[0]
                new_articles += 1
            else:
                cur.execute(FIND_SQL, (art.url_norm, art.content_hash))
                news_id = cur.fetchone()[0]
            for code in sorted(item.stock_codes):
                cur.execute(LINK_SQL, (news_id, code))
                new_links += cur.rowcount
    return new_articles, new_links, skipped


def run_naver(conn, since: datetime, until: datetime, config_path: Path | None = None,
              fetch: FetchFn | None = None) -> dict:
    """[since, until) 기사를 수집해 DB에 넣는다. daily 파이프라인에서 쓴다.

    fetch를 안 주면 환경변수(NAVER_CLIENT_ID/SECRET)로 실제 API를 부른다.
    """
    config = yaml.safe_load((config_path or Path(__file__).with_name("naver_queries.yaml"))
                            .read_text(encoding="utf-8"))
    if fetch is None:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not (client_id and client_secret):
            raise NaverApiError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 없습니다.")
        fetch = make_fetcher(client_id, client_secret, os.environ.get("NAVER_API_BASE_URL", DEFAULT_BASE_URL))
    items, stats = collect(config["stocks"], since, until, fetch,
                           config.get("publishers", {}), config.get("only_listed_publishers", True))
    failed = sum(1 for s in stats if s["error"])
    if stats and failed == len(stats):
        raise NaverApiError("모든 검색어 실패: " + "; ".join(s["error"] for s in stats if s["error"])[:300])
    new_articles, new_links, skipped = save_to_db(items, conn)
    return {"collected": len(items), "new_articles": new_articles, "new_links": new_links,
            "skipped_source": skipped, "failed_queries": failed, "queries": len(stats)}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="네이버 뉴스 검색 API 수집기")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("naver_queries.yaml"))
    parser.add_argument("--hours", type=float, help="최근 N시간 기사만 수집 (기본: 전날 KST 하루)")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 결과만 출력")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not (client_id and client_secret):
        log.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 필요합니다.")
        return 1

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.hours:
        until = datetime.now(UTC)
        since = until - timedelta(hours=args.hours)
    else:
        since, until = yesterday_range_kst()

    fetch = make_fetcher(client_id, client_secret,
                         os.environ.get("NAVER_API_BASE_URL", DEFAULT_BASE_URL))
    items, stats = collect(config["stocks"], since, until, fetch,
                           config.get("publishers", {}), config.get("only_listed_publishers", True))

    for s in stats:
        log.info("%s / %r: 조회 %d건, 보관 %d건%s", s["stock"], s["query"], s["fetched"], s["kept"],
                 f", 오류 {s['error']}" if s["error"] else "")
    failed = sum(1 for s in stats if s["error"])
    log.info("합쳐서 %d건 (실패 검색어 %d/%d)", len(items), failed, len(stats))
    if failed == len(stats):
        return 1
    if args.dry_run:
        return 0

    dsn = get_dsn()
    if not dsn:
        log.error("DATABASE_URL 환경변수가 없습니다.")
        return 1
    import psycopg
    target = (since.astimezone(KST).date() if not args.hours else None)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            run_id = start_run(cur, "news", target)
        try:
            with conn.transaction():
                new_articles, new_links, skipped = save_to_db(items, conn)
        except Exception as exc:
            with conn.cursor() as cur:
                finish_run(cur, run_id, 0, f"{type(exc).__name__}: {exc}")
            raise
        with conn.cursor() as cur:
            finish_run(cur, run_id, len(items), f"실패 검색어 {failed}/{len(stats)}" if failed else None)
    log.info("DB 적재: 신규 기사 %d건, 신규 종목 연결 %d건, 매체 미등록 %d건",
             new_articles, new_links, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
