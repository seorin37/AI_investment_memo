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
    get2 = http({})
    stats = ft.collect(rows, cfg(), get2, tmp_path, sleep=lambda s: None)
    assert stats["hankyung"]["already"] == 1 and stats["hankyung"]["gave_up"] == 1   # ok는 건너뛰고, 3번 실패는 포기
    assert get2.calls == []


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


def test_day_window_is_kst():
    from datetime import date
    start, end = ft.day_window(date(2026, 11, 5))
    assert start.isoformat() == "2026-11-04T15:00:00+00:00" and end.isoformat() == "2026-11-05T15:00:00+00:00"
