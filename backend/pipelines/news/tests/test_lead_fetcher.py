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
        (["https://www.hankyung.com/a/1", "https://plus.hankyung.com/c"], 2)   # 100건 미만 → 다음 페이지 안 부름
    assert lf.naver_probe_urls(fetch, ["증시", "환율"], ("hankyung.com",), 1) == (["https://www.hankyung.com/a/1"], 1)


def test_naver_probe_urls_pages_round_robin_until_limit_or_call_cap():
    calls = []

    def fetch(query, start):                     # 페이지마다 100건, 그중 한경 1건
        calls.append((query, start))
        items = [{"originallink": f"https://www.mk.co.kr/{query}/{start}/{i}"} for i in range(99)]
        return {"items": items + [{"originallink": f"https://www.hankyung.com/{query}/{start}"}]}
    urls, n = lf.naver_probe_urls(fetch, ["증시", "환율"], ("hankyung.com",), 3)
    assert (len(urls), n) == (3, 3)
    assert calls == [("증시", 1), ("환율", 1), ("증시", 101)]      # 모든 검색어 1페이지 먼저, 그다음 2페이지
    calls.clear()
    urls, n = lf.naver_probe_urls(fetch, ["증시"], ("hankyung.com",), 10, max_calls=4)
    assert (len(urls), n) == (4, 4) and calls[-1] == ("증시", 301)   # 상한에서 멈춤


def test_body_text_keeps_whole_article_and_lead_unchanged():
    html = "<div id='b'>첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다.<figure>사진 설명</figure></div>"
    assert lf.body_text(html, "#b") == "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다."
    assert lf.extract_lead(html, "#b", min_chars=1) == "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."
    assert lf.raw_text_chars(html, "#b") > len(lf.body_text(html, "#b"))   # 사진 설명까지 센다
    assert lf.body_text(html, "#none") is None


YONHAP = SourceConfig("yonhap", "link", True, ("yna.co.kr",), "#articletxt", url_patterns=("^/view/AKR",))


def test_url_patterns_skip_photo_articles_in_probe_fetch_and_sampling():   # 2026-11-06 연합 사진 기사(PYH) 9/10건
    akr, pyh = "https://www.yna.co.kr/view/AKR20261106079400060?input=1195m", "https://www.yna.co.kr/view/PYH20261106073300013"
    get = http({})
    fetches = []
    _, fetched, notes = lf.probe([pyh, akr], YONHAP, cfg(), get, sleep=lambda s: None, fetch_log=fetches)
    assert fetched == 1 and pyh not in get.calls and "URL 패턴" in notes[0]
    assert fetches[0].robots == "URL 패턴 다름"
    results, _ = fetch_leads([PendingItem(1, "yonhap", "t", pyh)], cfg(yonhap=YONHAP), get, sleep=lambda s: None)
    assert results[0].status == "skipped" and "URL 패턴" in results[0].error
    fetch = lambda q, start: {"items": [{"originallink": pyh}, {"originallink": akr}]}
    assert lf.naver_probe_urls(fetch, ["증시"], ("yna.co.kr",), 10, url_patterns=("^/view/AKR",)) == ([akr], 1)


def test_www_domain_excludes_other_subdomains():                  # 2026-11-06 mbn.mk.co.kr(MBN 방송)은 구조가 다름
    assert lf._host_matches("https://www.mk.co.kr/article/1", ("www.mk.co.kr",))
    assert not lf._host_matches("http://mbn.mk.co.kr/pages/news/newsView.php", ("www.mk.co.kr",))
    assert lf._host_matches("http://mbn.mk.co.kr/x", ("mk.co.kr",))            # www 없이 적으면 서브도메인 포함 (기존 동작)
    assert lf._host_matches("https://www.hankyung.com/a", ("hankyung.com",))


