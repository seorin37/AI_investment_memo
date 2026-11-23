"""주간보고서 1단계 (코드만) — 주·주가·소식 거르기·메모 문장 (2026-11-23). DB 없이 순수 함수만."""
from __future__ import annotations

from datetime import date, datetime

from app.studio_report.build import (SEOUL, MemoLink, Item, code_story, last_week, memo_section, mentions,
                                     pick_disclosures, pick_news, price_block, watch_lines, week_label, won_short)


def test_last_week():
    assert last_week(date(2026, 11, 23)) == (date(2026, 11, 16), date(2026, 11, 20))   # 월요일 → 지난주
    assert last_week(date(2026, 11, 20)) == (date(2026, 11, 9), date(2026, 11, 13))    # 금요일 → 지난주
    assert last_week(date(2026, 11, 21)) == (date(2026, 11, 16), date(2026, 11, 20))   # 토요일 → 이번 주
    assert week_label(date(2026, 11, 16)) == ("2026년 11월 3주", "11월 3주 주간 보고서")


def _p(d, close, high=None, low=None, vol=100):
    return {"trade_date": d, "close": close, "high": high or close, "low": low or close, "volume": vol}


def test_price_block_uses_prev_week_close_and_daily_volume():
    rows = [_p(date(2026, 11, 12), 100, vol=200), _p(date(2026, 11, 13), 110, vol=200),
            _p(date(2026, 11, 16), 112, 115, 108, 300), _p(date(2026, 11, 17), 121, 125, 111, 300)]
    p = price_block(rows, date(2026, 11, 16), date(2026, 11, 20))
    assert p["prev"] == 110 and p["close"] == 121 and p["pct"] == 10.0
    assert (p["hi"], p["lo"]) == ("125", "108")
    assert p["vol"] == "+50%"                          # 하루 평균 300 vs 200
    assert p["yr"][0] < 110 and p["yr"][1] > 121
    assert price_block(rows[:2], date(2026, 11, 16), date(2026, 11, 20)) is None


def test_mentions_needs_word_boundary():
    assert mentions("네이버, 사업자몰 개설", "네이버")
    assert mentions("“네이버가 만든 AI”", "네이버")
    assert not mentions("굿네이버스에 기부", "네이버")
    assert not mentions("KB증권 채권 실증", "KB")
    assert mentions("KB금융, 싱가포르 행사", "KB금융")
    assert not mentions("삼성디스플레이 체험존", "삼성")


def _n(i, title, score=1.0, cluster=None, day=16):
    return {"id": i, "title": title, "published_at": datetime(2026, 11, day, 9, tzinfo=SEOUL), "url": None,
            "score": score, "source": "연합뉴스", "cluster_id": cluster}


def test_pick_news_filters_and_dedupes():
    rows = [_n(1, "SK하이닉스, 주주환원 확대·낮아진 밸류에이션…시간 여전히 매수자 편", 0.9),
            _n(2, "SK하이닉스, 주주환원 확대·낮아진 밸류에이션…시간 여전히 매수자...", 0.8),   # 끝이 잘린 같은 제목
            _n(3, "[오전 시황] 코스피 SK하이닉스 급등 반납", 0.95),                            # 시황 묶음
            _n(4, "반도체 장비 발주 증가", 0.99),                                                # 회사 이름 없음
            _n(5, "SK하이닉스 HBM4 확대", 0.7, cluster=9, day=17), _n(6, "SK하이닉스, HBM4 공급 늘린다", 0.6, cluster=9),
            _n(7, "SK하이닉스 신규 투자", 0.5, day=18)]
    out = pick_news(rows, ["SK하이닉스"], limit=3)
    assert [i.ref for i in out] == ["news:1", "news:5", "news:7"]       # 같은 사건(cluster 9)은 점수 높은 하나
    assert [i.day.day for i in out] == [16, 17, 18]


