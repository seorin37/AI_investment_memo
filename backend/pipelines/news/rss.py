"""4개 매체 RSS 폴링 수집기.

30분마다 실행해 매체별 전체뉴스 기사를 news_articles에 적재한다.
- 발행일시는 KST 기준으로 해석한 뒤 UTC로 저장한다 (타임존 없는 값은 KST로 간주).
- URL을 정규화해 news_articles.url(UNIQUE)로 중복을 막는다.
- 피드 하나가 실패해도 나머지는 계속 수집한다.
- 원문은 저장하지 않는다. 제목, 제공 요약, 링크, 발행일시만 저장한다.

사용 예:
    python -m backend.pipelines.news.rss --dry-run                 # DB 없이 수집 결과만 확인
    python -m backend.pipelines.news.rss   # DB 적재
"""

from __future__ import annotations

import argparse
import html
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml

from ..common.db import finish_run, get_dsn, load_env, start_run
from .repository import content_hash, load_feeds_from_db, source_ids

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
log = logging.getLogger("news_collector")

USER_AGENT = "memos-news-collector/0.1 (+student project; RSS reader)"
REQUEST_TIMEOUT = 15  # seconds
SUMMARY_MAX_CHARS = 1000

# 추적용 파라미터는 같은 기사를 다른 URL로 보이게 하므로 제거한다.
TRACKING_PARAMS = {
    "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "referrer",
    "from", "source", "spm", "cmpid", "rss", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content",
}

_TAG_RE = re.compile(r"<[^>]+>")
# 글자 사이에 끼는 강조 태그(<b>삼성전자</b>가)는 공백 없이 지운다. 안 그러면 "삼성전자 가"로 갈라진다.
_INLINE_TAG_RE = re.compile(r"</?(?:b|strong|em|i|u|mark|span|a|font)\b[^>]*>", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_TITLE_KEY_RE = re.compile(r"[\W_]+", re.UNICODE)


@dataclass
class Article:
    source_code: str     # news_sources.code (예: hankyung)
    publisher: str       # 매체명 (표시·제목 중복 키용, DB에는 저장하지 않음)
    section: str | None
    title: str
    summary: str | None
    url: str
    url_norm: str        # DB의 url 컬럼에 저장되는 정규화 URL
    published_at: datetime  # tz-aware UTC
    content_hash: str = ""


# ---------------------------------------------------------------- 정규화 유틸

def normalize_url(url: str) -> str:
    """같은 기사가 같은 키가 되도록 URL을 정규화한다."""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"
    host = parts.netloc.lower()
    if host.startswith("m."):  # 모바일 도메인 통일은 매체별 규칙이 다르므로 m.만 처리
        host = host[2:]
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    )
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def clean_text(value: str | None, max_chars: int | None = None) -> str | None:
    """HTML 태그 제거, 엔티티 해제, 공백 정리."""
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", _INLINE_TAG_RE.sub("", value)))
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return None
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def title_key(publisher: str, title: str) -> str:
    """같은 매체의 같은 제목(공백·기호만 다른 경우 포함)을 한 기사로 보기 위한 키."""
    return f"{publisher}|{_TITLE_KEY_RE.sub('', title).casefold()}"


# ---------------------------------------------------------------- 시간 처리

def parse_published(raw: str | None) -> datetime | None:
    """발행일시 문자열을 UTC datetime으로 변환한다.

    - RFC822 형식('Tue, 20 Oct 2026 09:05:00 +0900')은 표기된 타임존을 따른다.
    - 타임존이 없거나 알 수 없으면 KST로 간주한다.
    """
    if not raw:
        return None
    raw = raw.strip()
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(UTC)


def yesterday_range_kst(now: datetime | None = None) -> tuple[datetime, datetime]:
    """전날 00:00:00 ~ 오늘 00:00:00(미포함)을 KST 기준 UTC 구간으로 돌려준다.

    종목 태깅·임베딩 일 배치가 '전날분'을 고를 때 사용한다.
    """
    now_kst = (now or datetime.now(UTC)).astimezone(KST)
    today: date = now_kst.date()
    start = datetime.combine(today - timedelta(days=1), time.min, tzinfo=KST)
    end = datetime.combine(today, time.min, tzinfo=KST)
    return start.astimezone(UTC), end.astimezone(UTC)


# ---------------------------------------------------------------- 피드 처리

def load_feeds(path: Path, include_unverified: bool = False,
               publishers: set[str] | None = None) -> list[dict]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    feeds: list[dict] = []
    for key, entry in config.items():
        if publishers and key not in publishers:
            continue
        for feed in entry.get("feeds") or []:
            if not feed.get("verified") and not include_unverified:
                log.warning("건너뜀(미확인 피드): %s %s", entry["publisher"], feed["section"])
                continue
            feeds.append({
                "source_code": entry.get("code", key),
                "publisher": entry["publisher"],
                "section": feed["section"],
                "url": feed["url"],
            })
    return feeds


