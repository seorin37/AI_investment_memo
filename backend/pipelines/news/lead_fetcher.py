"""뉴스 리드(첫 문단) 보충. RSS 요약이 없거나 40자 미만인 기사만 대상이다.

  python -m backend.pipelines.news.lead_fetcher --dry-run     # 보충 대상 건수만 확인 (요청·쓰기 없음)
  python -m backend.pipelines.news.lead_fetcher               # 보충 실행 (lead_sources.yaml에서 켠 매체만)
  python -m backend.pipelines.news.lead_fetcher --probe hankyung   # 본문 칸(selector) 찾기: 기사 3건만 요청
설정은 lead_sources.yaml. 2026-10-27 현재 모든 매체가 꺼져 있어 실행해도 요청을 보내지 않는다.

흐름
  1. enqueue: 켜져 있고 준비된(selector 확정 또는 naver) 매체의 최근 기사 중 요약이 부족한 기사에 pending 행을 만든다.
  2. fetch_leads: pending 기사를 매체별로 처리한다 (DB 없음, 가짜 응답으로 테스트).
     link  — robots.txt 확인 → 매체당 request_interval_seconds 간격으로 기사 요청 → 본문 칸의 첫 2~3문장
     naver — 제목으로 검색해 originallink가 같은 결과의 description
  3. save_results: 결과를 news_article_leads에 저장한다. 임베딩은 pending이 끝난 기사만 진행한다.

요청 규칙: 수집기 User-Agent를 그대로 쓰고(위장 없음) robots.txt를 지킨다. 403·429를 받으면 그 매체는
이번 실행에서 바로 멈춘다. 5xx·타임아웃은 다음 실행에 다시 시도하고 max_attempts를 넘으면 failed로 끝낸다.
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import yaml

from .embedder import SUMMARY_MIN_CHARS
from .rss import REQUEST_TIMEOUT, USER_AGENT, clean_text, normalize_url

log = logging.getLogger("lead_fetcher")

CONFIG_PATH = Path(__file__).with_name("lead_sources.yaml")
METHODS = ("link", "naver")
ADVISORY_LOCK_KEY = 0x4E4557534C44  # "NEWSLD"
STOP_STATUSES = (403, 429)          # 이 응답을 받으면 그 매체는 이번 실행에서 멈춘다

HttpGet = Callable[[str], "object"]                 # url -> 응답 (status_code, text)
NaverSearch = Callable[[str], list]                 # 검색어 -> 검색 결과 items


# ---------------------------------------------------------------- 설정

@dataclass(frozen=True)
class SourceConfig:
    code: str
    method: str
    enabled: bool = False
    domains: tuple[str, ...] = ()
    selector: str | None = None
    drop_selectors: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        """켜져 있고, link라면 본문 선택자까지 확정된 상태."""
        return self.enabled and (self.method == "naver" or bool(self.selector))


@dataclass(frozen=True)
class LeadConfig:
    sources: dict[str, SourceConfig]
    interval: float = 4.0
    max_attempts: int = 3
    max_chars: int = 300
    min_chars: int = 40
    enqueue_days: int = 3
    contact: str = ""

    @property
    def user_agent(self) -> str:
        return f"{USER_AGENT} {self.contact}".strip()


def load_config(path: Path = CONFIG_PATH) -> LeadConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = {}
    for code, s in (raw.get("sources") or {}).items():
        if s.get("method") not in METHODS:
            raise ValueError(f"{code}: method는 {METHODS} 중 하나여야 합니다")
        sources[code] = SourceConfig(
            code=code, method=s["method"], enabled=bool(s.get("enabled", False)),
            domains=tuple(s.get("domains") or ()), selector=s.get("selector") or None,
            drop_selectors=tuple(s.get("drop_selectors") or ()))
    config = LeadConfig(
        sources=sources, interval=float(raw.get("request_interval_seconds", 4)),
        max_attempts=int(raw.get("max_attempts", 3)), max_chars=int(raw.get("lead_max_chars", 300)),
        min_chars=int(raw.get("lead_min_chars", 40)), enqueue_days=int(raw.get("enqueue_days", 3)),
        contact=str(raw.get("contact") or ""))
    if config.interval < 1 or config.max_attempts < 1 or not 0 < config.min_chars <= config.max_chars <= 300:
        raise ValueError("요청 간격은 1초 이상, 재시도 1회 이상, 리드 길이는 1~300자여야 합니다")
    return config


# ---------------------------------------------------------------- 본문 추출

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_NOISE_RE = re.compile(r"무단\s*전재|재배포\s*금지|저작권자|ⓒ|©|Copyright", re.IGNORECASE)
# "(서울=연합뉴스) 홍길동 기자 =", "[한국경제TV 홍길동 기자]" 같은 머리말
_BYLINE_RE = re.compile(r"^\s*(\([^)]{0,30}=[^)]{0,30}\)|\[[^\]]{0,30}기자\])\s*([^\s=]{1,10}\s*){0,3}(기자|특파원)?\s*=?\s*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_REMOVE_TAGS = "script, style, figure, figcaption, table, iframe, noscript"


def extract_lead(html: str, selector: str, drop_selectors: Iterable[str] = (),
                 max_chars: int = 300, min_chars: int = 40) -> str | None:
    """본문 칸(selector)에서 첫 2~3문장을 max_chars자 안으로 뽑는다. 못 찾거나 너무 짧으면 None."""
    from bs4 import BeautifulSoup   # 리드 보충을 쓸 때만 필요하다

    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(selector)
    if node is None:
        return None
    for tag in node.select(", ".join([_REMOVE_TAGS, *drop_selectors])):
        tag.decompose()
    lines = []
    for raw in node.get_text("\n").splitlines():
        line = clean_text(raw)
        if line and not _EMAIL_RE.search(line) and not _NOISE_RE.search(line):
            lines.append(line)
    text = _BYLINE_RE.sub("", " ".join(lines), count=1).strip()
    lead = ""
    for sentence in _SENTENCE_RE.split(text)[:3]:
        candidate = f"{lead} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        lead = candidate
    if not lead:   # 첫 문장부터 너무 길면 글자 수로 자른다
        lead = text[:max_chars].rstrip()
    return lead if len(lead) >= min_chars else None


def lead_from_naver_items(items: Iterable[dict], url: str, max_chars: int = 300,
                          min_chars: int = 1) -> str | None:
    """검색 결과 중 원문 URL이 같은 기사의 description. 다른 기사의 요약을 붙이지 않도록 URL로만 맞춘다."""
    target = normalize_url(url)
    for item in items or []:
        link = (item.get("originallink") or item.get("link") or "").strip()
        if link and normalize_url(link) == target:
            text = clean_text(item.get("description"), max_chars)
            return text if text and len(text) >= min_chars else None
    return None


# ---------------------------------------------------------------- 요청 규칙

class Throttle:
    """같은 키(매체·호스트)에 보내는 요청 사이를 interval초 이상 띄운다."""

    def __init__(self, interval: float, sleep=time.sleep, clock=time.monotonic):
        self.interval, self.sleep, self.clock = interval, sleep, clock
        self.last: dict[str, float] = {}

    def wait(self, key: str) -> None:
        if key in self.last:
            remaining = self.interval - (self.clock() - self.last[key])
            if remaining > 0:
                self.sleep(remaining)
        self.last[key] = self.clock()


class RobotsCache:
    """호스트별 robots.txt를 한 번만 받아 확인한다. 4xx면 제한 없음, 5xx·오류면 이번에는 보류(None)."""

    def __init__(self, http_get: HttpGet, user_agent: str, throttle: Throttle):
        self.http_get, self.user_agent, self.throttle = http_get, user_agent, throttle
        self.parsers: dict[str, RobotFileParser | bool | None] = {}

    def allowed(self, url: str) -> bool | None:
        parts = urlsplit(url)
        host = parts.netloc.lower()
        if host not in self.parsers:
            self.throttle.wait(host)
            try:
                resp = self.http_get(f"{parts.scheme}://{host}/robots.txt")
            except Exception as exc:
                log.warning("robots.txt 요청 실패 %s: %s", host, type(exc).__name__)
                self.parsers[host] = None
            else:
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                    self.parsers[host] = parser
                else:
                    self.parsers[host] = True if 400 <= resp.status_code < 500 else None
        state = self.parsers[host]
        if state is None or state is True:
            return state
        return state.can_fetch(self.user_agent, url)


# ---------------------------------------------------------------- 처리 (DB 없음)

@dataclass(frozen=True)
class PendingItem:
    news_id: int
    source_code: str
    title: str
    url: str
    attempts: int = 0


@dataclass
class LeadResult:
    news_id: int
    status: str                   # ok / pending / failed / skipped
    source: str                   # link / naver / none
    attempts: int
    lead_text: str | None = None
    http_status: int | None = None
    error: str | None = None


@dataclass
class FetchStats:
    by_status: dict[str, int] = field(default_factory=dict)
    stopped_sources: list[str] = field(default_factory=list)
    not_ready_sources: list[str] = field(default_factory=list)

    def add(self, result: LeadResult) -> None:
        self.by_status[result.status] = self.by_status.get(result.status, 0) + 1


def _retry_or_fail(item: PendingItem, source: str, config: LeadConfig, error: str,
                   http_status: int | None = None) -> LeadResult:
    attempts = item.attempts + 1
    status = "failed" if attempts >= config.max_attempts else "pending"
    return LeadResult(item.news_id, status, source, attempts, http_status=http_status, error=error)


def _host_matches(url: str, domains: Iterable[str]) -> bool:
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def fetch_leads(items: Iterable[PendingItem], config: LeadConfig, http_get: HttpGet | None = None,
                naver_search: NaverSearch | None = None, sleep=time.sleep, clock=time.monotonic
                ) -> tuple[list[LeadResult], FetchStats]:
    """pending 기사의 리드를 가져온다. 준비되지 않은 매체의 기사는 결과 없이 그대로 둔다."""
    throttle = Throttle(config.interval, sleep, clock)
    robots = RobotsCache(http_get, config.user_agent, throttle) if http_get else None
    by_source: OrderedDict[str, list[PendingItem]] = OrderedDict()
    for item in items:
        by_source.setdefault(item.source_code, []).append(item)

    results: list[LeadResult] = []
    stats = FetchStats()
    for code, group in by_source.items():
        src = config.sources.get(code)
        if src is None or not src.ready or (src.method == "link" and http_get is None) \
                or (src.method == "naver" and naver_search is None):
            stats.not_ready_sources.append(code)
            continue
        for item in group:
            result = (_naver_one(item, src, config, naver_search, throttle) if src.method == "naver"
                      else _link_one(item, src, config, http_get, robots, throttle))
            results.append(result)
            stats.add(result)
            if result.http_status in STOP_STATUSES:
                log.warning("%s에서 HTTP %s를 받아 이번 실행에서는 멈춥니다.", code, result.http_status)
                stats.stopped_sources.append(code)
                break
    return results, stats


def _naver_one(item, src, config, naver_search, throttle) -> LeadResult:
    throttle.wait("naver")
    try:
        found = naver_search(item.title)
    except Exception as exc:
        return _retry_or_fail(item, "naver", config, f"검색 실패: {type(exc).__name__}")
    lead = lead_from_naver_items(found, item.url, config.max_chars, config.min_chars)
    if lead is None:
        return _retry_or_fail(item, "naver", config, "같은 원문 URL의 검색 결과 없음")
    return LeadResult(item.news_id, "ok", "naver", item.attempts + 1, lead_text=lead)


def _link_one(item, src, config, http_get, robots, throttle) -> LeadResult:
    if not _host_matches(item.url, src.domains):
        return LeadResult(item.news_id, "skipped", "none", item.attempts, error="설정한 도메인이 아님")
    allowed = robots.allowed(item.url)
    if allowed is None:
        return _retry_or_fail(item, "link", config, "robots.txt 확인 실패")
    if not allowed:
        return LeadResult(item.news_id, "skipped", "link", item.attempts, error="robots.txt가 허용하지 않음")
    throttle.wait(urlsplit(item.url).netloc.lower())
    try:
        resp = http_get(item.url)
    except Exception as exc:
        return _retry_or_fail(item, "link", config, f"요청 실패: {type(exc).__name__}")
    code = resp.status_code
    if code in STOP_STATUSES or code >= 500:
        return _retry_or_fail(item, "link", config, f"HTTP {code}", code)
    if code != 200:
        return LeadResult(item.news_id, "failed", "link", item.attempts + 1, http_status=code, error=f"HTTP {code}")
    lead = extract_lead(resp.text, src.selector, src.drop_selectors, config.max_chars, config.min_chars)
    if lead is None:
        return LeadResult(item.news_id, "failed", "link", item.attempts + 1, http_status=code,
                          error="본문 추출 실패 (선택자 확인 필요)")
    return LeadResult(item.news_id, "ok", "link", item.attempts + 1, lead_text=lead, http_status=code)


# ---------------------------------------------------------------- selector 찾기 (--probe)

# 흔히 쓰이는 본문 칸. 구체적인 것부터 두고, 넓은 것(article)은 메뉴가 섞일 수 있어 마지막에 둔다.
CANDIDATE_SELECTORS = (
    "#articletxt", "#article-body", "#article_body", "#articleBody", "#news_body_area", "#newsEndContents",
    "div.article-body", "div.article_body", "div.article-txt", "div.news_cnt_detail_wrap", "div.story-news",
    "[itemprop='articleBody']", "article",
)


@dataclass
class ProbeRow:
    selector: str
    hits: int
    samples: list[str] = field(default_factory=list)


def probe(urls: Iterable[str], src: SourceConfig, config: LeadConfig, http_get: HttpGet,
          selectors: Iterable[str] | None = None, sleep=time.sleep, clock=time.monotonic,
          save_dir: Path | None = None) -> tuple[list[ProbeRow], int, list[str]]:
    """기사 몇 건을 받아 후보 selector마다 리드가 뽑히는지 본다. (결과, 받은 기사 수, 메모)

    요청 규칙은 실제 수집과 같다 (UA, robots.txt, 간격, 403·429 중단). 설정 파일은 바꾸지 않는다.
    """
    throttle = Throttle(config.interval, sleep, clock)
    robots = RobotsCache(http_get, config.user_agent, throttle)
    pages: list[str] = []
    notes: list[str] = []
    for url in urls:
        if not _host_matches(url, src.domains):
            notes.append(f"건너뜀(도메인 다름): {url}")
            continue
        allowed = robots.allowed(url)
        if not allowed:
            notes.append(f"건너뜀(robots.txt {'확인 실패' if allowed is None else '불허'}): {url}")
            continue
        throttle.wait(urlsplit(url).netloc.lower())
        try:
            resp = http_get(url)
        except Exception as exc:
            notes.append(f"요청 실패({type(exc).__name__}): {url}")
            continue
        if resp.status_code in STOP_STATUSES:
            notes.append(f"HTTP {resp.status_code} — 더 요청하지 않고 멈춤: {url}")
            break
        if resp.status_code != 200:
            notes.append(f"HTTP {resp.status_code}: {url}")
            continue
        pages.append(resp.text)
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / f"{src.code}_{len(pages)}.html").write_text(resp.text, encoding="utf-8")
    rows = []
    for selector in selectors or CANDIDATE_SELECTORS:
        leads = [extract_lead(html, selector, src.drop_selectors, config.max_chars, config.min_chars)
                 for html in pages]
        found = [lead for lead in leads if lead]
        rows.append(ProbeRow(selector, len(found), found))
    rows.sort(key=lambda r: -r.hits)   # 안정 정렬: 같은 성공 수면 후보 순서(구체적인 것 먼저) 유지
    return rows, len(pages), notes


def recommend(rows: list[ProbeRow], fetched: int) -> str | None:
    """받은 기사 전부에서 리드가 뽑힌 첫 selector. 샘플 문장은 사람이 눈으로 확인해야 한다."""
    return next((r.selector for r in rows if fetched and r.hits == fetched), None)


def probe_urls(conn, code: str, limit: int = 3) -> list[str]:
    """그 매체의 최근 기사 중 요약이 부족한 것 우선으로 limit건."""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT a.url FROM news_articles a JOIN news_sources s ON s.id = a.source_id
            WHERE s.code = %s
            ORDER BY (a.summary IS NULL OR char_length(btrim(a.summary)) < {SUMMARY_MIN_CHARS}) DESC,
                     a.published_at DESC
            LIMIT %s""", (code, limit))
        return [r[0] for r in cur.fetchall()]