def test_pick_disclosures_merges_corrections_and_skips_subsidiary():
    rows = [{"rcept_no": "1", "title": "타법인주식및출자증권취득결정", "rcept_dt": date(2026, 11, 17), "source_url": None},
            {"rcept_no": "2", "title": "[기재정정]타법인주식및출자증권취득결정", "rcept_dt": date(2026, 11, 20), "source_url": None},
            {"rcept_no": "3", "title": "연결재무제표기준영업(잠정)실적(공정공시)(자회사의 주요경영사항)", "rcept_dt": date(2026, 11, 18),
             "source_url": None}]
    out = pick_disclosures(rows)
    assert [(i.title, i.ref) for i in out] == [("타법인 주식 취득 결정", "disc:2")]


def test_memo_and_watch_sentences():
    it = Item("뉴스", date(2026, 11, 17), "HBM4 확대", "서울경제", "news:10", no=10, linked=True)
    linked = MemoLink(25, "HBM4 소식", datetime(2026, 11, 10, 9, tzinfo=SEOUL), topics=[(28, "HBM4 공급")],
                      prices=[("price_below", 1_100_000)], linked={"news:10": it}, linked_topics=["HBM4 공급"])
    older = MemoLink(3, "옛 메모", datetime(2026, 11, 11, 9, tzinfo=SEOUL))
    m = memo_section([older, linked])                          # 카드가 붙은 메모가 먼저
    assert m["memo_id"] == "25" and m["linked_count"] == 1 and m["meta"] == "11.10 작성 · AI 연결 중"
    assert m["body"] == "메모의 추적 항목 'HBM4 공급'과 관련된 소식 1건([10])이 이번 주에 붙었어요."
    w = watch_lines([linked], 1_183_000, date(2026, 11, 19), True)
    assert w == [{"text": "메모의 가격 조건 110만 원과 11.19 종가의 차이 (7.5% 위)", "why": "내 메모 가격 조건"}]
    assert watch_lines([], 100, date(2026, 11, 19), False)[0]["text"] == "다음 주 새 공시·뉴스가 나오는지"
    assert won_short(152_900) == "152,900원"


def test_code_story():
    p = {"trade_dates": [date(2026, 11, 16), date(2026, 11, 17)], "closes": [216000, 212300], "close": 212300, "pct": -0.8}
    assert code_story(p, []) == "이번 주 새 공시·뉴스는 없었어요. 월요일(11.16) 종가 216,000원이 이번 주 가장 높았고, 11.17 종가 기준 212,300원이에요."
    items = [Item("공시", date(2026, 11, 16), "a", "DART", "disc:1"), Item("뉴스", date(2026, 11, 17), "b", "x", "news:1")]
    assert code_story(p, items) == "이번 주 공시 1건·뉴스 1건이 있었어요. 11.17 종가는 지난주보다 0.8% 낮은 212,300원이에요."


# ─── 2단계: 흐름 문장 LLM 검사 ─────────────────────────
from app.studio_report.story import check_story, input_text, llm_story  # noqa: E402

P = {"trade_dates": [date(2026, 11, 16), date(2026, 11, 17)], "closes": [1_200_000, 1_183_000], "prev": 1_215_000,
     "close": 1_183_000, "pct": -2.6}
ITEMS = [Item("뉴스", date(2026, 11, 17), "SK하이닉스, HBM4 확대", "서울경제", "news:10", no=10)]


def test_input_text_has_code_computed_changes():
    src = input_text("SK하이닉스", P, ITEMS)
    assert "11.16(월) 종가 1,200,000원 (전날보다 -1.2%)" in src
    assert "[10] 11.17(화) · 뉴스 · 서울경제 · SK하이닉스, HBM4 확대" in src


def test_check_story_rules():
    src = input_text("SK하이닉스", P, ITEMS)
    ok = "화요일(11.17) HBM4 확대 보도[10]가 있었어요. 11.17 종가 기준 1,183,000원으로, 지난주보다 2.6% 낮아요."
    assert check_story(ok, src, {10}) == []
    assert any("숫자" in p for p in check_story("화요일(11.17) 보도[10]가 있었어요. 종가는 1,190,000원이에요.", src, {10}))
    assert any("번호" in p for p in check_story("화요일(11.17) 보도[3]가 있었어요.", src, {10}))
    assert any("원인" in p for p in check_story("HBM4 보도[10] 덕분에 올랐어요.", src, {10}))
    assert any("금지" in p for p in check_story("HBM4 보도[10]는 호재예요.", src, {10}))


