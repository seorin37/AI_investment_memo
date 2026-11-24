"""원문 수집(fulltext) 테스트. 네트워크·DB 없이 가짜 응답으로 확인한다."""
import json

from backend.pipelines.news import fulltext as ft
from backend.pipelines.news.lead_fetcher import LeadConfig, SourceConfig

BODY = "삼성전자가 엔비디아에 6세대 고대역폭메모리(HBM4)를 공급한다. " * 4
PAGE = f"<html><head><meta property='og:title' content='삼성 HBM4 공급'></head><body><div id='b'>{BODY}</div></body></html>"
PAID = "<html><body><div id='b'><div class='box-cont'>한경 프리미엄9에 실린 기사입니다.</div>" + BODY + "</div></body></html>"
SHORT = "<html><body><div id='b'>짧은 사진 설명입니다.</div></body></html>"


class Resp:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text


def http(routes):
    calls = []

    def get(url):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return Resp(200, "User-agent: *\nAllow: /\n")
        value = routes.get(url, Resp(200, PAGE))
        if isinstance(value, Exception):
            raise value
        if isinstance(value, list):                    # 차례로 다른 응답
            return value.pop(0)
        return value
    get.calls = calls
    return get


def cfg(**over):
    hk = SourceConfig("hankyung", "link", True, ("hankyung.com",), "#b", paywall_selectors=("div.box-cont",),
                      paywall_text="프리미엄", skip_paywalled=True, skip_title_patterns=(r"^\[포토\]",))
    yh = SourceConfig("yonhap", "link", True, ("yna.co.kr",), "#b", url_patterns=("^/view/AKR",))
    off = SourceConfig("mk", "link", True, ("www.mk.co.kr",), "#b", fulltext_enabled=False)
    return LeadConfig(sources={"hankyung": hk, "yonhap": yh, "mk": off}, interval=4.0, max_attempts=3,
                      min_body_chars=100, **over)


def row(i, url, code="hankyung", title="삼성 HBM4 공급"):
    return ft.ArticleRow(i, code, url, title, "2026-11-05T09:00:00+09:00")


def lines(out):
    return [json.loads(l) for p in sorted(out.glob("*.jsonl")) for l in p.read_text(encoding="utf-8").splitlines()]


def test_collect_writes_ok_and_skips_by_rule(tmp_path):
    get = http({"https://www.hankyung.com/article/2": Resp(200, PAID),
                "https://www.hankyung.com/article/3": Resp(200, SHORT)})
    rows = [row(1, "https://www.hankyung.com/article/1"), row(2, "https://www.hankyung.com/article/2"),
            row(3, "https://www.hankyung.com/article/3"), row(4, "https://www.hankyung.com/article/4", title="[포토] 코스피"),
            row(5, "https://www.yna.co.kr/view/PYH1", "yonhap"), row(6, "https://www.mk.co.kr/article/6", "mk"),
            row(7, "http://www.hankyung.com/article/1?utm_source=naver")]  # 같은 링크(정규화 기준)는 한 번만
    stats = ft.collect(rows, cfg(), get, tmp_path, sleep=lambda s: None)
    recs = {r["news_id"]: r for r in lines(tmp_path)}
    assert (tmp_path / "2026-11-05.jsonl").exists()
    ok = recs[1]
    assert ok["status"] == "ok" and ok["body"].startswith("삼성전자가") and ok["body_chars"] == len(ok["body"])
    assert ok["body_hash"] == ft.sha256_text(ok["body"]) and ok["extractor_version"].startswith("hankyung-")
    assert ok["fetch_method"] == "link" and ok["attempts"] == 1
    assert recs[2]["status"] == "skipped" and recs[2]["reason"].startswith("유료 기사") and recs[2]["body"] is None
    assert recs[3]["reason"].startswith("본문 짧음")
    assert recs[4]["reason"].startswith("포토 기사")
    assert recs[5]["reason"].startswith("URL 패턴")
    assert 6 not in recs and stats["mk"]["not_ready"] == 1                 # fulltext_enabled: false → 요청 안 함
    assert 7 not in recs
    assert "https://www.hankyung.com/article/4" not in get.calls and "https://www.yna.co.kr/view/PYH1" not in get.calls
    assert stats["hankyung"]["ok"] == 1 and stats["hankyung"]["skipped"] == 3
    assert "유료" in ft.report(stats) and "hankyung" in ft.report(stats)


def test_already_collected_links_are_skipped_and_failed_retried(tmp_path):
    get = http({"https://www.hankyung.com/article/9": [Resp(503), Resp(503), Resp(503)]})
    rows = [row(1, "https://www.hankyung.com/article/1"), row(9, "https://www.hankyung.com/article/9")]
    slept = []
    ft.collect(rows, cfg(), get, tmp_path, sleep=slept.append)
    recs = {r["news_id"]: r for r in lines(tmp_path)}
    assert recs[9]["status"] == "failed" and recs[9]["attempts"] == 3 and recs[9]["http_status"] == 503
    assert 8.0 in slept                                                      # 재시도 간격을 늘려 간다 (4초 × 시도 횟수)
    # 다음 실행: ok는 건너뛰고 failed는 다시 시도한다. failed로 끝난 실행이 fulltext_max_runs(3)번이면 포기
    for _ in range(2):
        get2 = http({"https://www.hankyung.com/article/9": Resp(503)})
        stats = ft.collect(rows, cfg(), get2, tmp_path, sleep=lambda s: None)
        assert stats["hankyung"]["already"] == 1 and stats["hankyung"]["failed"] == 1
        assert get2.calls.count("https://www.hankyung.com/article/9") == 3        # 실행마다 max_attempts번까지
    get3 = http({})
    stats = ft.collect(rows, cfg(), get3, tmp_path, sleep=lambda s: None)
    assert stats["hankyung"]["gave_up"] == 1 and get3.calls == []
    assert ft.load_done(tmp_path)[ft.normalize_url(rows[1].url)] == ft.Seen("failed", 9, 3)


