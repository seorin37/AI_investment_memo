"""과거 뉴스 목록 백필 (한국경제·매일경제): 날짜별 사이트맵 → 기사 페이지 메타 → news_articles.

  python -m backend.pipelines.news.backfill_list --date 2026-10-27 --dry-run --limit 5     # 메타 확인만 (DB 쓰기 없음)
  python -m backend.pipelines.news.backfill_list --date 2026-10-27 --dsn-env TEST_DATABASE_URL --limit 10
  python -m backend.pipelines.news.backfill_list --date 2026-10-27                          # 공용 DB (.env DATABASE_URL)
  python -m backend.pipelines.news.backfill_list --date 2026-11-11 --allow-recent            # 실시간 수집 공백 채우기

- 사이트맵: 한경 /sitemap/daily-article/YYYYMMDD.xml, 매경 /sitemap/daily-articles/YYYYMMDD (loc만 쓴다).
  날짜 사이트맵에 다른 날짜 ID의 기사도 섞여 있어, 기사 페이지의 발행 시각(KST)이 --date인 기사만 저장한다.
  (2026-11-12 확인: D+1 사이트맵의 옛 ID 기사 6건은 모두 D+1 발행이라 D+1 사이트맵은 읽지 않는다)
- 기사 페이지에서 제목(og:title), 발행 시각(article:published_time → JSON-LD datePublished …), 요약(og:description),
  섹션(한경 meta article:section, 매경 URL 경로 /news/<섹션>/)을 뽑는다. 저장은 rss.save_to_db 그대로라
  URL(UNIQUE)·content_hash 중복은 조용히 건너뛴다. DB에 이미 있는 URL은 페이지를 요청하지도 않는다.
- 요청 규칙: 수집기 User-Agent, robots.txt 확인, 같은 호스트 사이 lead_sources.yaml request_interval_seconds(4초),
  일시 오류(타임아웃·5xx)는 max_attempts회까지 재시도, 403·429면 그 매체를 멈춘다(종료 코드 3).
- 06:00~07:30 KST에는 요청을 멈추고 기다린다 (06:30 AI 업데이트와 겹치지 않게).
- 페이지 50건마다 실시간 원문 임베딩 지연을 확인한다 (backfill_check.realtime_lag, 공용 DB 읽기만):
  최근 2일 발행분 중 원문을 받은 지 2시간 넘었는데 청크가 없는 기사가 있으면 멈춘다(종료 코드 4).
- 원문(2026-11-12): 받은 기사 페이지로 원문 기록도 <raw-dir>/<발행일>.jsonl에 fulltext와 같은 형식·판정(record_from_page)으로
  쓴다 (공용 DB 저장일 때만, --no-body로 끔). 그래서 뒤의 fulltext --date는 '본문 비어 있음' 같은 실패분만 다시 받는다.
- 진행 기록: <state-dir>/progress.json (매체·날짜별 상태와 건수), 실패 URL: <state-dir>/failures_<날짜>.jsonl.
  status done인 날짜는 다시 돌려도 건너뛴다 (--force면 다시). --dry-run은 진행 기록·실패 파일을 쓰지 않는다.
- 2026-10-28 이후 날짜는 실시간 수집 구간이라 기본 거부, --allow-recent를 줘야 한다.

종료 코드: 0 정상 / 1 오류 / 2 거부(날짜·설정) / 3 403·429로 매체 중단 / 4 실시간 임베딩 지연으로 중단
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import logging
import os
import re
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from . import fulltext as ft
from . import lead_fetcher as lf
from .repository import content_hash
from .rss import KST, SUMMARY_MAX_CHARS, UTC, Article, clean_text, normalize_url, parse_published

log = logging.getLogger("backfill_list")

SOURCES = {
    "hankyung": {"publisher": "한국경제", "host": "www.hankyung.com",
                 "sitemap": "https://www.hankyung.com/sitemap/daily-article/{ymd}.xml",
                 "path_re": re.compile(r"^/article/[0-9A-Za-z]+$")},
    "mk": {"publisher": "매일경제", "host": "www.mk.co.kr",
           "sitemap": "https://www.mk.co.kr/sitemap/daily-articles/{ymd}",
           "path_re": re.compile(r"^/news/([a-z0-9-]+)/\d+$")},
}
RECENT_FROM = date(2026, 10, 28)       # 이 날짜부터는 실시간 수집 구간 (--allow-recent 필요)
PAUSE_START, PAUSE_END = dtime(6, 0), dtime(7, 30)
LAG_EVERY = 50                          # 페이지 이만큼마다 실시간 임베딩 지연 확인
SAVE_EVERY = 20                         # 저장할 기사가 이만큼 모이면 DB에 쓴다 (중간에 멈춰도 남게)
STATE_DIR = Path("data/news_backfill")
EXIT_OK, EXIT_ERROR, EXIT_REFUSED, EXIT_BLOCKED, EXIT_LAG = 0, 1, 2, 3, 4

_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.IGNORECASE)
_TITLE_SUFFIX_RE = re.compile(r"\s*[-|ㅣ]\s*(매일경제|한국경제|한경닷컴|한경)\s*$")
# 한경 og:description = "제목, (부제…), 기자명 기자, 섹션" — 앞의 제목과 끝의 기자·섹션 꼬리를 뗀다
_HK_TAIL_RE = re.compile(r"(?:,\s*)?[가-힣A-Za-z·\s]{1,25}\s?기자(?:,\s*[^,]{1,20})?\s*$")


# ---------------------------------------------------------------- 사이트맵·메타 추출 (네트워크 없음)

def sitemap_url(code: str, day: date) -> str:
    return SOURCES[code]["sitemap"].format(ymd=day.strftime("%Y%m%d"))


def parse_sitemap(xml_text: str) -> list[str]:
    """<loc> 목록 (순서 유지, 중복 제거)."""
    seen, out = set(), []
    for loc in _LOC_RE.findall(xml_text or ""):
        url = htmllib.unescape(loc).strip()
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def article_section_from_url(code: str, url: str) -> str | None:
    m = SOURCES[code]["path_re"].match(urlsplit(url).path)
    return m.group(1) if (m and m.groups()) else None


def candidate_urls(code: str, locs: list[str], sections: set[str] | None = None) -> list[str]:
    """기사 URL만 (호스트·경로 규칙). sections가 있으면 매경 URL 경로 섹션으로 거른다."""
    spec = SOURCES[code]
    out = []
    for url in locs:
        parts = urlsplit(url)
        if parts.netloc.lower() != spec["host"] or not spec["path_re"].match(parts.path):
            continue
        if sections and code == "mk" and article_section_from_url(code, url) not in sections:
            continue
        out.append(url)
    return out


def _unescape(text: str | None) -> str | None:
    if text is None:
        return None
    for _ in range(2):                     # 한경 og:description은 &amp;middot;처럼 두 번 이스케이프된 경우가 있다
        new = htmllib.unescape(text)
        if new == text:
            break
        text = new
    return text


def _meta(soup, *, prop: str | None = None, name: str | None = None, itemprop: str | None = None) -> str | None:
    attrs = {"property": prop} if prop else {"name": name} if name else {"itemprop": itemprop}
    node = soup.find("meta", attrs=attrs)
    value = node.get("content") if node else None
    return value.strip() if value and value.strip() else None


def _jsonld_values(soup, key: str) -> list[str]:
    """JSON-LD 블록 안의 key 값들 (중첩·배열 포함). 깨진 JSON은 정규식으로 찾는다."""
    found: list[str] = []

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == key and isinstance(v, str):
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text() or ""
        try:
            walk(json.loads(text))
        except ValueError:
            found += re.findall(rf'"{key}"\s*:\s*"([^"]+)"', text)
    return found


def clean_title(raw: str | None) -> str | None:
    text = clean_text(_unescape(raw))
    if not text:
        return None
    return _TITLE_SUFFIX_RE.sub("", text).strip() or None


def clean_summary(code: str, raw: str | None, title: str | None) -> str | None:
    text = clean_text(_unescape(raw))
    if not text:
        return None
    if code == "hankyung":
        if title and text.startswith(title):
            text = text[len(title):].lstrip(" ,")
        text = _HK_TAIL_RE.sub("", text).strip(" ,")
    if not text or (title and text == title):
        return None
    return text[:SUMMARY_MAX_CHARS].rstrip()


@dataclass
class PageMeta:
    title: str | None
    published_at: datetime | None      # UTC
    summary: str | None
    section: str | None
    published_raw: str | None = None


def extract_meta(code: str, url: str, page_html: str) -> PageMeta:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "lxml")
    title = clean_title(_meta(soup, prop="og:title") or (soup.title.get_text() if soup.title else None))
    raw_pub = (_meta(soup, prop="article:published_time") or _meta(soup, name="article:published_time")
               or _meta(soup, itemprop="datePublished") or next(iter(_jsonld_values(soup, "datePublished")), None)
               or _meta(soup, name="pubdate") or _meta(soup, prop="og:article:published_time"))
    published = parse_published(raw_pub) if raw_pub and re.search(r"\d{1,2}:\d{2}", raw_pub) else None
    summary = clean_summary(code, _meta(soup, prop="og:description") or _meta(soup, name="description"), title)
    if code == "mk":
        section = article_section_from_url(code, url) or _meta(soup, prop="article:section")
    else:
        section = _meta(soup, prop="article:section")
    return PageMeta(title, published, summary, section, raw_pub)


def to_article(code: str, url: str, meta: PageMeta) -> Article:
    return Article(source_code=code, publisher=SOURCES[code]["publisher"], section=meta.section, title=meta.title,
                   summary=meta.summary, url=url, url_norm=normalize_url(url), published_at=meta.published_at,
                   content_hash=content_hash(code, meta.title))


def kst_date(dt: datetime) -> date:
    return dt.astimezone(KST).date()


# ---------------------------------------------------------------- 정지 시간·진행 기록

def in_pause(now_kst: datetime) -> bool:
    return PAUSE_START <= now_kst.timetz().replace(tzinfo=None) < PAUSE_END


def seconds_until_resume(now_kst: datetime) -> float:
    end = datetime.combine(now_kst.date(), PAUSE_END, tzinfo=KST)
    return max(1.0, (end - now_kst).total_seconds())


class Progress:
    """progress.json: {매체: {날짜: {status, 건수…, updated_at}}}. 스레드 사이 잠금, 임시 파일로 바꿔 쓴다."""

    def __init__(self, path: Path, enabled: bool = True):
        self.path, self.enabled = path, enabled
        self.lock = threading.Lock()
        self.data: dict = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}

    def status(self, code: str, day: date) -> str | None:
        return (self.data.get(code, {}).get(day.isoformat()) or {}).get("status")

    def update(self, code: str, day: date, status: str, counts: dict) -> None:
        with self.lock:
            entry = {"status": status, **{k: int(v) for k, v in counts.items()},
                     "updated_at": datetime.now(KST).isoformat(timespec="seconds")}
            self.data.setdefault(code, {})[day.isoformat()] = entry
            if not self.enabled:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)


class Failures:
    def __init__(self, path: Path, enabled: bool = True):
        self.path, self.enabled, self.lock = path, enabled, threading.Lock()

    def add(self, code: str, url: str, reason: str, http_status: int | None = None) -> None:
        log.debug("실패 %s %s: %s", code, url, reason)
        if not self.enabled:
            return
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"source": code, "url": url, "reason": reason, "http_status": http_status,
                                     "at": datetime.now(KST).isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 수집 (요청·DB는 주입)

@dataclass
class Env:
    """네트워크·DB·시계를 바꿔 끼울 수 있게 모은 것 (테스트는 가짜를 넣는다)."""
    http_get: lf.HttpGet
    config: lf.LeadConfig
    existing_urls: Callable[[list[str]], set[str]]      # 정규화 URL 중 DB에 이미 있는 것
    save: Callable[[list[Article]], int] | None          # 새로 넣은 건수. None이면 dry-run
    lag_check: Callable[[], dict] | None = None          # realtime_lag 결과
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    now_kst: Callable[[], datetime] = lambda: datetime.now(KST)
    stop: threading.Event = field(default_factory=threading.Event)   # 지연으로 모든 매체를 멈출 때
    lag_lock: threading.Lock = field(default_factory=threading.Lock)
    pages_since_lag: list = field(default_factory=lambda: [0])
    lag_result: dict = field(default_factory=dict)
    bodies: "BodyWriter | None" = None                    # 받은 페이지로 원문 기록도 쓴다 (None이면 목록만)


class BodyWriter:
    """목록 단계에서 이미 받은 기사 페이지로 원문 기록을 data/news_raw/<발행일>.jsonl에 쓴다 (fulltext와 같은 형식·판정).
    news_id가 필요해 저장(save_to_db) 직후 URL로 id를 찾는다. 저장 안 된 기사(content_hash 중복)는 쓰지 않는다.
    이미 ok/skipped 기록이 있는 URL은 다시 쓰지 않는다. failed(본문 비어 있음 등)는 뒤의 fulltext 단계가 다시 받는다."""

    def __init__(self, raw_dir: Path, config: lf.LeadConfig, rows_for: Callable[[list[str]], dict[str, "ft.ArticleRow"]],
                 now: Callable[[], datetime] = lambda: datetime.now(KST)):
        self.raw_dir, self.config, self.rows_for, self.now = raw_dir, config, rows_for, now
        self.lock = threading.Lock()

    def write(self, code: str, items: list[tuple[Article, str]], stat: Counter) -> None:
        src = self.config.sources.get(code)
        if src is None or not src.can_probe or not src.selector:
            stat["body_not_ready"] += len(items)          # 원문을 받지 않는 매체 설정이면 fulltext 단계와 같이 건너뜀
            return
        version = ft.extractor_version(src)
        rows = self.rows_for([a.url_norm for a, _ in items])
        records = []
        for art, page_html in items:
            row = rows.get(art.url_norm)
            if row is None:
                stat["body_no_id"] += 1
                continue
            reason = ft.precheck_reason(row, src)
            if reason:
                rec = ft.BodyRecord(row.news_id, row.url, row.source_code, ft.FETCH_METHOD, row.title, row.published_at,
                                    "skipped", reason=reason, extractor_version=version,
                                    fetched_at=self.now().isoformat(timespec="seconds"))
            else:
                rec = ft.record_from_page(row, src, self.config, version, 200, page_html, 1, self.now)
            records.append(rec)
        with self.lock:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            days = {datetime.fromisoformat(r.published_at).astimezone(KST).date() for r in records}
            done = ft.load_done(self.raw_dir, days)
            for rec in records:
                if done.get(normalize_url(rec.url), ft.Seen("")).status in ft.DONE:
                    stat["body_already"] += 1
                    continue
                day = datetime.fromisoformat(rec.published_at).astimezone(KST).date().isoformat()
                with (self.raw_dir / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
                stat[f"body_{rec.status}"] += 1


def wait_pause(env: Env) -> None:
    while in_pause(env.now_kst()):
        secs = seconds_until_resume(env.now_kst())
        log.info("06:00~07:30 KST 정지 구간: %.0f분 기다립니다", secs / 60)
        env.sleep(min(secs, 600))


def check_lag(env: Env, force: bool = False) -> bool:
    """LAG_EVERY 페이지마다(또는 force) 지연 확인. 지연이 있으면 stop을 켜고 True."""
    if env.lag_check is None:
        return False
    with env.lag_lock:
        if env.stop.is_set():
            return True
        env.pages_since_lag[0] += 0 if force else 1
        if not force and env.pages_since_lag[0] < LAG_EVERY:
            return False
        env.pages_since_lag[0] = 0
        result = env.lag_check()
        env.lag_result.update(result)
        if result.get("lagging"):
            log.error("실시간 원문 임베딩 지연: %d건 (최대 %.1f시간, 예 %s) — 백필을 멈춥니다",
                      result["lagging"], result.get("max_hours", 0), result.get("examples"))
            env.stop.set()
            return True
        log.info("실시간 임베딩 지연 없음 (최근 원문 %d건 확인)", result.get("checked", 0))
        return False


def get_with_retry(env: Env, throttle: lf.Throttle, url: str):
    """(응답, 오류 문자열, 시도 횟수). 타임아웃·연결 오류·5xx는 max_attempts회까지 간격을 늘려 다시."""
    host = urlsplit(url).netloc.lower()
    resp, error, attempts = None, None, 0
    for attempt in range(1, env.config.max_attempts + 1):
        attempts = attempt
        wait_pause(env)
        throttle.wait(host)
        try:
            resp = env.http_get(url)
        except Exception as exc:
            resp, error = None, f"요청 실패: {type(exc).__name__}"
        else:
            if resp.status_code < 500:
                return resp, None, attempts
            error = f"HTTP {resp.status_code}"
        if attempt < env.config.max_attempts:
            env.sleep(env.config.interval * attempt)
    return resp, error, attempts


def run_source(code: str, day: date, env: Env, *, limit: int | None = None, sections: set[str] | None = None,
               failures: Failures | None = None, show: Callable[[str], None] | None = None) -> tuple[str, Counter]:
    """매체 하나의 하루치. (status, 건수). status: done / partial / blocked / lag_stop / no_sitemap / error."""
    stat: Counter = Counter()
    failures = failures or Failures(Path(os.devnull), enabled=False)
    throttle = lf.Throttle(env.config.interval, env.sleep, env.clock)
    robots = lf.RobotsCache(env.http_get, env.config.user_agent, throttle)

    smap = sitemap_url(code, day)
    wait_pause(env)
    allowed = robots.allowed(smap)
    if allowed is False:
        log.error("%s: robots.txt가 사이트맵을 막습니다 (%s)", code, smap)
        return "error", stat
    resp, error, _ = get_with_retry(env, throttle, smap)
    if resp is None or resp.status_code >= 500:
        log.error("%s: 사이트맵 요청 실패 %s (%s)", code, smap, error)
        return "error", stat
    if resp.status_code in lf.STOP_STATUSES:
        log.error("%s: 사이트맵 HTTP %s — 이 매체를 멈춥니다", code, resp.status_code)
        stat["blocked_http"] = resp.status_code
        return "blocked", stat
    if resp.status_code != 200:
        log.warning("%s: 사이트맵 HTTP %s (%s)", code, resp.status_code, smap)
        return "no_sitemap", stat

    locs = parse_sitemap(resp.text)
    urls = candidate_urls(code, locs, sections)
    stat["sitemap"], stat["candidates"] = len(locs), len(urls)
    existing = env.existing_urls([normalize_url(u) for u in urls]) if urls else set()
    todo = [u for u in urls if normalize_url(u) not in existing]
    stat["already_in_db"] = len(urls) - len(todo)
    limited = bool(limit and len(todo) > limit)
    if limit:
        todo = todo[:limit]
    log.info("%s %s: 사이트맵 %d건, 기사 URL %d건, DB에 이미 있음 %d건, 이번에 받을 페이지 %d건",
             code, day, len(locs), len(urls), stat["already_in_db"], len(todo))

    pending: list[tuple[Article, str]] = []          # (기사, 받은 페이지 HTML) — 저장 뒤 원문 기록에 쓴다

    def flush() -> None:
        if pending and env.save is not None:
            stat["inserted"] += env.save([a for a, _ in pending])
            if env.bodies is not None:
                try:
                    env.bodies.write(code, list(pending), stat)
                except Exception:                     # 원문 기록 실패는 목록을 멈추지 않는다 (fulltext 단계가 다시 받음)
                    log.exception("%s: 원문 기록 쓰기 실패 — fulltext 단계에서 다시 받습니다", code)
                    stat["body_write_error"] += len(pending)
        pending.clear()

    status = "done"
    for i, url in enumerate(todo, 1):
        if check_lag(env):
            status = "lag_stop"
            break
        if robots.allowed(url) is False:
            stat["robots_disallowed"] += 1
            failures.add(code, url, "robots.txt 불허")
            continue
        resp, error, _ = get_with_retry(env, throttle, url)
        stat["fetched"] += 1
        if resp is None or resp.status_code >= 500:
            stat["failed"] += 1
            failures.add(code, url, error or "요청 실패", getattr(resp, "status_code", None))
            continue
        if resp.status_code in lf.STOP_STATUSES:
            stat["failed"] += 1
            stat["blocked_http"] = resp.status_code
            failures.add(code, url, f"HTTP {resp.status_code} (매체 중단)", resp.status_code)
            log.error("%s: HTTP %s — 이 매체를 멈춥니다 (남은 %d건)", code, resp.status_code, len(todo) - i)
            status = "blocked"
            break
        if resp.status_code != 200:
            stat["failed"] += 1
            failures.add(code, url, f"HTTP {resp.status_code}", resp.status_code)
            continue
        stat["pages_ok"] += 1
        try:
            meta = extract_meta(code, url, resp.text)
        except Exception as exc:                      # 깨진 HTML 하나가 전체를 멈추지 않게
            stat["failed"] += 1
            failures.add(code, url, f"메타 추출 오류: {type(exc).__name__}")
            continue
        stat["has_title"] += bool(meta.title)
        stat["has_published"] += meta.published_at is not None
        stat["has_summary"] += bool(meta.summary)
        stat["has_section"] += bool(meta.section)
        if show:
            pub = meta.published_at.astimezone(KST).strftime("%m-%d %H:%M") if meta.published_at else "(없음)"
            show(f"  [{code}] {pub} | {meta.section} | {meta.title} | {(meta.summary or '')[:60]} | {url}")
        if not meta.title or meta.published_at is None:
            stat["failed"] += 1
            failures.add(code, url, "제목 없음" if not meta.title else f"발행 시각 없음 ({meta.published_raw})")
            continue
        if kst_date(meta.published_at) != day:
            stat["other_date"] += 1
            continue
        stat["matched"] += 1
        pending.append((to_article(code, url, meta), resp.text))
        if len(pending) >= SAVE_EVERY:
            flush()
        if i % 100 == 0:
            log.info("%s %s: %d/%d 페이지 (해당 날짜 %d, 저장 %d)", code, day, i, len(todo), stat["matched"],
                     stat["inserted"])
    flush()
    if status == "done" and limited:
        status = "partial"
    stat["duplicate"] = max(0, stat["matched"] - stat["inserted"]) if env.save is not None else 0
    return status, stat


def run_day(day: date, codes: list[str], env: Env, progress: Progress, failures: Failures, *,
            limit: int | None = None, sections: set[str] | None = None, force: bool = False,
            show: Callable[[str], None] | None = None) -> dict[str, tuple[str, Counter]]:
    """매체마다 스레드 하나 (같은 호스트에는 한 번에 하나). 완료된 매체·날짜는 건너뛴다."""
    results: dict[str, tuple[str, Counter]] = {}
    todo = []
    for code in codes:
        if not force and progress.status(code, day) == "done":
            log.info("%s %s: 이미 완료 (progress.json) — 건너뜁니다", code, day)
            results[code] = ("skipped_done", Counter())
        else:
            todo.append(code)
    if check_lag(env, force=True):
        for code in todo:
            results[code] = ("lag_stop", Counter())
            progress.update(code, day, "lag_stop", {})
        return results

    def one(code: str) -> None:
        try:
            status, stat = run_source(code, day, env, limit=limit, sections=sections, failures=failures, show=show)
        except Exception:
            log.exception("%s %s: 처리 중 오류", code, day)
            status, stat = "error", Counter()
        results[code] = (status, stat)
        progress.update(code, day, status, stat)

    threads = [threading.Thread(target=one, args=(c,), name=f"backfill-{c}") for c in todo]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def exit_code(results: dict[str, tuple[str, Counter]]) -> int:
    statuses = {s for s, _ in results.values()}
    if "lag_stop" in statuses:
        return EXIT_LAG
    if "blocked" in statuses:
        return EXIT_BLOCKED
    if "error" in statuses:
        return EXIT_ERROR
    return EXIT_OK


def summary_lines(day: date, results: dict[str, tuple[str, Counter]]) -> list[str]:
    lines = [f"{day} 결과"]
    for code, (status, s) in sorted(results.items()):
        pages = s["pages_ok"]
        rate = (lambda k: f"{s[k] / pages * 100:.0f}%" if pages else "-")
        lines.append(f"  {code:9} {status:12} 사이트맵 {s['sitemap']} 기사URL {s['candidates']} DB기존 {s['already_in_db']} "
                     f"페이지 {pages}/{s['fetched']} 제목 {rate('has_title')} 발행시각 {rate('has_published')} "
                     f"요약 {rate('has_summary')} 섹션 {rate('has_section')} | 해당날짜 {s['matched']} "
                     f"다른날짜 {s['other_date']} 저장 {s['inserted']} 중복 {s['duplicate']} 실패 {s['failed']}")
        if any(k.startswith("body_") for k in s):
            lines.append(f"  {'':9} 원문 기록 ok {s['body_ok']} 제외 {s['body_skipped']} 실패 {s['body_failed']} "
                         f"이미 있음 {s['body_already']} id 없음(중복) {s['body_no_id']}"
                         + (f" 쓰기 오류 {s['body_write_error']}" if s["body_write_error"] else ""))
    return lines


# ---------------------------------------------------------------- DB 접속

def resolve_dsn(env_name: str) -> str | None:
    """env_name(기본 DATABASE_URL)의 접속 주소. TEST_DATABASE_URL이 환경에 없으면 .env.test에서 읽는다."""
    from ..common.db import _psycopg_url, get_dsn, load_env

    load_env()
    if env_name == "DATABASE_URL":
        return get_dsn()
    if not os.getenv(env_name):
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parents[3] / ".env.test")
        except ImportError:
            pass
    url = os.getenv(env_name)
    return _psycopg_url(url) if url else None


def db_name(dsn: str) -> str:
    from .fulltext_load import dsn_target

    return dsn_target(dsn)


def make_db_env(dsn: str | None, dry_run: bool):
    """(existing_urls, save). dsn이 없으면(dry-run 전용) DB 확인 없이 진행."""
    import psycopg

    if not dsn:
        return (lambda urls: set()), None

    def existing(urls: list[str]) -> set[str]:
        with psycopg.connect(dsn) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute("SELECT url FROM news_articles WHERE url = ANY(%s)", (urls,))
                return {r[0] for r in cur.fetchall()}

    def save(articles: list[Article]) -> int:
        from .rss import save_to_db

        with psycopg.connect(dsn, autocommit=True) as conn:
            inserted, skipped = save_to_db(articles, conn)
        if skipped:
            log.warning("매체 미등록으로 건너뜀 %d건", skipped)
        return inserted

    return existing, (None if dry_run else save)


def make_rows_for(dsn: str):
    """정규화 URL → fulltext.ArticleRow (fulltext.read_rows와 같은 값·형식)."""
    import psycopg

    def rows_for(urls: list[str]) -> dict[str, ft.ArticleRow]:
        with psycopg.connect(dsn) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute("""SELECT a.id, s.code, a.url, a.title, a.published_at
                               FROM news_articles a JOIN news_sources s ON s.id = a.source_id
                               WHERE a.url = ANY(%s)""", (urls,))
                return {url: ft.ArticleRow(nid, code, url, title, published.isoformat())
                        for nid, code, url, title, published in cur.fetchall()}
    return rows_for


def make_lag_check(raw_dir: Path):
    """공용 DB(DATABASE_URL)에서 실시간 원문 임베딩 지연을 본다 (읽기만)."""
    from ..common.db import get_dsn
    from .backfill_check import connect, realtime_lag

    dsn = get_dsn()
    if not dsn:
        return None

    def check() -> dict:
        try:
            with connect(dsn) as conn:
                return realtime_lag(conn, raw_dir)
        except Exception as exc:
            log.warning("실시간 지연 확인 실패 (%s) — 이번에는 넘어갑니다", type(exc).__name__)
            return {"lagging": 0, "checked": 0, "error": type(exc).__name__}
    return check


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="한경·매경 사이트맵으로 과거 기사 목록을 news_articles에 채운다")
    ap.add_argument("--date", required=True, type=date.fromisoformat, help="발행일 YYYY-MM-DD (KST)")
    ap.add_argument("--sources", default="hankyung,mk")
    ap.add_argument("--sections", help="매경 URL 섹션 제한 (쉼표, 예: stock,economy,business,it)")
    ap.add_argument("--limit", type=int, help="매체당 받을 페이지 수 (시험용, 진행 기록은 partial)")
    ap.add_argument("--dsn-env", default="DATABASE_URL", help="쓸 DB 주소의 환경변수 (예: TEST_DATABASE_URL)")
    ap.add_argument("--dry-run", action="store_true", help="DB·진행 기록에 쓰지 않고 뽑은 메타만 출력")
    ap.add_argument("--force", action="store_true", help="progress.json에 done인 날짜도 다시")
    ap.add_argument("--allow-recent", action="store_true", help=f"{RECENT_FROM} 이후 날짜 허용 (실시간 공백 채우기)")
    ap.add_argument("--state-dir", type=Path, default=Path(os.getenv("BACKFILL_STATE_DIR", STATE_DIR)))
    ap.add_argument("--raw-dir", type=Path, default=Path(os.getenv("BACKFILL_RAW_DIR", "data/news_raw")),
                    help="실시간 원문 jsonl 폴더 (지연 확인용, 실시간 수집이 쓰는 폴더)")
    ap.add_argument("--no-lag-check", action="store_true", help="지연 확인을 끈다 (테스트 DB 시험용)")
    ap.add_argument("--no-body", action="store_true",
                    help="원문 기록을 쓰지 않는다 (예전 방식: 원문은 fulltext 단계가 페이지를 다시 받는다)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s")

    codes = [c.strip() for c in args.sources.split(",") if c.strip()]
    unknown = [c for c in codes if c not in SOURCES]
    if unknown:
        log.error("지원하지 않는 매체: %s (가능: %s)", unknown, ", ".join(SOURCES))
        return EXIT_REFUSED
    if args.date >= RECENT_FROM and not args.allow_recent:
        log.error("%s 이후는 실시간 수집 구간입니다. 공백을 채우려면 --allow-recent를 붙이세요.", RECENT_FROM)
        return EXIT_REFUSED
    if args.date > datetime.now(KST).date():
        log.error("미래 날짜입니다: %s", args.date)
        return EXIT_REFUSED

    dsn = resolve_dsn(args.dsn_env)
    if not dsn and not args.dry_run:
        log.error("%s 접속 정보가 없습니다.", args.dsn_env)
        return EXIT_REFUSED
    if dsn:
        target = db_name(dsn)
        if args.dsn_env == "TEST_DATABASE_URL" and "test" not in target.rsplit("/", 1)[-1].lower():
            log.error("TEST_DATABASE_URL의 DB 이름에 test가 없습니다 (%s). 멈춥니다.", target)
            return EXIT_REFUSED
        log.info("접속 대상: %s (%s)%s", target, args.dsn_env, " — dry-run: 읽기만" if args.dry_run else "")

    config = lf.load_config()
    existing, save = make_db_env(dsn, args.dry_run)
    lag = None if args.no_lag_check else make_lag_check(args.raw_dir)
    # 원문 기록은 공용 DB에 저장할 때만 (테스트 DB id가 실시간 원문 폴더에 섞이면 공용 원문 수집이 그 URL을 건너뛴다)
    bodies = (BodyWriter(args.raw_dir, config, make_rows_for(dsn))
              if dsn and save is not None and args.dsn_env == "DATABASE_URL" and not args.no_body else None)
    env = Env(http_get=lf._requests_get(config.user_agent), config=config, existing_urls=existing, save=save,
              lag_check=lag, bodies=bodies)
    log.info("원문 기록: %s", f"{args.raw_dir} (같은 페이지로 함께 저장)" if bodies else "쓰지 않음")
    suffix = "" if args.dsn_env == "DATABASE_URL" else f".{args.dsn_env}"
    write_state = not args.dry_run
    progress = Progress(args.state_dir / f"progress{suffix}.json", enabled=write_state)
    failures = Failures(args.state_dir / f"failures_{args.date.isoformat()}{suffix}.jsonl", enabled=write_state)
    sections = {s.strip() for s in args.sections.split(",")} if args.sections else None

    started = time.monotonic()
    results = run_day(args.date, codes, env, progress, failures, limit=args.limit, sections=sections,
                      force=args.force, show=print if args.dry_run else None)
    for line in summary_lines(args.date, results):
        print(line)
    if env.lag_result:
        print(f"  실시간 임베딩 지연 확인: {env.lag_result}")
    print(f"  {(time.monotonic() - started) / 60:.1f}분" + (" (dry-run: DB·진행 기록에 쓰지 않음)" if args.dry_run else ""))
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