def test_llm_story_retries_then_falls_back():
    calls = []

    def bad(msgs):
        calls.append(msgs)
        return {"story": "HBM4 보도[10] 덕분에 올랐어요.", "_usage": {"input": 10, "output": 5}}
    story, meta = llm_story("SK하이닉스", P, ITEMS, bad, "코드 문장")
    assert story == "코드 문장" and meta["source"] == "code" and meta["tries"] == 2 and len(calls) == 2
    assert "검사에서 고칠 점" in calls[1][-1]["content"]                       # 두 번째는 고칠 점을 알려 준다

    good = lambda msgs: {"story": "화요일(11.17) HBM4 확대 보도[10]가 있었어요. 11.17 종가 기준 1,183,000원이에요.",
                         "issues": "서울경제는 HBM4 확대를 보도했어요[10]. 11.17 종가는 1,183,000원이에요. 지난주 마지막 종가는 1,215,000원이에요."}
    story, meta = llm_story("SK하이닉스", P, ITEMS, good, "코드 문장")
    assert meta["source"] == "llm" and story.startswith("화요일")
    story, meta = llm_story("SK하이닉스", P, [], good, "코드 문장")              # 소식 0건이면 부르지 않는다
    assert story == "코드 문장" and meta["tries"] == 0


def test_issues_and_attributed_cause():
    from app.studio_report.story import check_issues, llm_stock, sentences
    src = input_text("SK하이닉스", P, ITEMS)
    assert check_issues("서울경제는 HBM4 확대 영향으로 매출이 늘었다고 전했어요[10]. 둘째 문장이에요. 셋째 문장이에요.", src, {10}) == []
    assert any("원인" in x for x in check_issues("HBM4 확대 영향으로 올랐어요[10]. 둘째예요. 셋째예요.", src, {10}))
    assert len(sentences("주요 이슈가 있었어요[1]. 필요 자금은 1.5%였어요 그리고 공시했어요[2][3]")) == 3
    good = lambda msgs: {"story": "화요일(11.17) HBM4 확대 보도[10]가 있었어요.",
                         "issues": "서울경제는 HBM4 확대를 보도했어요[10].\n\n11.17 종가는 1,183,000원이에요. 지난주 마지막 종가는 1,215,000원이에요."}
    story, issues, meta = llm_stock("SK하이닉스", P, ITEMS, good, "코드 문장")
    assert meta["source"] == "llm" and issues.count("\n\n") == 1


def test_verify_removes_unsupported_sentences_keeps_paragraphs():
    from app.studio_report.story import verify_texts
    seen = []

    def judge(msgs, schema=None, model=None):
        seen.append((schema["name"], model))
        return {"results": [{"i": 1, "ok": True, "why": ""}, {"i": 2, "ok": False, "why": "자료에 없음"},
                            {"i": 3, "ok": True, "why": ""}, {"i": 4, "ok": True, "why": ""}]}
    out, removed, usage = verify_texts(judge, "자료", {"story": "가였어요. 나였어요.", "issues": "다였어요.\n\n라였어요."})
    assert out == {"story": "가였어요.", "issues": "다였어요.\n\n라였어요."}
    assert removed == [{"field": "story", "text": "나였어요.", "why": "자료에 없음"}]
    assert seen == [("report_verify", "gpt-6.1-terra")] and usage["failed"] is False

    def broken(msgs, schema=None, model=None):
        raise RuntimeError("down")
    out, removed, usage = verify_texts(broken, "자료", {"story": "가였어요."})
    assert out == {"story": "가였어요."} and removed == [] and usage["failed"] is True     # 검수 실패면 그대로


def test_periodic_report_not_sent_to_llm():
    from app.studio_report.story import llm_stock
    periodic = [Item("공시", date(2026, 11, 16), "분기보고서 (2026.09)", "DART", "disc:1", no=1)]
    called = []
    story, issues, meta = llm_stock("SK하이닉스", P, periodic, lambda m: called.append(m) or {}, "코드 문장")
    assert called == [] and story == "코드 문장" and issues == ""
