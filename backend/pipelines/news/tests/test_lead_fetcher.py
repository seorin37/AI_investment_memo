"""리드 보충 테스트. 네트워크 없이 가짜 응답·가짜 시계로 요청 규칙과 추출을 확인한다."""
from dataclasses import replace

import pytest

from backend.pipelines.news import lead_fetcher as lf
from backend.pipelines.news.lead_fetcher import (LeadConfig, PendingItem, SourceConfig, extract_lead,
                                                 fetch_leads, lead_from_naver_items, load_config)

ARTICLE_HTML = """
<html><body><div id="articletxt">
  <figure><img src="x.jpg"><figcaption>사진 설명은 빠져야 한다</figcaption></figure>
  (서울=연합뉴스) 홍길동 기자 = 삼성전자가 엔비디아에 6세대 고대역폭메모리(HBM4)를 공급한다.
  업계에 따르면 삼성전자는 27일 엔비디아와 HBM4 공급 계약을 맺었다.
  계약 규모는 수조 원대로 알려졌다. 네 번째 문장은 리드에 들어가지 않는다.
  <div class="related">관련 기사 목록</div>
  gildong@yna.co.kr
  <p>&lt;저작권자(c) 연합뉴스, 무단 전재-재배포 금지&gt;</p>
</div></body></html>
"""


class Resp:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text


class FakeClock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 3))
        self.now += seconds


def cfg(**sources):
    base = {
        "hankyung": SourceConfig("hankyung", "link", True, ("hankyung.com",), "#articletxt"),
        "sedaily": SourceConfig("sedaily", "naver", True),
    }
    base.update(sources)
    return LeadConfig(sources=base, interval=4.0, max_attempts=3)


def item(news_id, url="https://www.hankyung.com/article/1", code="hankyung", attempts=0, title="제목"):
    return PendingItem(news_id, code, title, url, attempts)


def http(routes):
    """url → Resp. robots.txt는 기본으로 모두 허용."""
    calls = []

    def get(url):
        calls.append(url)
        if url.endswith("/robots.txt") and url not in routes:
            return Resp(200, "User-agent: *\nAllow: /\n")
        value = routes.get(url, Resp(200, ARTICLE_HTML))
        if isinstance(value, Exception):
            raise value
        return value
    get.calls = calls
    return get


# ---------------------------------------------------------------- 추출

def test_extract_lead_takes_first_sentences_and_drops_noise():
    lead = extract_lead(ARTICLE_HTML, "#articletxt", drop_selectors=[".related"])
    assert lead.startswith("삼성전자가 엔비디아에 6세대")          # 머리말 "(서울=연합뉴스) 홍길동 기자 =" 제거
    assert "업계에 따르면" in lead and "계약 규모는" in lead
    assert "네 번째 문장" not in lead                               # 최대 3문장
    for noise in ("사진 설명", "관련 기사", "@", "무단", "저작권"):
        assert noise not in lead
    assert len(lead) <= 300


def test_extract_lead_respects_length_limits():
    long_sentence = "가" * 400 + "."
    html = f'<div id="b">{long_sentence}</div>'
    assert len(extract_lead(html, "#b")) == 300                     # 첫 문장이 길면 300자로 자름
    assert extract_lead('<div id="b">짧은 글.</div>', "#b") is None  # 40자 미만이면 실패
    assert extract_lead(ARTICLE_HTML, "#없는칸") is None              # 선택자가 틀리면 실패


def test_naver_lead_matches_only_same_original_url():
    items = [
        {"originallink": "https://www.sedaily.com/article/2", "description": "다른 기사 요약"},
        {"originallink": "https://www.sedaily.com/article/1?utm_source=naver", "description": "<b>같은</b> 기사 요약입니다"},
    ]
    assert lead_from_naver_items(items, "https://www.sedaily.com/article/1") == "같은 기사 요약입니다"
    assert lead_from_naver_items(items, "https://www.sedaily.com/article/9") is None
    assert lead_from_naver_items([], "https://www.sedaily.com/article/1") is None


# ---------------------------------------------------------------- 요청 규칙

def test_same_host_requests_are_spaced_by_interval():
    fc = FakeClock()
    get = http({})
    items = [item(i, f"https://www.hankyung.com/article/{i}") for i in range(1, 4)]
    results, _ = fetch_leads(items, cfg(), get, sleep=fc.sleep, clock=fc.clock)
    assert [r.status for r in results] == ["ok"] * 3
    assert get.calls[0] == "https://www.hankyung.com/robots.txt"    # robots.txt 먼저, 한 번만
    assert get.calls.count("https://www.hankyung.com/robots.txt") == 1
    assert fc.slept == [4.0, 4.0, 4.0]                               # robots 뒤 + 기사 사이마다 4초


