"""리드 보충 테스트. 네트워크 없이 가짜 응답·가짜 시계로 요청 규칙과 추출을 확인한다."""
import csv
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


def test_404_is_final_and_empty_body_is_retried_until_last_attempt():
    get = http({"https://www.hankyung.com/article/1": Resp(404),
                "https://www.hankyung.com/article/2": Resp(200, "<html>본문 없음</html>")})
    results, _ = fetch_leads([item(1), item(2, "https://www.hankyung.com/article/2")], cfg(), get,
                             sleep=lambda s: None)
    assert [r.status for r in results] == ["failed", "pending"]   # 본문이 아직 안 채워졌을 수 있어 다시 시도
    assert "선택자" in results[1].error
    last = fetch_leads([item(2, "https://www.hankyung.com/article/2", attempts=2)], cfg(), get,
                       sleep=lambda s: None)[0][0]
    assert last.status == "failed"


def test_last_attempt_falls_back_to_meta_description():
    desc = "영업이익 83조 원으로 632% 증가했다. 6개 분기 연속 역대 최대 실적을 냈고 3분기 배당은 주당 2만 원으로 정했다."
    html = f'<html><head><meta property="og:description" content="{desc}"></head><body>본문 칸 없음</body></html>'
    get = http({"https://www.hankyung.com/article/1": Resp(200, html)})
    first = fetch_leads([item(1)], cfg(), get, sleep=lambda s: None)[0][0]
    assert first.status == "pending"                                  # 처음에는 본문이 채워지길 기다린다
    last = fetch_leads([item(1, attempts=2)], cfg(), get, sleep=lambda s: None)[0][0]
    assert last.status == "ok" and "영업이익" in last.lead_text


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


# ---------------------------------------------------------------- selector 찾기 (--probe)

MENU_HTML = """<html><body><article><nav>경제 | 증권 | 산업 | 부동산 | 정치 | 사회 | 국제 | 오피니언 | 스포츠 | 연예</nav>
<div id="articletxt">삼성전자가 엔비디아에 6세대 고대역폭메모리(HBM4)를 공급한다. 업계에 따르면 계약을 맺었다.</div>
</article></body></html>"""


def test_probe_ranks_selectors_and_recommends_specific_one(tmp_path):
    fc = FakeClock()
    get = http({"https://www.hankyung.com/a/1": Resp(200, MENU_HTML),
                "https://www.hankyung.com/a/2": Resp(200, MENU_HTML)})
    src = cfg().sources["hankyung"]
    rows, fetched, notes = lf.probe(["https://www.hankyung.com/a/1", "https://www.hankyung.com/a/2"], src, cfg(),
                                    get, sleep=fc.sleep, clock=fc.clock, save_dir=tmp_path)
    assert fetched == 2 and notes == []
    hits = {r.selector: r.hits for r in rows}
    assert hits["#articletxt"] == 2 and hits["article"] == 2 and hits["div.article-body"] == 0
    assert lf.recommend(rows, fetched) == "#articletxt"           # 같은 성공 수면 구체적인 칸 우선
    assert rows[0].samples[0].startswith("삼성전자가")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hankyung_1.html", "hankyung_2.html"]
    assert fc.slept == [4.0, 4.0]                                  # robots 뒤, 기사 사이 4초


def test_probe_stops_on_403_and_respects_robots():
    get = http({"https://www.hankyung.com/a/1": Resp(403)})
    rows, fetched, notes = lf.probe(["https://www.hankyung.com/a/1", "https://www.hankyung.com/a/2"],
                                    cfg().sources["hankyung"], cfg(), get, sleep=lambda s: None)
    assert fetched == 0 and "멈춤" in notes[0]
    assert "https://www.hankyung.com/a/2" not in get.calls
    assert lf.recommend(rows, fetched) is None
    blocked = http({"https://www.hankyung.com/robots.txt": Resp(200, "User-agent: *\nDisallow: /\n")})
    _, fetched, notes = lf.probe(["https://www.hankyung.com/a/1"], cfg().sources["hankyung"], cfg(), blocked,
                                 sleep=lambda s: None)
    assert fetched == 0 and "불허" in notes[0] and blocked.calls == ["https://www.hankyung.com/robots.txt"]


def test_probe_with_given_selector_only():
    get = http({})
    rows, fetched, _ = lf.probe(["https://www.hankyung.com/a/1"], cfg().sources["hankyung"], cfg(), get,
                                selectors=["#articletxt"], sleep=lambda s: None)
    assert [r.selector for r in rows] == ["#articletxt"] and rows[0].hits == 1


def test_probe_fetch_log_and_report(tmp_path):
    get = http({"https://www.hankyung.com/a/1": Resp(200, MENU_HTML), "https://www.hankyung.com/a/2": Resp(429)})
    fetches = []
    lf.probe(["https://www.hankyung.com/a/1", "https://www.hankyung.com/a/2", "https://www.hankyung.com/a/3"],
             cfg().sources["hankyung"], cfg(), get, sleep=lambda s: None, save_dir=tmp_path / "html", fetch_log=fetches)
    assert [(f.robots, f.http_status, f.stopped) for f in fetches] == [("허용", 200, False), ("허용", 429, True)]
    assert fetches[0].file.endswith("hankyung_1.html")
    report = tmp_path / "report.csv"
    n = lf.write_probe_report(report, cfg().sources["hankyung"], cfg(), fetches, ["#articletxt", "div.nope"])
    assert n == 3                                                   # 받은 기사 1건 × selector 2 + 멈춘 기사 1줄
    rows = list(csv.DictReader(report.open(encoding="utf-8-sig")))
    assert [(r["selector"], r["성공"]) for r in rows[:2]] == [("#articletxt", "O"), ("div.nope", "X")]
    assert int(rows[0]["원문_글자수"]) >= int(rows[0]["본문_글자수"]) > 40
    assert rows[2]["멈춤_403_429"] == "예" and rows[2]["http_status"] == "429"
    lf.write_probe_report(report, cfg().sources["hankyung"], cfg(), fetches[:1], ["#articletxt"])   # 덧붙일 때 머리줄 없음
    assert report.read_text(encoding="utf-8-sig").count("매체,url") == 1