def test_timeout_then_success_and_stop_on_429(tmp_path):
    calls = {"n": 0}

    def flaky(url):
        if url.endswith("/robots.txt"):
            return Resp(200, "User-agent: *\nAllow: /\n")
        if url.endswith("/1"):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError()
            return Resp(200, PAGE)
        return Resp(429)
    rows = [row(1, "https://www.hankyung.com/article/1"), row(2, "https://www.hankyung.com/article/2"),
            row(3, "https://www.hankyung.com/article/3")]
    stats = ft.collect(rows, cfg(), flaky, tmp_path, sleep=lambda s: None)
    recs = {r["news_id"]: r for r in lines(tmp_path)}
    assert recs[1]["status"] == "ok" and recs[1]["attempts"] == 2              # 타임아웃 뒤 재시도 성공
    assert recs[2]["status"] == "failed" and "429" in recs[2]["reason"]
    assert 3 not in recs and stats["hankyung"]["stopped"] == 1                 # 429 뒤 이 매체는 멈춤


def test_empty_body_is_failed_for_retry(tmp_path):                  # 2026-11-06 매경 [속보] 본문 0자
    empty = "<html><body><div id='b'> </div></body></html>"
    get = http({"https://www.hankyung.com/article/1": Resp(200, empty)})
    ft.collect([row(1, "https://www.hankyung.com/article/1", title="[속보] 다우 3% 급등")], cfg(), get, tmp_path,
               sleep=lambda s: None)
    rec = lines(tmp_path)[0]
    assert rec["status"] == "failed" and rec["reason"].startswith("본문 비어 있음")     # 다음 실행에서 다시 받는다


def test_failed_run_then_success(tmp_path):                         # 본문이 나중에 채워진 속보
    empty = "<html><body><div id='b'> </div></body></html>"
    r = row(1, "https://www.hankyung.com/article/1", title="[속보] 다우 3% 급등")
    ft.collect([r], cfg(), http({"https://www.hankyung.com/article/1": Resp(200, empty)}), tmp_path, sleep=lambda s: None)
    stats = ft.collect([r], cfg(), http({}), tmp_path, sleep=lambda s: None)
    assert stats["hankyung"]["ok"] == 1 and [x["status"] for x in lines(tmp_path)] == ["failed", "ok"]
    assert ft.collect([r], cfg(), http({}), tmp_path, sleep=lambda s: None)["hankyung"]["already"] == 1


def test_load_done_reads_only_given_days(tmp_path):
    (tmp_path / "2026-11-04.jsonl").write_text(json.dumps({"url": "https://a/1", "status": "ok", "attempts": 1}) + "\n",
                                               encoding="utf-8")
    (tmp_path / "2026-11-05.jsonl").write_text(json.dumps({"url": "https://a/2", "status": "failed", "attempts": 1}) + "\n",
                                               encoding="utf-8")
    from datetime import date
    assert set(ft.load_done(tmp_path)) == {"https://a/1", "https://a/2"}
    only = ft.load_done(tmp_path, [date(2026, 11, 5), date(2026, 11, 6)])        # 없는 날짜 파일은 건너뛴다
    assert only == {"https://a/2": ft.Seen("failed", 1, 1)}


def test_recent_window_and_days():
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    now = datetime(2026, 11, 8, 3, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    start, end = ft.recent_window(6, now)
    assert start.isoformat() == "2026-11-07T12:00:00+00:00" and end.isoformat() == "2026-11-07T18:00:00+00:00"
    assert ft.window_days(start, end) == [date(2026, 11, 7), date(2026, 11, 8)]       # 전날 21시~ → 이틀 파일
    assert ft.window_days(*ft.day_window(date(2026, 11, 5))) == [date(2026, 11, 5)]


def test_day_window_is_kst():
    from datetime import date
    start, end = ft.day_window(date(2026, 11, 5))
    assert start.isoformat() == "2026-11-04T15:00:00+00:00" and end.isoformat() == "2026-11-05T15:00:00+00:00"


def test_record_from_page_matches_fetch_one(tmp_path):
    """판정 함수(record_from_page)는 fetch_one이 같은 페이지를 받았을 때와 같은 기록을 만든다 (백필 목록 단계가 재사용)."""
    config = cfg()
    src = config.sources["hankyung"]
    version = ft.extractor_version(src)
    fixed = lambda: __import__("datetime").datetime(2026, 11, 12, 10, 0, tzinfo=ft.KST)   # noqa: E731
    for i, page in enumerate([PAGE, PAID, SHORT, "<html><body><div id=b></div></body></html>"], 1):
        r = row(i, f"https://www.hankyung.com/article/{i}")
        get = http({r.url: Resp(200, page)})
        from backend.pipelines.news import lead_fetcher as lf
        throttle = lf.Throttle(4.0, lambda s: None, lambda: 0.0)
        fetched = ft.fetch_one(r, src, config, get, lf.RobotsCache(get, config.user_agent, throttle), throttle, version,
                               sleep=lambda s: None, now=fixed)
        judged = ft.record_from_page(r, src, config, version, 200, page, 1, fixed)
        assert judged == fetched
    assert ft.precheck_reason(row(9, "https://www.hankyung.com/article/9", title="[포토] 코스피"), src).startswith("포토")
    assert ft.precheck_reason(row(9, "https://www.hankyung.com/article/9"), src) is None