def test_real_config_url_filters():
    config = load_config()
    assert config.sources["mk"].domains == ("www.mk.co.kr",)
    assert config.sources["yonhap"].url_patterns == ("^/view/AKR",)
    yonhap = config.sources["yonhap"]                                  # 끄면 naver 요약으로 돌아간다
    assert yonhap.fulltext_enabled and yonhap.fallback == "naver" and "div.writer-zone01" in yonhap.drop_selectors
    assert replace(yonhap, fulltext_enabled=False).active_method == "naver"
    mk, hk = config.sources["mk"], config.sources["hankyung"]
    assert mk.subtitle_selector == "div.mid_title" and "div.mid_title" in mk.drop_selectors
    assert hk.paywall_selectors == ("div.box-cont", "blockquote") and hk.paywall_text
    assert "div.box-cont" not in hk.drop_selectors                     # 편집자주에도 쓰여 통째로 지우지 않는다
    assert hk.skip_paywalled                                            # 2026-11-06 유료 기사는 빼고 무료만


def test_skip_paywalled_stores_nothing_and_probe_keeps_going_to_free_target(tmp_path):   # 2026-11-06 무료 기사만
    hk = replace(cfg().sources["hankyung"], selector="div.article-body", paywall_selectors=("div.box-cont", "blockquote"),
                 paywall_text="유료|프리미엄", skip_paywalled=True)
    free = HK_PAID.replace("한경 프리미엄9에 실린 기사입니다. 구독하시면 더 많은 기사를 볼 수 있습니다.", "[편집자주] 연재 소개")
    get = http({"https://www.hankyung.com/a/1": Resp(200, HK_PAID), "https://www.hankyung.com/a/2": Resp(200, free),
                "https://www.hankyung.com/a/3": Resp(200, free)})
    results, _ = fetch_leads([PendingItem(1, "hankyung", "t", "https://www.hankyung.com/a/1")], cfg(hankyung=hk), get,
                             sleep=lambda s: None)
    assert results[0].status == "skipped" and "유료" in results[0].error and results[0].lead_text is None
    fetches = []
    _, fetched, notes = lf.probe([f"https://www.hankyung.com/a/{i}" for i in (1, 2, 3)], hk, cfg(), get,
                                 sleep=lambda s: None, save_dir=tmp_path, fetch_log=fetches, max_pages=1)
    assert fetched == 1 and "유료" in notes[0]                                  # 유료 1건 건너뛰고 무료 1건에서 멈춤
    assert "https://www.hankyung.com/a/3" not in get.calls
    assert [p.name for p in tmp_path.iterdir()] == ["hankyung_1.html"] and fetches[0].paywalled
    report = tmp_path / "r.csv"
    lf.write_probe_report(report, hk, cfg(), fetches, ["div.article-body"])
    rows = list(csv.DictReader(report.open(encoding="utf-8-sig")))
    assert [(r["is_paywalled"], r["html_file"] != "") for r in rows] == [("Y", False), ("N", True)]


MK_HTML = """<html><body><div class="news_cnt_detail_wrap"><div class="mid_title">AI 규제에 증시 급락<br>
증권가, 시장 우려 과도하다고 분석</div><p>미국 중간선거 이후 데이터센터 규제 강화 우려로 미국 및 국내 증시가 급락했다.</p></div></body></html>"""
HK_PAID = """<html><body><div class="article-body"><div class="box-cont">한경 프리미엄9에 실린 기사입니다. 구독하시면 더 많은 기사를 볼 수 있습니다.</div>
김 교수는 코스피가 내년 상반기까지 박스권에 머물 것이라고 내다봤다. 그는 반도체 업황을 근거로 들었다.</div></body></html>"""


