"""과거 뉴스 목록 백필(backfill_list)·확인 도구(backfill_check) 테스트. 네트워크·DB 없이 가짜 응답으로 확인한다."""
import json
from collections import Counter
from datetime import date, datetime, timedelta

from backend.pipelines.news import backfill_check as bc
from backend.pipelines.news import backfill_list as bl
from backend.pipelines.news.lead_fetcher import LeadConfig
from backend.pipelines.news.rss import KST, UTC

DAY = date(2026, 10, 27)

HK_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url><loc>https://www.hankyung.com/article/2026102790967</loc><lastmod>2026-10-27T23:54:20+09:00</lastmod></url>
   <url><loc>https://www.hankyung.com/article/202610264187g</loc><lastmod>2026-10-27T15:00:02+09:00</lastmod></url>
   <url><loc>https://www.hankyung.com/article/2026092612345</loc><lastmod>2026-10-27T10:00:00+09:00</lastmod></url>
   <url><loc>https://www.hankyung.com/article/2026102790967</loc></url>
   <url><loc>https://www.hankyung.com/tag/삼성</loc></url>
</urlset>"""

MK_SITEMAP = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              '<url><loc>https://www.mk.co.kr/news/society/12187776</loc></url>'
              '<url><loc>https://www.mk.co.kr/news/stock/12187661</loc></url>'
              '<url><loc>https://stock.mk.co.kr/news/view/1</loc></url></urlset>')


def hk_page(title, published, desc=None, section="사건사고"):
    desc = desc if desc is not None else f"{title}, 장지민 기자, 사회"
    return (f"<html><head><meta property='og:title' content='{title}' />"
            f"<meta property='og:description' content='{desc}' />"
            f"<meta property='article:section' content='{section}'>"
            f"<meta property='article:published_time' content='{published}'></head><body></body></html>")


def mk_page(title, published, desc="용수부족·강풍에 진화 난항", meta_time=True):
    head = f"<meta property='og:title' content='{title} - 매일경제'><meta property='og:description' content='{desc}' />"
    if meta_time:
        head += f"<meta property='article:published_time' content='{published}'>"
    else:
        head += ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle",'
                 f'"datePublished": "{published}"}}</script>')
    return f"<html><head>{head}</head><body></body></html>"


class Resp:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text


def http(routes):
    calls = []

    def get(url):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return Resp(200, "User-agent: *\nDisallow: /api/\n")
        value = routes.get(url, Resp(404, ""))
        if isinstance(value, Exception):
            raise value
        return value
    get.calls = calls
    return get


def make_env(routes, existing=(), lag=None, now=None):
    saved = []

    def save(articles):
        new = [a for a in articles if a.url_norm not in {s.url_norm for s in saved}]
        saved.extend(new)
        return len(new)

    env = bl.Env(http_get=http(routes), config=LeadConfig(sources={}, interval=4.0, max_attempts=2),
                 existing_urls=lambda urls: {u for u in urls if u in set(existing)}, save=save,
                 lag_check=lag, sleep=lambda s: None, clock=lambda: 0.0,
                 now_kst=now or (lambda: datetime(2026, 11, 12, 2, 0, tzinfo=KST)))
    env.saved = saved
    return env


HK_ROUTES = {
    "https://www.hankyung.com/sitemap/daily-article/20261027.xml": Resp(200, HK_SITEMAP),
    "https://www.hankyung.com/article/2026102790967": Resp(200, hk_page("구룡마을 주불 진화", "2026-10-27T23:54:20+09:00")),
    "https://www.hankyung.com/article/202610264187g": Resp(200, hk_page(
        "외국인 몰리더니 2700억", "2026-10-27T15:00:02+09:00",
        desc="외국인 몰리더니 2700억, &amp;#039;K굿즈&amp;#039; 열풍 탄 아트박스", section="생활경제")),
    "https://www.hankyung.com/article/2026092612345": Resp(200, hk_page("한 달 전 기사", "2026-09-26T10:00:00+09:00")),
}


# ---------------------------------------------------------------- 사이트맵·메타

def test_parse_sitemap_dedupes_and_candidates_filter_paths():
    locs = bl.parse_sitemap(HK_SITEMAP)
    assert len(locs) == 4                          # 중복 loc 제거
    urls = bl.candidate_urls("hankyung", locs)
    assert urls == ["https://www.hankyung.com/article/2026102790967",
                    "https://www.hankyung.com/article/202610264187g",
                    "https://www.hankyung.com/article/2026092612345"]
    mk = bl.candidate_urls("mk", bl.parse_sitemap(MK_SITEMAP))
    assert mk == ["https://www.mk.co.kr/news/society/12187776", "https://www.mk.co.kr/news/stock/12187661"]
    assert bl.candidate_urls("mk", bl.parse_sitemap(MK_SITEMAP), {"stock"}) == [
        "https://www.mk.co.kr/news/stock/12187661"]


def test_extract_meta_hankyung_strips_title_and_byline_from_description():
    meta = bl.extract_meta("hankyung", "https://www.hankyung.com/article/1", hk_page("구룡마을 주불 진화",
                                                                                      "2026-10-27T23:54:20+09:00"))
    assert meta.title == "구룡마을 주불 진화"
    assert meta.published_at == datetime(2026, 10, 27, 14, 54, 20, tzinfo=UTC)
    assert meta.summary is None                    # "제목, 기자명 기자, 섹션"뿐이면 요약 없음
    assert meta.section == "사건사고"
    meta2 = bl.extract_meta("hankyung", "u", HK_ROUTES["https://www.hankyung.com/article/202610264187g"].text)
    assert meta2.summary == "'K굿즈' 열풍 탄 아트박스"   # 두 번 이스케이프된 문자도 푼다


def test_extract_meta_mk_suffix_section_and_jsonld_fallback():
    url = "https://www.mk.co.kr/news/society/12187776"
    meta = bl.extract_meta("mk", url, mk_page("강남 구룡마을서 큰불", "2026-10-27T23:22:27+09:00"))
    assert meta.title == "강남 구룡마을서 큰불"     # " - 매일경제" 제거
    assert meta.section == "society"               # URL 경로
    assert meta.summary == "용수부족·강풍에 진화 난항"
    meta2 = bl.extract_meta("mk", url, mk_page("제목", "2026-10-27T07:00:00+09:00", meta_time=False))
    assert meta2.published_at == datetime(2026, 10, 26, 22, 0, tzinfo=UTC)   # JSON-LD datePublished
    meta3 = bl.extract_meta("mk", url, "<html><head><meta property='og:title' content='x'>"
                                       "<meta property='article:published' content='2026-10-27' /></head></html>")
    assert meta3.published_at is None              # 날짜만 있고 시각이 없으면 못 읽은 것으로 본다


# ---------------------------------------------------------------- 날짜 거르기·저장

def test_run_source_keeps_only_target_day_and_skips_existing_urls():
    env = make_env(HK_ROUTES, existing={"https://www.hankyung.com/article/2026102790967"})
    status, stat = bl.run_source("hankyung", DAY, env)
    assert status == "done"
    assert stat["already_in_db"] == 1              # DB에 있는 URL은 요청하지 않는다
    assert "https://www.hankyung.com/article/2026102790967" not in env.http_get.calls
    assert stat["matched"] == 1 and stat["other_date"] == 1 and stat["inserted"] == 1
    art = env.saved[0]
    assert art.source_code == "hankyung" and art.publisher == "한국경제" and art.section == "생활경제"
    assert art.published_at.astimezone(KST).date() == DAY and art.content_hash


def test_run_source_dry_run_saves_nothing_and_limit_marks_partial():
    env = make_env(HK_ROUTES)
    env.save = None
    status, stat = bl.run_source("hankyung", DAY, env, limit=1)
    assert status == "partial" and stat["fetched"] == 1 and stat["inserted"] == 0


def test_run_source_stops_source_on_403():
    routes = dict(HK_ROUTES)
    routes["https://www.hankyung.com/article/2026102790967"] = Resp(429, "")
    env = make_env(routes)
    status, stat = bl.run_source("hankyung", DAY, env)
    assert status == "blocked" and stat["blocked_http"] == 429
    assert "https://www.hankyung.com/article/202610264187g" not in env.http_get.calls   # 남은 기사는 요청하지 않음
    assert bl.exit_code({"hankyung": (status, stat)}) == bl.EXIT_BLOCKED


def test_run_source_records_failures_and_missing_published(tmp_path):
    routes = dict(HK_ROUTES)
    routes["https://www.hankyung.com/article/2026102790967"] = Resp(200, "<html><head>"
                                                                       "<meta property='og:title' content='t'></head></html>")
    routes["https://www.hankyung.com/article/2026092612345"] = Resp(503, "")
    env = make_env(routes)
    failures = bl.Failures(tmp_path / "failures_2026-10-27.jsonl")
    status, stat = bl.run_source("hankyung", DAY, env, failures=failures)
    assert status == "done" and stat["failed"] == 2 and stat["matched"] == 1
    rows = [json.loads(l) for l in (tmp_path / "failures_2026-10-27.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["reason"].split(" (")[0] for r in rows} == {"발행 시각 없음", "HTTP 503"}


def test_no_sitemap_is_not_done():
    env = make_env({})
    status, _ = bl.run_source("mk", DAY, env)
    assert status == "no_sitemap"


# ---------------------------------------------------------------- 안전장치

def test_lag_stop_halts_all_sources():
    calls = Counter()

    def lag():
        calls["n"] += 1
        return {"lagging": 3, "max_hours": 2.5, "checked": 10, "examples": [(1, 2.5)]}

    env = make_env(HK_ROUTES, lag=lag)
    progress = bl.Progress(path=None, enabled=False)
    results = bl.run_day(DAY, ["hankyung", "mk"], env, progress, bl.Failures(None, enabled=False))
    assert {s for s, _ in results.values()} == {"lag_stop"}
    assert bl.exit_code(results) == bl.EXIT_LAG
    assert env.http_get.calls == []                # 시작 전 확인에서 멈춰 요청을 하나도 보내지 않는다


def test_lag_checked_every_50_pages(monkeypatch):
    monkeypatch.setattr(bl, "LAG_EVERY", 2)
    seen = []
    env = make_env(HK_ROUTES, lag=lambda: seen.append(1) or {"lagging": 0, "checked": 5})
    bl.run_source("hankyung", DAY, env)
    assert len(seen) == 1                          # 페이지 3개 → 2개째 다음 확인 1번


def test_pause_window_waits_until_0730():
    t = [datetime(2026, 11, 12, 6, 50, tzinfo=KST)]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += timedelta(seconds=s)

    env = make_env(HK_ROUTES, now=lambda: t[0])
    env.sleep = sleep
    bl.wait_pause(env)
    assert t[0] >= datetime(2026, 11, 12, 7, 30, tzinfo=KST) and sum(slept) >= 40 * 60
    assert not bl.in_pause(datetime(2026, 11, 12, 7, 30, tzinfo=KST))
    assert bl.in_pause(datetime(2026, 11, 12, 6, 0, tzinfo=KST))


def test_progress_skips_done_dates_and_force_reruns(tmp_path):
    path = tmp_path / "progress.json"
    progress = bl.Progress(path)
    env = make_env(HK_ROUTES)
    first = bl.run_day(DAY, ["hankyung"], env, progress, bl.Failures(None, enabled=False))
    assert first["hankyung"][0] == "done"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["hankyung"]["2026-10-27"]["status"] == "done" and data["hankyung"]["2026-10-27"]["inserted"] == 2

    env2 = make_env(HK_ROUTES)
    again = bl.run_day(DAY, ["hankyung"], env2, bl.Progress(path), bl.Failures(None, enabled=False))
    assert again["hankyung"][0] == "skipped_done" and env2.http_get.calls == []
    forced = bl.run_day(DAY, ["hankyung"], env2, bl.Progress(path), bl.Failures(None, enabled=False), force=True)
    assert forced["hankyung"][0] == "done"


def test_main_refuses_recent_dates_without_flag():
    assert bl.main(["--date", "2026-11-11", "--dry-run"]) == bl.EXIT_REFUSED


# ---------------------------------------------------------------- backfill_check

def test_lagging_counts_old_fetches_without_chunks():
    now = datetime(2026, 11, 12, 12, 0, tzinfo=KST)
    records = [
        {"news_id": 1, "fetched_at": "2026-11-12T09:00:00+09:00"},   # 3시간, 청크 없음 → 지연
        {"news_id": 2, "fetched_at": "2026-11-12T11:00:00+09:00"},   # 1시간 → 아직 아님
        {"news_id": 3, "fetched_at": "2026-11-12T08:00:00+09:00"},   # 청크 있음
        {"news_id": 4, "fetched_at": "2026-11-12T08:00:00+09:00"},   # news_articles에 없음 (다른 DB 기록)
        {"news_id": 1, "fetched_at": "2026-11-12T10:30:00+09:00"},   # 같은 기사 다시 받음 → 이른 시각 기준
    ]
    late = bc.lagging(records, loaded_ids={3}, known_ids={1, 2, 3}, now=now)
    assert late == [(1, 3.0)]


def test_raw_counts_uses_last_status(tmp_path):
    lines = [{"url": "u1", "source_code": "mk", "status": "failed"},
             {"url": "u1", "source_code": "mk", "status": "ok"},
             {"url": "u2", "source_code": "mk", "status": "skipped"},
             {"url": "u3", "source_code": "hankyung", "status": "failed"}]
    (tmp_path / "2026-10-27.jsonl").write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
    out = bc.raw_counts(tmp_path, DAY, ["hankyung", "mk"])
    assert out["mk"] == {"ok": 1, "skipped": 1, "failed": 0} and out["hankyung"]["failed"] == 1