def test_robots_disallow_skips_without_requesting_article():
    get = http({"https://www.hankyung.com/robots.txt": Resp(200, "User-agent: *\nDisallow: /article/\n")})
    results, _ = fetch_leads([item(1)], cfg(), get, sleep=lambda s: None)
    assert results[0].status == "skipped" and "robots" in results[0].error
    assert get.calls == ["https://www.hankyung.com/robots.txt"]


def test_robots_404_allows_and_5xx_defers():
    ok = http({"https://www.hankyung.com/robots.txt": Resp(404)})
    assert fetch_leads([item(1)], cfg(), ok, sleep=lambda s: None)[0][0].status == "ok"
    down = http({"https://www.hankyung.com/robots.txt": Resp(503)})
    r = fetch_leads([item(1)], cfg(), down, sleep=lambda s: None)[0][0]
    assert (r.status, r.attempts) == ("pending", 1)
    assert down.calls == ["https://www.hankyung.com/robots.txt"]


def test_403_stops_that_source_for_this_run():
    urls = [f"https://www.hankyung.com/article/{i}" for i in range(1, 4)]
    get = http({urls[1]: Resp(403)})
    naver = lambda q: [{"originallink": "https://www.sedaily.com/a/1", "description": "서울경제 기사 요약 " * 4}]
    items = [item(i + 1, u) for i, u in enumerate(urls)] + [item(9, "https://www.sedaily.com/a/1", "sedaily")]
    results, stats = fetch_leads(items, cfg(), get, naver, sleep=lambda s: None)
    by_id = {r.news_id: r for r in results}
    assert by_id[1].status == "ok"
    assert (by_id[2].status, by_id[2].http_status) == ("pending", 403)
    assert 3 not in by_id and urls[2] not in get.calls               # 403 뒤로는 요청하지 않음
    assert by_id[9].status == "ok"                                   # 다른 매체는 계속
    assert stats.stopped_sources == ["hankyung"]


def test_transient_errors_retry_then_fail():
    get = http({"https://www.hankyung.com/article/1": Resp(502)})
    assert fetch_leads([item(1, attempts=0)], cfg(), get, sleep=lambda s: None)[0][0].status == "pending"
    assert fetch_leads([item(1, attempts=2)], cfg(), get, sleep=lambda s: None)[0][0].status == "failed"
    timeout = http({"https://www.hankyung.com/article/1": TimeoutError()})
    r = fetch_leads([item(1)], cfg(), timeout, sleep=lambda s: None)[0][0]
    assert (r.status, r.attempts) == ("pending", 1) and "TimeoutError" in r.error


def test_404_and_extraction_failure_are_final():
    get = http({"https://www.hankyung.com/article/1": Resp(404),
                "https://www.hankyung.com/article/2": Resp(200, "<html>본문 없음</html>")})
    results, _ = fetch_leads([item(1), item(2, "https://www.hankyung.com/article/2")], cfg(), get,
                             sleep=lambda s: None)
    assert [r.status for r in results] == ["failed", "failed"]
    assert "선택자" in results[1].error


def test_other_domain_is_skipped_without_request():
    get = http({})
    r = fetch_leads([item(1, "https://evil.example.com/a")], cfg(), get, sleep=lambda s: None)[0][0]
    assert (r.status, r.source) == ("skipped", "none")
    assert get.calls == []


def test_not_ready_sources_send_nothing():
    get = http({})
    unready = cfg(hankyung=SourceConfig("hankyung", "link", True, ("hankyung.com",), None),
                  sedaily=SourceConfig("sedaily", "naver", False))
    results, stats = fetch_leads([item(1), item(2, "https://www.sedaily.com/a", "sedaily")], unready, get,
                                 naver_search=lambda q: pytest.fail("호출되면 안 됨"), sleep=lambda s: None)
    assert results == [] and get.calls == []
    assert stats.not_ready_sources == ["hankyung", "sedaily"]


def test_naver_no_match_retries():
    r = fetch_leads([item(1, "https://www.sedaily.com/a", "sedaily")], cfg(), None,
                    naver_search=lambda q: [], sleep=lambda s: None)[0][0]
    assert (r.status, r.source, r.attempts) == ("pending", "naver", 1)


# ---------------------------------------------------------------- 설정

def test_shipped_config_sends_no_requests():
    config = load_config()
    assert set(config.sources) == {"hankyung", "mk", "yonhap", "sedaily"}
    assert not any(s.enabled for s in config.sources.values())
    assert not any(s.ready for s in config.sources.values())
    assert config.sources["sedaily"].method == "naver"            # 약관상 링크 수집 안 함
    assert config.user_agent.startswith("memos-news-collector/")
    # 준비된 매체가 없으면 DB에 손대지 않고 끝난다 (conn=None이어도 됨)
    assert lf.run(None, config)["skipped"] == "no_ready_source"


def test_config_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n  x: {method: web}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad)
    fast = tmp_path / "fast.yaml"
    fast.write_text("request_interval_seconds: 0.1\nsources: {}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(fast)
