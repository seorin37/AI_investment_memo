"""뉴스 리드(첫 문단) 보충. RSS 요약이 없거나 40자 미만인 기사만 대상이다.

  python -m backend.pipelines.news.lead_fetcher --dry-run     # 보충 대상 건수만 확인 (요청·쓰기 없음)
  python -m backend.pipelines.news.lead_fetcher               # 보충 실행 (lead_sources.yaml에서 켠 매체만)
  python -m backend.pipelines.news.lead_fetcher --probe hankyung   # 본문 칸(selector) 찾기: 기사 3건만 요청
  python -m backend.pipelines.news.lead_fetcher --probe mk --limit 10 --from-naver 증시 \
      --save-fixtures samples/mk --report samples/report.csv       # 네이버 검색 원본 링크 10건, HTML 저장 + CSV
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
    fulltext_enabled: bool = True     # link 방식에서 원문 페이지를 요청할지. false면 원문을 요청하지 않는다
    fallback: str | None = None       # 원문을 쓸 수 없을 때(fulltext_enabled false 또는 selector 미확정) 쓸 방식 (naver)
    probe_selectors: tuple[str, ...] = ()   # --probe에서 기본 후보 앞에 더 볼 selector (확정 전 후보)
    url_patterns: tuple[str, ...] = ()      # 있으면 URL 경로가 이 정규식 중 하나와 맞는 기사만 원문을 받는다 (사진 기사 제외 등)
    subtitle_selector: str | None = None    # 부제목 칸 (본문에서는 drop_selectors로 빼고 따로 뽑는다)
    paywall_selectors: tuple[str, ...] = () # 유료 안내 칸 후보. paywall_text가 글에 있으면 본문에서 빼고 유료 기사로 표시
    paywall_text: str | None = None         # 유료 안내 문구 정규식 (없으면 칸만 있어도 유료)
    skip_paywalled: bool = False            # true면 유료 기사는 저장하지 않고 skipped (받아 봐야 알 수 있어 요청은 한 번 간다)
    drop_text_patterns: tuple[str, ...] = ()     # 글이 이 정규식으로 시작하는 문단(p·li)을 통째로 지운다 (관련 기사 링크 줄 등)
    skip_section_patterns: tuple[str, ...] = ()  # 페이지 meta[property='article:section']이 맞으면 skipped (모음 기사 등)
    skip_title_patterns: tuple[str, ...] = ()    # 제목(RSS 제목, 페이지 og:title)이 맞으면 skipped (모음 기사 등)

    @property
    def skips_after_fetch(self) -> bool:
        """받아 봐야 건너뛸지 알 수 있는 규칙이 있는지 (--probe가 여유분 URL을 더 모은다)."""
        return self.skip_paywalled or bool(self.skip_section_patterns or self.skip_title_patterns)

    @property
    def active_method(self) -> str | None:
        """지금 실제로 쓰는 방식. link는 원문 허용 + selector 확정일 때만, 아니면 fallback, 둘 다 없으면 None."""
        if self.method == "link" and self.fulltext_enabled and self.selector:
            return "link"
        if self.method == "naver" or self.fallback == "naver":
            return "naver"
        return None

    @property
    def ready(self) -> bool:
        """켜져 있고 쓸 방식이 있는 상태 (link라면 원문 허용 + 본문 선택자 확정)."""
        return self.enabled and self.active_method is not None

    @property
    def can_probe(self) -> bool:
        """--probe로 원문을 요청해도 되는 매체 (link 방식이고 fulltext_enabled). selector 확정은 필요 없다."""
        return self.method == "link" and self.fulltext_enabled


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
        if s.get("fallback") not in (None, "naver"):
            raise ValueError(f"{code}: fallback은 비우거나 naver여야 합니다")
        sources[code] = SourceConfig(
            code=code, method=s["method"], enabled=bool(s.get("enabled", False)),
            domains=tuple(s.get("domains") or ()), selector=s.get("selector") or None,
            drop_selectors=tuple(s.get("drop_selectors") or ()),
            fulltext_enabled=bool(s.get("fulltext_enabled", True)), fallback=s.get("fallback") or None,
            probe_selectors=tuple(s.get("probe_selectors") or ()), url_patterns=tuple(s.get("url_patterns") or ()),
            subtitle_selector=s.get("subtitle_selector") or None,
            paywall_selectors=tuple(s.get("paywall_selectors") or ()), paywall_text=s.get("paywall_text") or None,
            skip_paywalled=bool(s.get("skip_paywalled", False)),
            drop_text_patterns=tuple(s.get("drop_text_patterns") or ()),
            skip_section_patterns=tuple(s.get("skip_section_patterns") or ()),
            skip_title_patterns=tuple(s.get("skip_title_patterns") or ()))
        src = sources[code]
        for pattern in (*src.url_patterns, *src.drop_text_patterns, *src.skip_section_patterns, *src.skip_title_patterns,
                        *([src.paywall_text] if src.paywall_text else [])):
            re.compile(pattern)                                  # 잘못된 정규식은 설정을 읽을 때 바로 실패시킨다
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
# "(서울=연합뉴스) 홍길동 기자 =", "[한국경제TV 홍길동 기자]" 같은 머리말. 괄호 뒤 단어(최대 3개)는 "기자 =", "특파원 =",
# "="로 끝날 때만 지운다. 2026-11-06 전에는 "기자"와 "="가 둘 다 선택이라 "(서울=연합뉴스) 코스피 상장사 한화엔진[082740]은"의
# "코스피 상장사 한화엔진[08274"까지 지웠다
_BYLINE_RE = re.compile(r"^\s*(\([^)]{0,30}=[^)]{0,30}\)|\[[^\]]{0,30}기자\])\s*"
                        r"(?:(?:[^\s=]{1,10}\s*){0,3}?(?:기자|특파원)?\s*=\s*)?")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_REMOVE_TAGS = "script, style, figure, figcaption, table, iframe, noscript"


def _notice_nodes(root, selectors: Iterable[str], pattern: str | None) -> list:
    """selectors 칸 중 글에 pattern이 있는 것 (pattern이 없으면 칸 전부)."""
    selectors = list(selectors)
    if not selectors:
        return []
    nodes = root.select(", ".join(selectors))
    return [n for n in nodes if not pattern or re.search(pattern, n.get_text(" "))]


def body_text(html: str, selector: str, drop_selectors: Iterable[str] = (),
              notice_selectors: Iterable[str] = (), notice_pattern: str | None = None,
              drop_text_patterns: Iterable[str] = ()) -> str | None:
    """본문 칸(selector)의 글 전체 (사진·표·스크립트, 이메일·저작권 줄, 머리말 제거). 칸이 없으면 None.
    notice_selectors 칸은 글에 notice_pattern이 있을 때만 지운다 (한국경제 div.box-cont는 유료 안내에도, 편집자주에도 쓰인다).
    drop_text_patterns: 글이 이 정규식으로 시작하는 문단(p·li)을 통째로 지운다. 서울경제 "▶기사 바로가기: <링크 제목>"은
    한 문단 안에서 태그로 나뉘어 줄 단위로 지우면 링크 제목이 남는다."""
    from bs4 import BeautifulSoup   # 리드 보충을 쓸 때만 필요하다

    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(selector)
    if node is None:
        return None
    for tag in _notice_nodes(node, notice_selectors, notice_pattern):
        tag.decompose()
    for tag in node.select(", ".join([_REMOVE_TAGS, *drop_selectors])):
        tag.decompose()
    patterns = [re.compile(p) for p in drop_text_patterns]
    if patterns:
        for tag in node.find_all(["p", "li"]):
            if not tag.decomposed and any(p.match(tag.get_text(" ").strip()) for p in patterns):
                tag.decompose()
    lines = []
    for raw in node.get_text("\n").splitlines():
        line = clean_text(raw)
        if line and not _EMAIL_RE.search(line) and not _NOISE_RE.search(line):
            lines.append(line)
    return _BYLINE_RE.sub("", " ".join(lines).lstrip(" ·•|"), count=1).strip()


def raw_text_chars(html: str, selector: str) -> int | None:
    """본문 칸을 아무것도 지우지 않고 읽었을 때의 글자 수 (body_text와의 차이 = 지운 잡음의 양). 칸이 없으면 None."""
    from bs4 import BeautifulSoup

    node = BeautifulSoup(html, "lxml").select_one(selector)
    return None if node is None else len(clean_text(node.get_text(" ")) or "")


def extract_subtitle(html: str, selector: str | None) -> str | None:
    """부제목 칸의 줄들을 " / "로 이은 글. 칸이 없거나 비면 None. (매일경제 div.mid_title: 여러 줄 부제목)"""
    if not selector:
        return None
    from bs4 import BeautifulSoup

    node = BeautifulSoup(html, "lxml").select_one(selector)
    if node is None:
        return None
    lines = [line for line in (clean_text(raw) for raw in node.get_text("\n").splitlines()) if line]
    return " / ".join(lines) or None


def paywall_reason(html: str, selectors: Iterable[str], pattern: str | None = None) -> str | None:
    """유료 안내 칸이 있으면 '걸린 칸: 글 앞 60자', 없으면 None.
    한국경제: div.box-cont "한경 프리미엄9에 실린 기사입니다", blockquote "…유료 프리미엄…" (2026-11-06 샘플)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for selector in selectors:
        nodes = _notice_nodes(soup, [selector], pattern)
        if nodes:
            return f"{selector}: {clean_text(nodes[0].get_text(' ')) or ''}"[:len(selector) + 2 + 60]
    return None