def fetch_feed(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def parse_feed(content: bytes | str, publisher: str, section: str | None,
               source_code: str = "") -> list[Article]:
    """피드 내용을 Article 목록으로 변환한다. 필수 값이 없는 항목은 버린다."""
    parsed = feedparser.parse(content)
    articles: list[Article] = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title"))
        link = (entry.get("link") or "").strip()
        raw_date = entry.get("published") or entry.get("updated") or entry.get("pubDate")
        published_at = parse_published(raw_date)
        if not title or not link or published_at is None:
            log.debug("필수 값 누락으로 제외: %r", entry.get("title"))
            continue
        articles.append(Article(
            source_code=source_code,
            publisher=publisher,
            section=section,
            title=title,
            summary=clean_text(entry.get("summary") or entry.get("description"), SUMMARY_MAX_CHARS),
            url=link,
            url_norm=normalize_url(link),
            published_at=published_at,
            content_hash=content_hash(source_code, title),
        ))
    return articles


def dedupe(articles: list[Article]) -> list[Article]:
    """한 번의 수집 안에서 URL과 제목 기준으로 중복을 제거한다.

    같은 기사가 여러 섹션 피드에 동시에 실리므로, 처음 나온 것만 남긴다.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Article] = []
    for art in articles:
        tkey = title_key(art.publisher, art.title)
        if art.url_norm in seen_urls or tkey in seen_titles:
            continue
        seen_urls.add(art.url_norm)
        seen_titles.add(tkey)
        unique.append(art)
    return unique


def collect(feeds: list[dict]) -> tuple[list[Article], list[dict]]:
    """모든 피드를 수집한다. 피드별 결과(stats)도 함께 돌려준다."""
    all_articles: list[Article] = []
    stats: list[dict] = []
    for feed in feeds:
        stat = {"publisher": feed["publisher"], "section": feed["section"],
                "url": feed["url"], "entries": 0, "error": None, "newest": None}
        try:
            articles = parse_feed(fetch_feed(feed["url"]), feed["publisher"], feed["section"],
                                   feed.get("source_code", ""))
            stat["entries"] = len(articles)
            if articles:
                stat["newest"] = max(a.published_at for a in articles).astimezone(KST).isoformat()
            all_articles.extend(articles)
        except Exception as exc:  # 한 피드 실패가 전체를 막지 않게 한다
            stat["error"] = f"{type(exc).__name__}: {exc}"
            log.error("피드 수집 실패 %s/%s: %s", feed["publisher"], feed["section"], exc)
        stats.append(stat)
    return dedupe(all_articles), stats


# ---------------------------------------------------------------- DB 적재

INSERT_SQL = """
INSERT INTO news_articles
    (source_id, url, title, summary, section, content_hash, published_at)
VALUES
    (%(source_id)s, %(url_norm)s, %(title)s, %(summary)s, %(section)s,
     %(content_hash)s, %(published_at)s)
ON CONFLICT DO NOTHING
"""


def save_to_db(articles: list[Article], conn) -> tuple[int, int]:
    """(신규 건수, 매체 코드를 몰라 건너뛴 건수). url·content_hash 중복은 조용히 건너뛴다."""
    inserted = skipped = 0
    with conn.cursor() as cur:
        ids = source_ids(cur)
        for art in articles:
            sid = ids.get(art.source_code)
            if sid is None:
                skipped += 1
                continue
            row = asdict(art)
            row["source_id"] = sid
            cur.execute(INSERT_SQL, row)
            inserted += cur.rowcount
    return inserted, skipped


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="4개 매체 RSS 수집기")
    parser.add_argument("--db-feeds", action="store_true",
                        help="feeds.yaml 대신 DB의 news_feeds(enabled)를 사용")
    parser.add_argument("--feeds", type=Path, default=Path(__file__).with_name("feeds.yaml"))
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 결과만 출력")
    parser.add_argument("--include-unverified", action="store_true",
                        help="주소 미확인 피드도 호출해 응답을 확인한다")
    parser.add_argument("--publishers", help="쉼표로 구분한 매체 키(예: hankyung,mk)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    import psycopg
    dsn = get_dsn()
    publishers = set(args.publishers.split(",")) if args.publishers else None
    if args.db_feeds:
        if not dsn:
            log.error("--db-feeds에는 DATABASE_URL이 필요합니다.")
            return 1
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            feeds = load_feeds_from_db(cur)
    else:
        feeds = load_feeds(args.feeds, args.include_unverified, publishers)
    if not feeds:
        log.error("수집할 피드가 없습니다.")
        return 1

    articles, stats = collect(feeds)

    for s in stats:
        status = s["error"] or f"{s['entries']}건, 최신 {s['newest']}"
        log.info("%s/%s: %s", s["publisher"], s["section"], status)

    failed = sum(1 for s in stats if s["error"])
    log.info("중복 제거 후 %d건, 실패 피드 %d/%d", len(articles), failed, len(stats))

    if args.dry_run:
        return 0 if failed < len(stats) else 1

    if not dsn:
        log.error("DATABASE_URL 환경변수가 없습니다. (.env는 Git에 커밋하지 않는다)")
        return 1
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            run_id = start_run(cur, "news", None)
        try:
            inserted, skipped = save_to_db(articles, conn)
            err = None if failed < len(stats) else "모든 피드 실패"
        except Exception as exc:
            with conn.cursor() as cur:
                finish_run(cur, run_id, 0, f"{type(exc).__name__}: {exc}")
            raise
        with conn.cursor() as cur:
            finish_run(cur, run_id, len(articles), err)
    log.info("DB 적재: 신규 %d건 / 수집 %d건 (매체 미등록 %d건)", inserted, len(articles), skipped)
    return 0 if failed < len(stats) else 1


if __name__ == "__main__":
    sys.exit(main())
