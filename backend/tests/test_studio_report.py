"""주간보고서 1단계 (코드만) — 주·주가·소식 거르기·메모 문장 (2026-11-23). DB 없이 순수 함수만."""
from __future__ import annotations

from datetime import date, datetime

from app.studio_report.build import (SEOUL, MemoLink, Item, code_story, last_week, memo_section, mentions,
                                     pick_disclosures, pick_news, price_block, watch_lines, week_label, won_short,
                                     next_periodic)


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
    assert w[-1] == {"sid": "t0", "kind": "tracking", "tracked": True,
                     "text": "메모의 가격 조건 110만 원과 11.19 종가의 차이 (7.5% 위)", "why": "내 메모 가격 조건"}
    assert [x["kind"] for x in w] == ["schedule", "tracking"]                # 가격 메모가 있으면 가격 제안은 안 함
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


def test_news_window_includes_weekend():
    from app.studio_report.build import news_window
    mon = date(2026, 11, 16)
    start, end, partial = news_window(mon, datetime(2026, 11, 23, 9, tzinfo=SEOUL))          # 다음 주 월요일 → 일요일 밤까지
    assert (start, end, partial) == (datetime(2026, 11, 16, tzinfo=SEOUL), datetime(2026, 11, 23, tzinfo=SEOUL), False)
    start, end, partial = news_window(mon, datetime(2026, 11, 21, 15, tzinfo=SEOUL))         # 토요일 오후 → 지금까지
    assert end == datetime(2026, 11, 21, 15, tzinfo=SEOUL) and partial is True


def test_sentence_end_with_period_before_refs():
    from app.studio_report.story import sentences
    assert len(sentences("찬성하기로 했어요.[3][4] 통과됐어요.[8] 임기는 3년이에요[8]. 끝이에요.")) == 4


def test_pick_news_per_day_cap_lets_weekend_in():
    rows = [_n(i, f"SK하이닉스 평일 기사 {i}번 제목입니다", 0.9 - i * 0.01, day=17) for i in range(1, 6)] + [_n(9, "SK하이닉스 주말 기사 제목입니다", 0.1, day=22)]
    out = pick_news(rows, ["SK하이닉스"], limit=10, per_day=2)
    assert [i.day.day for i in out] == [17, 17, 22]


# ─── 앞으로 지켜볼 것 = 메모 제안 (2026-11-24) ───────────

def test_watch_never_empty_and_gives_memo_text():
    """메모·소식이 하나도 없어도 제안이 최소 1개 (다음 정기 공시), 가격 메모가 없으면 이번 주 저가 제안."""
    w = watch_lines([], 1_085_000, date(2026, 11, 24), False, code="000660", items=[], lo=1_044_000, name="SK하이닉스")
    assert [x["sid"] for x in w] == ["periodic", "low"]
    assert w[0]["text"] == "SK하이닉스 2027년 3월 사업보고서에 실적이 어떻게 나오는지" and w[0]["memo_body"].endswith("알려줘")
    assert w[1]["memo_body"] == "1,044,000원 아래로 내려가면 알려줘. 이번 주 저가였어"
    assert all(x.get("memo_title") and x.get("memo_body") for x in w)


def test_watch_orders_llm_follow_then_ir_then_schedule_and_caps_three():
    ir = Item("공시", date(2026, 11, 13), "기업설명회(IR)개최(안내공시)", "DART", "disc:1", no=4)
    sug = [{"text": "손정의 인수 검토 후속 공시가 나오는지", "memo_title": "인수 검토 후속", "memo_body": "회사 공식 입장이나 공시 나오면 알려줘", "refs": [3]}]
    w = watch_lines([], 100, date(2026, 11, 24), True, code="000660", items=[ir], lo=90, suggest=sug)
    assert [x["sid"] for x in w] == ["f0", "ir", "periodic"]                 # 제안은 최대 3개
    assert w[0]["why"] == "이번 주 소식 [3]" and "[4]" in w[1]["memo_body"]


def test_watch_skips_schedule_when_report_already_tracked():
    m = MemoLink(9, "실적", datetime(2026, 11, 10, 9, tzinfo=SEOUL), topics=[(1, "3분기 실적 발표")])
    w = watch_lines([m], 100, date(2026, 11, 24), True, code="005930", items=[], lo=95)
    assert [x["sid"] for x in w] == ["low"]


def test_next_periodic_rolls_to_next_year():
    assert next_periodic(date(2026, 11, 24)) == (date(2027, 3, 31), "사업보고서")
    assert next_periodic(date(2026, 4, 1)) == (date(2026, 5, 15), "1분기 보고서")


def test_suggestion_checks_drop_bad_ones():
    from app.studio_report.story import clean_suggestions
    ok = {"text": "자사주 취득 결과 보고가 나오는지", "memo_title": "자사주 결과", "memo_body": "취득 기간 끝나고 결과 보고 나오면 알려줘", "refs": [2]}
    bad_ref = {**ok, "refs": [99]}
    advice = {**ok, "text": "주가가 반등할지 지켜보기"}
    no_ask = {**ok, "memo_body": "자사주 취득 결과 보고서가 궁금함"}
    assert clean_suggestions([bad_ref, advice, no_ask, ok], {2, 3}) == [ok]


def test_llm_stock_passes_suggestions_through_meta():
    from app.studio_report.story import llm_stock
    good = lambda msgs: {"story": "화요일(11.17) HBM4 확대 보도[10]가 있었어요.",
                         "issues": "서울경제는 HBM4 확대를 보도했어요[10].\n\n11.17 종가는 1,183,000원이에요. 지난주 마지막 종가는 1,215,000원이에요.",
                         "suggest": [{"text": "HBM4 공급 계약 공시가 나오는지", "memo_title": "HBM4 계약", "memo_body": "공급 계약 공시 나오면 알려줘", "refs": [10]},
                                     {"text": "주가가 반등할지 지켜보기", "memo_title": "반등", "memo_body": "반등하면 알려줘", "refs": [10]}]}
    _story, _issues, meta = llm_stock("SK하이닉스", P, ITEMS, good, "코드 문장", verify=False)
    assert [x["memo_title"] for x in meta["suggest"]] == ["HBM4 계약"]          # 예측 표현 제안은 빠짐


def test_periodic_suggestion_uses_stock_quarter_numbers():
    from app.studio_report.build import periodic_suggestion
    q = {"label": "2026년 3분기", "operating_income": "11조 3,830억원", "net_income": "9조원", "op_yoy": 62.1}
    s = periodic_suggestion(date(2026, 11, 24), "SK하이닉스", q)
    assert s["text"] == "3월 사업보고서에 3분기 이후 영업이익이 어떻게 나오는지 (3분기 11조 3,830억원, 전년 대비 +62.1%)"
    assert s["memo_title"] == "SK하이닉스 사업보고서 실적" and s["memo_body"].startswith("SK하이닉스 사업보고서(3월 31일까지) 나오면")
    fin = periodic_suggestion(date(2026, 11, 24), "KB금융", {"label": "2026년 3분기", "operating_income": "", "net_income": "1조 6,000억원", "op_yoy": None})
    assert "순이익" in fin["text"] and "전년 대비" not in fin["text"]
