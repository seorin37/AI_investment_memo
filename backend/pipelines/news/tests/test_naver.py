from datetime import datetime, timezone

from backend.pipelines.news import naver as n

UTC = timezone.utc
PUBLISHERS = {"sedaily.com": "sedaily", "mk.co.kr": "mk"}
SAMSUNG = {"code": "005930", "name": "삼성전자", "queries": ["삼성전자"], "aliases": ["삼성전자", "삼전"]}
HYNIX = {"code": "000660", "name": "SK하이닉스", "queries": ["SK하이닉스"], "aliases": ["SK하이닉스"]}

SINCE = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)   # 2026-10-20 00:00 KST
UNTIL = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)   # 2026-10-21 00:00 KST


def item(title, link, pub, desc="", original=None):
    return {"title": title, "originallink": original if original is not None else link,
            "link": link, "description": desc, "pubDate": pub}


def test_parse_item_strips_markup_converts_time_and_maps_publisher():
    art = n.parse_item(
        item("<b>삼성전자</b>, &quot;HBM4&quot; 양산", "https://n.news.naver.com/a/1",
             "Tue, 20 Oct 2026 09:05:00 +0900", "<b>삼성전자</b>가 투자를 늘린다.",
             original="http://www.sedaily.com/NewsView/ABC/"),
        SAMSUNG["aliases"], PUBLISHERS)
    assert art.title == '삼성전자, "HBM4" 양산'
    assert art.summary == "삼성전자가 투자를 늘린다."
    assert art.source_code == "sedaily"
    assert art.section is None
    assert art.url == "http://www.sedaily.com/NewsView/ABC/"
    assert art.url_norm == "https://www.sedaily.com/NewsView/ABC"
    assert art.published_at == datetime(2026, 10, 20, 0, 5, tzinfo=UTC)


def test_parse_item_unknown_publisher_uses_domain_and_can_be_excluded():
    raw = item("삼성전자 소식", "https://n.news.naver.com/a/2", "Tue, 20 Oct 2026 09:05:00 +0900",
               original="https://www.other-news.co.kr/x/1")
    art = n.parse_item(raw, SAMSUNG["aliases"], PUBLISHERS)
    assert art.publisher == "other-news.co.kr"
    assert n.parse_item(raw, SAMSUNG["aliases"], PUBLISHERS, only_listed=True) is None


def test_parse_item_drops_results_that_do_not_mention_the_stock():
    raw = item("엉뚱한 기사", "https://a.com/1", "Tue, 20 Oct 2026 09:05:00 +0900", "관련 없음")
    assert n.parse_item(raw, SAMSUNG["aliases"], PUBLISHERS) is None


def test_parse_item_drops_incomplete_results():
    assert n.parse_item(item("삼성전자", "", "Tue, 20 Oct 2026 09:05:00 +0900", original=""),
                        SAMSUNG["aliases"], PUBLISHERS) is None
    assert n.parse_item(item("삼성전자", "https://a.com/1", "날짜아님"), SAMSUNG["aliases"], PUBLISHERS) is None


def test_publisher_for_matches_subdomains_only_on_domain_boundary():
    assert n.publisher_for("https://biz.mk.co.kr/x", PUBLISHERS) == ("mk", True)
    assert n.publisher_for("https://notmk.co.kr/x", PUBLISHERS) == ("notmk.co.kr", False)


def _paged_fetch(pages):
    calls = []

    def fetch(query, start):
        calls.append((query, start))
        index = (start - 1) // n.PAGE_SIZE
        return {"items": pages[index] if index < len(pages) else []}

    fetch.calls = calls
    return fetch


def _items(count, base_hour_kst, title="삼성전자 기사"):
    # base_hour_kst 시각부터 1분씩 과거로 내려가는 결과(최신순)
    out = []
    for i in range(count):
        minute = (base_hour_kst * 60 - i) % 60
        hour = (base_hour_kst * 60 - i) // 60
        out.append(item(f"{title} {base_hour_kst}-{i}", f"https://a.com/{base_hour_kst}-{i}",
                        f"Tue, 20 Oct 2026 {hour:02d}:{minute:02d}:00 +0900"))
    return out


def test_iter_query_items_stops_when_reaching_older_than_since():
    old = [item("삼성전자 옛 기사", "https://a.com/old", "Mon, 19 Oct 2026 12:00:00 +0900")]
    first_page = _items(n.PAGE_SIZE, 20)           # 전부 윈도우 안
    fetch = _paged_fetch([first_page, old + _items(n.PAGE_SIZE - 1, 3), _items(n.PAGE_SIZE, 2)])
    got = list(n.iter_query_items("삼성전자", SINCE, fetch))
    assert len(got) == 2 * n.PAGE_SIZE
    assert [c[1] for c in fetch.calls] == [1, 101]   # 윈도우 밖에 닿은 2페이지에서 멈춤


def test_iter_query_items_stops_on_short_page_and_respects_start_limit():
    fetch = _paged_fetch([_items(10, 20)])
    assert len(list(n.iter_query_items("q", SINCE, fetch))) == 10
    assert len(fetch.calls) == 1

    always_full = lambda q, s: {"items": _items(n.PAGE_SIZE, 20)}
    starts = []

    def counting(q, s):
        starts.append(s)
        return always_full(q, s)

    list(n.iter_query_items("q", SINCE, counting))
    assert starts[-1] <= n.MAX_START and len(starts) == 10


def test_collect_merges_stock_codes_and_filters_window():
    shared = item("삼성전자와 SK하이닉스 HBM 경쟁", "https://x.com/1", "Tue, 20 Oct 2026 10:00:00 +0900")
    too_late = item("삼성전자 오늘 기사", "https://x.com/2", "Wed, 21 Oct 2026 00:00:00 +0900")

    def fetch(query, start):
        return {"items": [shared, too_late]}

    items, stats = n.collect([SAMSUNG, HYNIX], SINCE, UNTIL, fetch, PUBLISHERS)
    assert len(items) == 1
    assert items[0].stock_codes == {"005930", "000660"}
    assert all(s["error"] is None for s in stats)
    # 윈도우 밖(자정 이후) 기사는 제외돼 보관 건수에 잡히지 않는다
    assert [s["kept"] for s in stats] == [1, 1]


def test_collect_isolates_query_failures():
    good = item("삼성전자 소식", "https://x.com/1", "Tue, 20 Oct 2026 10:00:00 +0900")

    def fetch(query, start):
        if query == "SK하이닉스":
            raise n.NaverApiError("HTTP 400: SE02")
        return {"items": [good]}

    items, stats = n.collect([SAMSUNG, HYNIX], SINCE, UNTIL, fetch, PUBLISHERS)
    assert len(items) == 1
    assert stats[0]["error"] is None and "SE02" in stats[1]["error"]


def test_title_only_naver():
    item = {"title": "아이폰 듀오 후기", "description": "네이버 블로그 리뷰", "originallink": "https://www.sedaily.com/a",
            "pubDate": "Wed, 21 Oct 2026 10:00:00 +0900"}
    assert n.parse_item(item, ["네이버"], PUBLISHERS) is not None
    assert n.parse_item(item, ["네이버"], PUBLISHERS, title_only=True) is None