def test_subtitle_split_from_body_and_paywall_flag_in_report(tmp_path):
    mk = SourceConfig("mk", "link", True, ("www.mk.co.kr",), "div.news_cnt_detail_wrap",
                      drop_selectors=("div.mid_title",), subtitle_selector="div.mid_title")
    hk = SourceConfig("hankyung", "link", True, ("hankyung.com",), "div.article-body",
                      paywall_selectors=("div.box-cont", "blockquote"), paywall_text="유료|프리미엄")
    assert lf.extract_subtitle(MK_HTML, mk.subtitle_selector) == "AI 규제에 증시 급락 / 증권가, 시장 우려 과도하다고 분석"
    assert lf.body_text(MK_HTML, mk.selector, mk.drop_selectors).startswith("미국 중간선거")   # 본문에서는 빠짐
    paid = (hk.paywall_selectors, hk.paywall_text)
    assert lf.is_paywalled(HK_PAID, *paid) and not lf.is_paywalled(MK_HTML, *paid)
    assert lf.body_text(HK_PAID, hk.selector, (), *paid).startswith("김 교수는")       # 안내 문구만 빠지고 나머지는 둔다
    editor = HK_PAID.replace("한경 프리미엄9에 실린 기사입니다. 구독하시면 더 많은 기사를 볼 수 있습니다.", "[편집자주] 이수의 ETF줌인은…")
    assert not lf.is_paywalled(editor, *paid)                                          # 같은 칸의 편집자주는 유료가 아님
    assert lf.body_text(editor, hk.selector, (), *paid).startswith("[편집자주]")          # 편집자주는 이번엔 그대로 둔다
    report = tmp_path / "r.csv"
    lf.write_probe_report(report, mk, cfg(), [lf.ProbeFetch("https://www.mk.co.kr/article/1", "허용", 200, html=MK_HTML)],
                          [mk.selector])
    lf.write_probe_report(report, hk, cfg(), [lf.ProbeFetch("https://www.hankyung.com/article/1i", "허용", 200,
                                                            html=HK_PAID)], [hk.selector])
    rows = list(csv.DictReader(report.open(encoding="utf-8-sig")))
    assert (rows[0]["subtitle"], rows[0]["is_paywalled"]) == ("AI 규제에 증시 급락 / 증권가, 시장 우려 과도하다고 분석", "")
    assert (rows[1]["subtitle"], rows[1]["is_paywalled"]) == ("", "Y")


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
    assert src.probe_selectors == ()                                              # 2026-11-06 미검증 후보 3개 0/10 → 삭제
    assert src.drop_selectors == ("div.article-video",) and src.drop_text_patterns
    with_probe = replace(src, probe_selectors=("div.x",))                         # 매체 후보가 있으면 공통 후보보다 먼저 본다
    assert lf.probe_candidates(with_probe)[0] == "div.x"


def test_byline_removed_only_when_it_ends_with_equals():          # 2026-11-06 기자 없는 머리말에서 종목명이 잘렸다
    cut = lambda text: lf.body_text(f"<div id='b'>{text}</div>", "#b")
    assert cut("(서울=연합뉴스) 코스피 상장사 한화엔진[082740]은 3분기 영업이익이 늘었다.") == \
        "코스피 상장사 한화엔진[082740]은 3분기 영업이익이 늘었다."
    assert cut("(포천=연합뉴스) 노승혁 기자 = 경기 포천시는 슬로건을 정했다.") == "경기 포천시는 슬로건을 정했다."
    assert cut("(워싱턴=연합뉴스) 김철수 특파원 = 미국 증시가 내렸다.") == "미국 증시가 내렸다."
    assert cut("(서울=연합뉴스) 홍길동 = 정부가 발표했다.") == "정부가 발표했다."
    assert cut("[한국경제TV 홍길동 기자] 코스피가 내렸다.") == "코스피가 내렸다."


def test_drop_text_patterns_remove_whole_paragraph():               # 서울경제 "▶기사 바로가기: <링크 제목>"
    html = ("<div id='b'><p>정부가 대책을 냈다. 증시가 흔들렸다.</p>"
            "<p class='align-c'>▶기사 바로가기: <span><b><a href='#'>민주당 압승에…유가 안정세</a></b></span></p>"
            "<p>▶ 관련 표는 아래와 같다.</p></div>")
    text = lf.body_text(html, "#b", drop_text_patterns=[r"^▶\s*기사\s*바로가기"])
    assert "바로가기" not in text and "민주당 압승" not in text                     # 링크 제목까지 문단째 지운다
    assert text.startswith("정부가 대책을") and "▶ 관련 표는" in text