def _print_probe(code: str, rows: list[ProbeRow], fetched: int, notes: list[str]) -> None:
    print(f"\n[{code}] 받은 기사 {fetched}건")
    for note in notes:
        print("  -", note)
    for r in rows:
        sample = (r.samples[0][:70] + "…") if r.samples else "(칸 없음 또는 너무 짧음)"
        print(f"  {r.selector:<28} {r.hits}/{fetched}  {sample}")
    best = recommend(rows, fetched)
    if best:
        print(f"\n추천: {best}")
        print("  샘플이 기사 첫 문장인지(메뉴·광고가 섞이지 않았는지) 눈으로 확인한 뒤")
        print(f"  lead_sources.yaml 의 {code}.selector 에 적고 enabled: true 로 바꾸세요.")
    else:
        print("\n모든 기사에서 뽑힌 칸이 없습니다. 브라우저에서 본문 오른쪽 클릭 → 검사로 칸 이름을 찾아")
        print('  --selector "칸이름" 으로 다시 확인하세요.')


# ---------------------------------------------------------------- DB

def enqueue(conn, config: LeadConfig, days: int | None = None) -> int:
    """준비된 매체의 최근 기사 중 요약이 부족하고 아직 리드 행이 없는 기사를 pending으로 올린다."""
    ready = [s for s in config.sources.values() if s.ready]
    added = 0
    with conn.cursor() as cur:
        for src in ready:
            cur.execute(f"""
                INSERT INTO news_article_leads (news_id, source, status)
                SELECT a.id, %(method)s, 'pending'
                FROM news_articles a JOIN news_sources s ON s.id = a.source_id
                WHERE s.code = %(code)s
                  AND a.published_at >= now() - make_interval(days => %(days)s)
                  AND (a.summary IS NULL OR char_length(btrim(a.summary)) < {SUMMARY_MIN_CHARS})
                ON CONFLICT (news_id) DO NOTHING""",
                        {"method": src.method, "code": src.code, "days": days or config.enqueue_days})
            added += cur.rowcount
    return added