def is_paywalled(html: str, selectors: Iterable[str], pattern: str | None = None) -> bool:
    """페이지에 유료 안내 칸(selectors 중 글에 pattern이 있는 것)이 하나라도 있으면 True."""
    return paywall_reason(html, selectors, pattern) is not None if selectors else False


def page_title(html: str) -> str:
    """페이지 제목 (og:title, 없으면 <title>)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", attrs={"property": "og:title"})
    text = (meta.get("content") if meta else None) or (soup.title.get_text() if soup.title else "")
    return " ".join(text.split())


def title_skip_reason(title: str, src: SourceConfig) -> str | None:
    """제목이 skip_title_patterns와 맞으면 '모음 기사 (제목 …)'."""
    if title and any(re.search(p, title) for p in src.skip_title_patterns):
        return f"모음 기사 (제목 '{title[:40]}')"
    return None


def page_skip_reason(html: str, src: SourceConfig) -> str | None:
    """받은 페이지가 건너뛸 기사면 이유, 아니면 None. 유료(skip_paywalled) → 모음 기사(섹션 meta, 페이지 제목) 순."""
    if src.skip_paywalled:
        reason = paywall_reason(html, src.paywall_selectors, src.paywall_text)
        if reason:
            return f"유료 기사 ({reason})"
    if src.skip_section_patterns:
        from bs4 import BeautifulSoup

        meta = BeautifulSoup(html, "lxml").find("meta", attrs={"property": "article:section"})
        section = (meta.get("content") or "").strip() if meta else ""
        if section and any(re.search(p, section) for p in src.skip_section_patterns):
            return f"모음 기사 (섹션 '{section}')"
    return title_skip_reason(page_title(html), src) if src.skip_title_patterns else None


def source_body_text(html: str, src: SourceConfig, selector: str | None = None) -> str | None:
    """매체 설정(drop·유료 안내·문구 패턴)을 모두 적용한 본문. selector를 주면 그 칸으로 (--probe 후보 비교)."""
    return body_text(html, selector or src.selector, src.drop_selectors, src.paywall_selectors, src.paywall_text,
                     src.drop_text_patterns)


def extract_lead(html: str, selector: str, drop_selectors: Iterable[str] = (),
                 max_chars: int = 300, min_chars: int = 40,
                 notice_selectors: Iterable[str] = (), notice_pattern: str | None = None,
                 drop_text_patterns: Iterable[str] = ()) -> str | None:
    """본문 칸(selector)에서 첫 2~3문장을 max_chars자 안으로 뽑는다. 못 찾거나 너무 짧으면 None."""
    text = body_text(html, selector, drop_selectors, notice_selectors, notice_pattern, drop_text_patterns)
    if text is None:
        return None
    lead = ""
    for sentence in _SENTENCE_RE.split(text)[:3]:
        candidate = f"{lead} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        lead = candidate
    if not lead:   # 첫 문장부터 너무 길면 글자 수로 자른다
        lead = text[:max_chars].rstrip()
    return lead if len(lead) >= min_chars else None


def meta_description_lead(html: str, max_chars: int = 300, min_chars: int = 1, title: str = "") -> str | None:
    """본문 칸이 없는 페이지의 대체 리드: 페이지가 제공하는 요약(og:description). 제목과 같거나 너무 짧으면 쓰지 않는다."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"})
    text = " ".join((meta.get("content") or "").split()) if meta else ""
    if not text or len(text) < min_chars or (title and text in title):
        return None
    return text[:max_chars].rstrip()


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
    """도메인 또는 그 서브도메인. "www.mk.co.kr"처럼 www를 붙여 적으면 그 호스트만 (mbn.mk.co.kr 제외)."""
    host = urlsplit(url).netloc.lower()
    bare = host.removeprefix("www.")
    return any(h == d or h.endswith("." + d) for d in domains for h in (host, bare))