def test_paywall_reason_names_matched_box_and_text():
    reason = lf.paywall_reason(HK_PAID, ["div.box-cont", "blockquote"], "유료|프리미엄")
    assert reason.startswith("div.box-cont: 한경 프리미엄9에 실린 기사입니다")
    assert len(reason) <= len("div.box-cont: ") + 60
    quote = "<html><body><blockquote>전체 심층 기사 내용은 한국경제신문의 유료 프리미엄 서비스에서</blockquote></body></html>"
    assert lf.paywall_reason(quote, ["div.box-cont", "blockquote"], "유료|프리미엄").startswith("blockquote: 전체 심층")
    hk = replace(cfg().sources["hankyung"], paywall_selectors=("div.box-cont",), paywall_text="유료|프리미엄",
                 skip_paywalled=True)
    results, _ = fetch_leads([PendingItem(1, "hankyung", "t", "https://www.hankyung.com/a/1")], cfg(hankyung=hk),
                             http({"https://www.hankyung.com/a/1": Resp(200, HK_PAID)}), sleep=lambda s: None)
    assert results[0].error.startswith("유료 기사 (div.box-cont: 한경 프리미엄9")        # 리드 테이블 last_error에 남는다


ROUNDUP_HTML = """<html><head><meta property="og:title" content="[전국 주요 신문 톱뉴스](6일 석간) | 연합뉴스">
<meta property="article:section" content="뉴스편집"></head><body><div id="articletxt">▲ 내일신문(서울) = AI투자 둔화 우려에
코스피 장중 5000선 붕괴 ▲ 문화일보(서울) = AI 패닉셀 녹아내린 K증시</div></body></html>"""


def test_roundup_articles_skipped_in_fetch_and_probe(tmp_path):    # 2026-11-06 연합 신문 1면 모음 2/10건
    yh = replace(YONHAP, url_patterns=(), skip_section_patterns=("^뉴스편집$",), skip_title_patterns=(r"^\[전국 주요 신문",))
    a, b = "https://www.yna.co.kr/view/AKR1", "https://www.yna.co.kr/view/AKR2"
    get = http({a: Resp(200, ROUNDUP_HTML)})
    # RSS 제목으로 알 수 있으면 요청하지 않는다
    results, _ = fetch_leads([PendingItem(1, "yonhap", "[전국 주요 신문 사설](6일 석간)", b)], cfg(yonhap=yh), get,
                             sleep=lambda s: None)
    assert results[0].status == "skipped" and results[0].error.startswith("모음 기사 (제목") and b not in get.calls
    # 제목으로 모르면 받은 페이지의 섹션 meta로 거른다
    results, _ = fetch_leads([PendingItem(2, "yonhap", "석간 주요 뉴스", a)], cfg(yonhap=yh), get, sleep=lambda s: None)
    assert results[0].status == "skipped" and results[0].error == "모음 기사 (섹션 '뉴스편집')"
    fetches = []
    _, fetched, notes = lf.probe([a, b], yh, cfg(), get, sleep=lambda s: None, save_dir=tmp_path, fetch_log=fetches)
    assert fetched == 1 and "모음 기사" in notes[0] and not fetches[0].paywalled and fetches[0].file == ""
    assert yh.skips_after_fetch


def test_real_config_mk_selector_and_yonhap_roundup_rules():
    config = load_config()
    mk, yh = config.sources["mk"], config.sources["yonhap"]
    assert mk.selector == "[itemprop='articleBody']" and "div.article-summary-box" in mk.drop_selectors
    assert yh.skip_section_patterns == ("^뉴스편집$",) and yh.skip_title_patterns == (r"^\[전국 주요 신문",)
    assert config.sources["sedaily"].selector is None                               # 서울경제는 아직 비워 둔다


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
    # 2026-11-06 팀 재결정: 약관 제11조를 인지한 채 비상업적 교육 범위에서 원문 수집 (README·yaml 주석)
    sedaily = config.sources["sedaily"]
    assert (sedaily.method, sedaily.fallback, sedaily.fulltext_enabled) == ("link", "naver", True)
    if not sedaily.selector:                                       # selector 확정 전에는 원문 대신 naver 요약
        assert sedaily.active_method == "naver"
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