def load_pending(conn, codes: Iterable[str]) -> list[PendingItem]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT l.news_id, s.code, a.title, a.url, l.attempts
            FROM news_article_leads l
            JOIN news_articles a ON a.id = l.news_id
            JOIN news_sources s ON s.id = a.source_id
            WHERE l.status = 'pending' AND s.code = ANY(%s)
            ORDER BY a.published_at, a.id""", (list(codes),))
        return [PendingItem(*row) for row in cur.fetchall()]


def save_results(conn, results: Iterable[LeadResult]) -> int:
    saved = 0
    with conn.cursor() as cur:
        for r in results:
            cur.execute("""
                UPDATE news_article_leads
                SET status = %s, source = %s, lead_text = %s, attempts = %s, http_status = %s,
                    last_error = %s, fetched_at = CASE WHEN %s = 'pending' THEN fetched_at ELSE now() END,
                    updated_at = now()
                WHERE news_id = %s""",
                        (r.status, r.source, r.lead_text, r.attempts, r.http_status, r.error, r.status, r.news_id))
            saved += cur.rowcount
    return saved


def _requests_get(user_agent: str) -> HttpGet:
    import requests
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    return lambda url: session.get(url, timeout=REQUEST_TIMEOUT)


def _naver_search_from_env() -> NaverSearch | None:
    import os
    from .naver import DEFAULT_BASE_URL, make_fetcher
    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        log.warning("NAVER_CLIENT_ID/SECRET이 없어 naver 방식 매체는 건너뜁니다.")
        return None
    fetch = make_fetcher(cid, secret, os.environ.get("NAVER_API_BASE_URL", DEFAULT_BASE_URL))
    return lambda query: (fetch(query, 1) or {}).get("items") or []


def run(conn, config: LeadConfig | None = None, http_get: HttpGet | None = None,
        naver_search: NaverSearch | None = None, days: int | None = None) -> dict:
    """enqueue → fetch → save. conn은 autocommit이어도 된다. 다른 곳에서 실행 중이면 건너뛴다."""
    config = config or load_config()
    ready = [s for s in config.sources.values() if s.ready]
    if not ready:
        log.info("리드 보충: 켜져 있고 준비된 매체가 없어 요청을 보내지 않습니다.")
        return {"enqueued": 0, "results": {}, "skipped": "no_ready_source"}
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        if not cur.fetchone()[0]:
            log.warning("다른 곳에서 리드 보충이 실행 중입니다. 이번에는 건너뜁니다.")
            return {"enqueued": 0, "results": {}, "skipped": "locked"}
    try:
        enqueued = enqueue(conn, config, days)
        items = load_pending(conn, [s.code for s in ready])
        if http_get is None and any(s.method == "link" for s in ready):
            http_get = _requests_get(config.user_agent)
        if naver_search is None and any(s.method == "naver" for s in ready):
            naver_search = _naver_search_from_env()
        results, stats = fetch_leads(items, config, http_get, naver_search)
        save_results(conn, results)
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
    log.info("리드 보충: 새 대상 %d건, 처리 %s, 멈춘 매체 %s", enqueued, stats.by_status, stats.stopped_sources)
    return {"enqueued": enqueued, "results": stats.by_status, "stopped": stats.stopped_sources}


def dry_run(conn, config: LeadConfig, days: int) -> list[tuple]:
    """요청·쓰기 없이 매체별 보충 대상 건수와 설정 상태를 돌려준다."""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT s.code, count(*)
            FROM news_articles a JOIN news_sources s ON s.id = a.source_id
            WHERE a.published_at >= now() - make_interval(days => %s)
              AND (a.summary IS NULL OR char_length(btrim(a.summary)) < {SUMMARY_MIN_CHARS})
            GROUP BY 1 ORDER BY 2 DESC""", (days,))
        counts = cur.fetchall()
    out = []
    for code, n in counts:
        src = config.sources.get(code)
        state = "설정 없음" if src is None else ("준비됨" if src.ready else
                 ("꺼짐" if not src.enabled else "선택자 미확정"))
        out.append((code, n, src.method if src else "-", state))
    return out