def _url_accepted(url: str, src: SourceConfig) -> bool:
    """매체 도메인이고, url_patterns가 있으면 경로(쿼리 제외)가 그중 하나와 맞는 기사."""
    if not _host_matches(url, src.domains):
        return False
    return not src.url_patterns or any(re.search(p, urlsplit(url).path) for p in src.url_patterns)


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
        method = src.active_method if src is not None and src.ready else None
        if method is None or (method == "link" and http_get is None) \
                or (method == "naver" and naver_search is None):
            stats.not_ready_sources.append(code)
            continue
        for item in group:
            result = (_naver_one(item, src, config, naver_search, throttle) if method == "naver"
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
    if not _url_accepted(item.url, src):
        return LeadResult(item.news_id, "skipped", "none", item.attempts, error="설정한 URL 패턴이 아님 (사진 기사 등)")
    reason = title_skip_reason(item.title, src)              # RSS 제목으로 알 수 있으면 요청하지 않는다
    if reason:
        log.info("%s 건너뜀: %s %s", src.code, reason, item.url)
        return LeadResult(item.news_id, "skipped", "none", item.attempts, error=reason)
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
    reason = page_skip_reason(resp.text, src)                # 유료 기사(걸린 칸·문구 앞 60자), 모음 기사
    if reason:
        log.info("%s 건너뜀(저장 안 함): %s %s", src.code, reason, item.url)
        return LeadResult(item.news_id, "skipped", "link", item.attempts + 1, http_status=code, error=reason)
    lead = extract_lead(resp.text, src.selector, src.drop_selectors, config.max_chars, config.min_chars,
                        src.paywall_selectors, src.paywall_text, src.drop_text_patterns)
    if lead is None and item.attempts + 1 >= config.max_attempts:
        # 본문이 끝내 안 채워지면 마지막 시도에서만 페이지 요약으로 대체 (속보는 본문이 늦게 채워진다)
        lead = meta_description_lead(resp.text, config.max_chars, config.min_chars, item.title)
    if lead is None:
        return _retry_or_fail(item, "link", config, "본문 추출 실패 (선택자 확인 필요)", code)
    return LeadResult(item.news_id, "ok", "link", item.attempts + 1, lead_text=lead, http_status=code)


# ---------------------------------------------------------------- selector 찾기 (--probe)

# 흔히 쓰이는 본문 칸. 구체적인 것부터 두고, 넓은 것(article)은 메뉴가 섞일 수 있어 마지막에 둔다.
CANDIDATE_SELECTORS = (
    "#articletxt", "#article-body", "#article_body", "#articleBody", "#news_body_area", "#newsEndContents",
    "div.article-body", "div.article_body", "div.article-txt", "div.news_cnt_detail_wrap", "div.story-news",
    "[itemprop='articleBody']", "article",
)


def probe_candidates(src: SourceConfig, selectors: Iterable[str] | None = None) -> list[str]:
    """--selector를 주면 그것만, 아니면 매체 후보(probe_selectors) + 공통 후보 (중복 없이, 매체 후보 먼저)."""
    if selectors:
        return list(selectors)
    return list(dict.fromkeys([*src.probe_selectors, *CANDIDATE_SELECTORS]))


PROBE_MAX = 10  # --probe 한 번에 받는 기사 수 상한 (2026-11-06 5 → 10: 매체별 10건으로 선택자 확정)


@dataclass
class ProbeRow:
    selector: str
    hits: int
    samples: list[str] = field(default_factory=list)


@dataclass
class ProbeFetch:
    """--probe가 기사 하나에 대해 한 일 (--report용)."""
    url: str
    robots: str                     # 허용 / 불허 / 확인 실패 / 도메인 다름
    http_status: int | None = None
    stopped: bool = False           # 403·429를 받아 이 매체 요청을 멈췄는지
    html: str | None = None
    file: str = ""
    error: str = ""
    paywalled: bool = False         # skip_paywalled로 건너뛴 유료 기사


def probe(urls: Iterable[str], src: SourceConfig, config: LeadConfig, http_get: HttpGet,
          selectors: Iterable[str] | None = None, sleep=time.sleep, clock=time.monotonic,
          save_dir: Path | None = None, fetch_log: list[ProbeFetch] | None = None, max_pages: int | None = None
          ) -> tuple[list[ProbeRow], int, list[str]]:
    """기사 몇 건을 받아 후보 selector마다 리드가 뽑히는지 본다. (결과, 받은 기사 수, 메모)

    요청 규칙은 실제 수집과 같다 (UA, robots.txt, 간격, 403·429 중단). 설정 파일은 바꾸지 않는다.
    fetch_log를 주면 기사마다 robots.txt 결과·HTTP 상태·저장 파일을 담는다.
    """
    throttle = Throttle(config.interval, sleep, clock)
    robots = RobotsCache(http_get, config.user_agent, throttle)
    pages: list[str] = []
    notes: list[str] = []
    log_ = fetch_log if fetch_log is not None else []
    for url in urls:
        if not _host_matches(url, src.domains):
            notes.append(f"건너뜀(도메인 다름): {url}")
            log_.append(ProbeFetch(url, "도메인 다름"))
            continue
        if not _url_accepted(url, src):
            notes.append(f"건너뜀(URL 패턴 다름): {url}")
            log_.append(ProbeFetch(url, "URL 패턴 다름"))
            continue
        allowed = robots.allowed(url)
        if not allowed:
            state = "확인 실패" if allowed is None else "불허"
            notes.append(f"건너뜀(robots.txt {state}): {url}")
            log_.append(ProbeFetch(url, state))
            continue
        throttle.wait(urlsplit(url).netloc.lower())
        try:
            resp = http_get(url)
        except Exception as exc:
            notes.append(f"요청 실패({type(exc).__name__}): {url}")
            log_.append(ProbeFetch(url, "허용", error=type(exc).__name__))
            continue
        if resp.status_code in STOP_STATUSES:
            notes.append(f"HTTP {resp.status_code} — 더 요청하지 않고 멈춤: {url}")
            log_.append(ProbeFetch(url, "허용", resp.status_code, stopped=True))
            break
        if resp.status_code != 200:
            notes.append(f"HTTP {resp.status_code}: {url}")
            log_.append(ProbeFetch(url, "허용", resp.status_code))
            continue
        reason = page_skip_reason(resp.text, src)            # 유료 기사(걸린 칸·문구 앞 60자), 모음 기사
        if reason:
            notes.append(f"건너뜀(저장 안 함) {reason}: {url}")
            log.info("%s 건너뜀(저장 안 함): %s %s", src.code, reason, url)
            log_.append(ProbeFetch(url, "허용", 200, error=f"{reason} (저장 안 함)", paywalled=reason.startswith("유료")))
            continue
        pages.append(resp.text)
        fetch = ProbeFetch(url, "허용", 200, html=resp.text)
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            path = save_dir / f"{src.code}_{len(pages)}.html"
            path.write_text(resp.text, encoding="utf-8")
            fetch.file = str(path)
        log_.append(fetch)
        if max_pages and len(pages) >= max_pages:   # 유료 기사를 건너뛸 여유분으로 URL을 더 모았을 때 목표 건수에서 멈춘다
            break
    rows = []
    for selector in probe_candidates(src, selectors):
        leads = [extract_lead(html, selector, src.drop_selectors, config.max_chars, config.min_chars,
                              src.paywall_selectors, src.paywall_text, src.drop_text_patterns) for html in pages]
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


NAVER_PROBE_MAX_CALLS = 12   # --from-naver: 매체 하나를 채울 때 검색 API 호출 상한 (기본값, --max-searches로 바꾼다)


def naver_probe_urls(fetch, queries: Iterable[str], domains: Iterable[str], limit: int,
                     max_calls: int = NAVER_PROBE_MAX_CALLS, url_patterns: Iterable[str] = ()
                     ) -> tuple[list[str], int]:
    """네이버 뉴스 검색 결과의 originallink(언론사 원본 링크) 중 그 매체 도메인(서브도메인 포함)인 것 limit건. (URL, 검색 횟수)
    fetch는 naver.make_fetcher가 만든 함수 (검색어, start) -> 응답 JSON (한 번에 최대 100건).
    모든 검색어의 1페이지를 먼저 보고, 모자라면 2페이지(start=101), 3페이지(201)… 순으로 넘긴다 (한 검색어가 호출을 다 쓰지 않게).
    결과가 100건보다 적게 온 검색어는 끝난 것으로 보고 다음 페이지를 부르지 않는다. 2026-11-06 검색어 4개 × 1페이지로는
    서울경제 1건, 한국경제 5건밖에 모이지 않았다."""
    from .naver import MAX_START, PAGE_SIZE

    accept = SourceConfig("", "link", domains=tuple(domains), url_patterns=tuple(url_patterns))
    urls: list[str] = []
    calls = 0
    active = list(dict.fromkeys(queries))
    start = 1
    while active and start <= MAX_START:
        for query in list(active):
            if calls >= max_calls or len(urls) >= limit:
                return urls, calls
            items = (fetch(query, start) or {}).get("items") or []
            calls += 1
            for item in items:
                link = (item.get("originallink") or "").strip()
                if link and _url_accepted(link, accept) and link not in urls:   # 사진 기사(PYH 등)는 모으지 않는다
                    urls.append(link)
                    if len(urls) >= limit:
                        return urls, calls
            if len(items) < PAGE_SIZE:
                active.remove(query)
        start += PAGE_SIZE
    return urls, calls


REPORT_FIELDS = ("매체", "url", "host", "robots", "http_status", "멈춤_403_429", "html_file", "error",
                 "subtitle", "is_paywalled", "selector", "본문_글자수", "원문_글자수", "성공")


def write_probe_report(path: Path, src: SourceConfig, config: LeadConfig, fetches: list[ProbeFetch],
                       selectors: Iterable[str] | None = None) -> int:
    """기사 × 후보 selector마다 한 줄씩 CSV에 덧붙인다 (매체별로 여러 번 실행해 한 파일에 모은다). 쓴 줄 수.
    본문_글자수는 잡음을 지운 뒤(body_text), 원문_글자수는 칸 안 글자 전부. 성공은 본문이 lead_min_chars 이상.
    subtitle은 subtitle_selector 칸(본문에서는 뺀다), is_paywalled는 paywall_selectors 칸이 페이지에 있는지 (기사 단위)."""
    import csv

    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", newline="", encoding="utf-8-sig" if new else "utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(REPORT_FIELDS)
        for f in fetches:
            base = [src.code, f.url, urlsplit(f.url).netloc.lower(), f.robots, f.http_status or "",
                    "예" if f.stopped else "", f.file, f.error]
            if f.html is None:
                writer.writerow([*base, "", "Y" if f.paywalled else "", "", "", "", ""])
                n += 1
                continue
            base += [extract_subtitle(f.html, src.subtitle_selector) or "",
                     ("Y" if is_paywalled(f.html, src.paywall_selectors, src.paywall_text) else "N")
                     if src.paywall_selectors else ""]
            for selector in probe_candidates(src, selectors):
                text = source_body_text(f.html, src, selector)
                raw = raw_text_chars(f.html, selector)
                writer.writerow([*base, selector, "" if text is None else len(text), "" if raw is None else raw,
                                 "O" if text and len(text) >= config.min_chars else "X"])
                n += 1
    return n


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
                        {"method": src.active_method, "code": src.code, "days": days or config.enqueue_days})
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
        if http_get is None and any(s.active_method == "link" for s in ready):
            http_get = _requests_get(config.user_agent)
        if naver_search is None and any(s.active_method == "naver" for s in ready):
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
                 ("꺼짐" if not src.enabled else ("원문 꺼짐" if not src.fulltext_enabled else "선택자 미확정")))
        out.append((code, n, (src.active_method or src.method) if src else "-", state))
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
    ap.add_argument("--limit", type=int, default=3, help=f"--probe: 받을 기사 수 (기본 3, 최대 {PROBE_MAX})")
    ap.add_argument("--save-fixtures", type=Path, metavar="DIR", help="--probe: 받은 HTML을 저장할 폴더")
    ap.add_argument("--from-naver", action="append", metavar="QUERY",
                    help="--probe: 기사 URL을 DB 대신 네이버 뉴스 검색 originallink에서 고른다 (검색어, 여러 번 지정 가능)")
    ap.add_argument("--max-searches", type=int, default=NAVER_PROBE_MAX_CALLS,
                    help=f"--from-naver: 매체 하나당 검색 API 호출 상한 (기본 {NAVER_PROBE_MAX_CALLS}, 한 번에 100건)")
    ap.add_argument("--report", type=Path, metavar="CSV", help="--probe: 기사×selector 결과를 이 CSV에 덧붙임")
    ap.add_argument("--yes", action="store_true", help="--probe: 요청 전 확인 질문을 건너뜀")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    config = load_config()
    if args.probe:
        src = config.sources.get(args.probe)
        if src is not None and src.method == "link" and not src.fulltext_enabled:
            log.error("%s: lead_sources.yaml에서 fulltext_enabled: false라 원문을 요청하지 않습니다.", args.probe)
            return 1
        if src is None or not src.can_probe:
            log.error("%s: lead_sources.yaml에 link 방식으로 설정된 매체가 아닙니다.", args.probe)
            return 1
        limit = max(1, min(args.limit, PROBE_MAX))
        if args.url:
            urls = args.url[:limit]
        elif args.from_naver:
            import os
            from .naver import DEFAULT_BASE_URL, make_fetcher
            cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
            if not cid or not secret:
                log.error("--from-naver에는 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 필요합니다.")
                return 1
            fetch = make_fetcher(cid, secret, os.environ.get("NAVER_API_BASE_URL", DEFAULT_BASE_URL))
            # 유료·모음 기사를 건너뛰는 매체는 받아 봐야 알 수 있어 여유분(절반)을 더 모은다. 원문은 목표 건수에서 멈춘다
            want = limit + (limit + 1) // 2 if src.skips_after_fetch else limit
            urls, calls = naver_probe_urls(fetch, args.from_naver, src.domains, want, max(1, args.max_searches),
                                           src.url_patterns)
            print(f"[{args.probe}] 네이버 검색 {calls}회(상한 {max(1, args.max_searches)}) → 원본 링크 {len(urls)}건 모음"
                  f" (목표 {limit}건, 검색어 {len(args.from_naver)}개)")
            if len(urls) < limit:
                print(f"  {limit}건이 안 찼습니다. --from-naver 검색어를 더 넣거나 --max-searches를 올리세요.")
        else:
            dsn = get_dsn()
            if not dsn:
                log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
                return 1
            with psycopg.connect(dsn, autocommit=True) as conn:
                urls = probe_urls(conn, args.probe, limit)
        if not urls:
            log.error("확인할 기사 URL이 없습니다.")
            return 1
        extra = (f" (유료·모음 기사는 건너뛰고 {limit}건이 저장되면 멈춤)"
                 if src.skips_after_fetch and len(urls) > limit else "")
        print(f"{args.probe} 매체에 robots.txt 1건 + 기사 최대 {len(urls)}건을 "
              f"{config.interval:g}초 간격으로 요청합니다{extra}. (User-Agent: {config.user_agent})")
        if not args.yes and input("계속할까요? [y/N] ").strip().lower() != "y":
            print("취소했습니다.")
            return 1
        fetches: list[ProbeFetch] = []
        rows, fetched, notes = probe(urls, src, config, _requests_get(config.user_agent),
                                     args.selector, save_dir=args.save_fixtures, fetch_log=fetches, max_pages=limit)
        _print_probe(args.probe, rows, fetched, notes)
        if args.report:
            n = write_probe_report(args.report, src, config, fetches, args.selector)
            print(f"\n{args.report} 에 {n}줄 덧붙였습니다.")
        return 0
    dsn = get_dsn()
    if not dsn:
        log.error("DB 접속 정보가 없습니다. .env의 DATABASE_URL 또는 POSTGRES_*를 확인하세요.")
        return 1
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