def test_naver_probe_urls_keeps_media_domains_with_subdomains():
    calls = []

    def fetch(query, start):
        calls.append(query)
        return {"items": [{"originallink": "https://www.hankyung.com/a/1"}, {"originallink": "https://www.mk.co.kr/b"},
                          {"originallink": "https://plus.hankyung.com/c"}, {"originallink": "https://www.hankyung.com/a/1"}]}
    assert lf.naver_probe_urls(fetch, ["증시", "환율"], ("hankyung.com",), 10) == \
        ["https://www.hankyung.com/a/1", "https://plus.hankyung.com/c"]
    assert lf.naver_probe_urls(fetch, ["증시", "환율"], ("hankyung.com",), 1) == ["https://www.hankyung.com/a/1"]


def test_body_text_keeps_whole_article_and_lead_unchanged():
    html = "<div id='b'>첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다.<figure>사진 설명</figure></div>"
    assert lf.body_text(html, "#b") == "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다."
    assert lf.extract_lead(html, "#b", min_chars=1) == "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."
    assert lf.raw_text_chars(html, "#b") > len(lf.body_text(html, "#b"))   # 사진 설명까지 센다
    assert lf.body_text(html, "#none") is None


SEDAILY_LINK = SourceConfig("sedaily", "link", True, ("sedaily.com",), "div.article_view", fallback="naver")


def test_fulltext_disabled_sends_no_page_request_and_falls_back_to_naver():
    item = PendingItem(1, "sedaily", "삼성전자 실적", "https://www.sedaily.com/a/1")
    get = http({})
    searched = []
    naver = lambda q: searched.append(q) or [{"originallink": item.url, "description": "삼성전자가 3분기 실적을 발표했다. " * 3}]
    on = cfg(sedaily=SEDAILY_LINK)
    results, _ = fetch_leads([item], on, get, naver, sleep=lambda s: None)
    assert results[0].source == "link" and get.calls and not searched     # 원문 허용 + selector 확정 → link
    off = cfg(sedaily=replace(SEDAILY_LINK, fulltext_enabled=False))
    get = http({})
    results, _ = fetch_leads([item], off, get, naver, sleep=lambda s: None)
    assert get.calls == [] and results[0].source == "naver" and searched  # 원문 요청 없이 naver 요약
    no_fallback = cfg(sedaily=replace(SEDAILY_LINK, fulltext_enabled=False, fallback=None))
    get = http({})
    results, stats = fetch_leads([item], no_fallback, get, naver, sleep=lambda s: None)
    assert get.calls == [] and results == [] and stats.not_ready_sources == ["sedaily"]
    pending = cfg(sedaily=replace(SEDAILY_LINK, selector=None))                  # selector 확정 전 → naver
    assert pending.sources["sedaily"].active_method == "naver" and pending.sources["sedaily"].can_probe


def test_probe_cli_refuses_when_fulltext_disabled(monkeypatch):
    monkeypatch.setattr(lf, "load_config", lambda: cfg(sedaily=replace(SEDAILY_LINK, fulltext_enabled=False)))
    monkeypatch.setattr("backend.pipelines.common.db.load_env", lambda: None)
    monkeypatch.setattr(lf, "_requests_get", lambda ua: pytest.fail("fulltext_enabled: false면 요청하면 안 됨"))
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("묻기 전에 멈춰야 함"))
    assert lf.main(["--probe", "sedaily", "--url", "https://www.sedaily.com/a/1"]) == 1


def test_real_config_sedaily_link_with_naver_fallback():
    src = load_config().sources["sedaily"]
    assert (src.method, src.fallback, src.can_probe) == ("link", "naver", True)
    assert src.active_method == ("link" if src.selector else "naver")             # selector 확정 전엔 naver 요약
    assert src.probe_selectors and lf.probe_candidates(src)[:len(src.probe_selectors)] == list(src.probe_selectors)


def test_probe_cli_asks_before_sending(monkeypatch, capsys):
    monkeypatch.setattr(lf, "load_config", lambda: cfg())
    monkeypatch.setattr("backend.pipelines.common.db.get_dsn", lambda: "postgresql://unused")
    monkeypatch.setattr("backend.pipelines.common.db.load_env", lambda: None)
    monkeypatch.setattr(lf, "_requests_get", lambda ua: pytest.fail("확인 전에 요청하면 안 됨"))
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert lf.main(["--probe", "hankyung", "--url", "https://www.hankyung.com/a/1"]) == 1
    assert "취소" in capsys.readouterr().out
    assert lf.main(["--probe", "sedaily", "--url", "https://www.sedaily.com/a/1"]) == 1   # naver 방식은 대상 아님


# ---------------------------------------------------------------- 설정

def test_shipped_config_is_consistent():
    config = load_config()
    assert set(config.sources) == {"hankyung", "mk", "yonhap", "sedaily"}
    for code, src in config.sources.items():
        if src.enabled:
            assert src.ready, f"{code}: 켜져 있는데 준비가 안 됨 (본문 selector가 비어 있음)"
    assert config.sources["sedaily"].method == "naver"            # 약관상 링크 수집 안 함
    assert config.user_agent.startswith("memos-news-collector/")


def test_config_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n  x: {method: web}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad)
    fast = tmp_path / "fast.yaml"
    fast.write_text("request_interval_seconds: 0.1\nsources: {}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(fast)