def main(argv=None) -> int:
    import psycopg
    from ..common.db import get_dsn, load_env

    ap = argparse.ArgumentParser(description="뉴스 리드(첫 문단) 보충")
    ap.add_argument("--dry-run", action="store_true", help="요청·쓰기 없이 보충 대상 건수만 출력")
    ap.add_argument("--days", type=int, help="최근 며칠 발행분을 볼지 (기본: 설정의 enqueue_days)")
    ap.add_argument("--probe", metavar="MEDIA", help="이 매체(link 방식)의 본문 칸 찾기. enabled와 상관없이 기사 몇 건만 요청")
    ap.add_argument("--selector", action="append", help="--probe: 이 selector만 확인 (여러 번 지정 가능)")
    ap.add_argument("--url", action="append", help="--probe: 확인할 기사 URL (기본: DB에서 최근 기사)")
    ap.add_argument("--limit", type=int, default=3, help="--probe: 받을 기사 수 (기본 3, 최대 5)")
    ap.add_argument("--save-fixtures", type=Path, metavar="DIR", help="--probe: 받은 HTML을 테스트용으로 저장")
    ap.add_argument("--yes", action="store_true", help="--probe: 요청 전 확인 질문을 건너뜀")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
    config = load_config()
    if args.probe:
        src = config.sources.get(args.probe)
        if src is None or src.method != "link":
            log.error("%s: lead_sources.yaml에 link 방식으로 설정된 매체가 아닙니다.", args.probe)
            return 1
        limit = max(1, min(args.limit, 5))
        if args.url:
            urls = args.url[:limit]
        else:
            with psycopg.connect(dsn, autocommit=True) as conn:
                urls = probe_urls(conn, args.probe, limit)
        if not urls:
            log.error("확인할 기사 URL이 없습니다.")
            return 1
        print(f"{args.probe} 매체에 robots.txt 1건 + 기사 {len(urls)}건을 "
              f"{config.interval:g}초 간격으로 요청합니다. (User-Agent: {config.user_agent})")
        if not args.yes and input("계속할까요? [y/N] ").strip().lower() != "y":
            print("취소했습니다.")
            return 1
        rows, fetched, notes = probe(urls, src, config, _requests_get(config.user_agent),
                                     args.selector, save_dir=args.save_fixtures)
        _print_probe(args.probe, rows, fetched, notes)
        return 0
    with psycopg.connect(dsn, autocommit=True) as conn:
        if args.dry_run:
            print("매체  보충대상  방식  상태")
            for row in dry_run(conn, config, args.days or config.enqueue_days):
                print(*row)
            return 0
        run(conn, config, days=args.days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
