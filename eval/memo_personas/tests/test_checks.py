from eval.memo_personas import checks


def test_parse_korean_numbers():
    got = [(n["value"], n["kind"]) for n in checks.parse_numbers("삼전 7만1500원 · 매출 79조 1,400억원 · 3.2% · 2.8배")]
    assert got == [(71500, "won"), (79_140_000_000_000, "won"), (3.2, "pct"), (2.8, "ratio")]


def test_number_and_date_matching():
    ev = [{"numbers": [71500, 3.4, 88000], "dates": ["2026-10-14", "2026-10-23"], "text": "종가 71,500원"}]
    ok = "삼전 7만원대인데 10월 14일 거래량 터진 날 3.4% 올랐던 거 다시 보기"
    assert checks.number_problems(ok, ev, "2026-10-23", (55000, 88000), False) == []
    bad = checks.number_problems("삼전 11월 3일에 12만 간다는데 5.9% 오를 듯", ev, "2026-10-23", (55000, 88000), False)
    assert any("11월 3일" in p for p in bad) and any("12만" in p for p in bad) and any("5.9" in p for p in bad)


def test_price_levels_only_for_price_types():
    ev = [{"numbers": [71500], "dates": [], "text": ""}]
    assert checks.number_problems("삼전 6만4천원 밑으로 오면 알림", ev, "2026-10-23", (55000, 88000), True) == []
    assert checks.number_problems("삼전 6만4천원 밑으로 오면 알림", ev, "2026-10-23", (55000, 88000), False)


def test_generic_periods_are_not_facts():
    assert checks.number_problems("국고채 10년 금리랑 52주 고점, 20일 평균 거래량 보기. 3분기 실적, 26년 계획", [],
                                  "2026-10-23", None, False) == []


def test_mentions_longest_first():
    assert checks.mentions("삼성바이오 말고 삼전") == ["삼성바이오로직스", "삼성전자"]
    assert set(checks.mentions("하닉이랑 kb, 네이버")) == {"SK하이닉스", "KB금융", "NAVER"}
    assert checks.mentions("kbps 속도 빠르네") == []


def test_style_problems():
    assert checks.style_problems("하닉 hbm 기사 다시 보기") == []
    probs = checks.style_problems("직장인으로서 종합적으로 분석해 주세요")
    assert len(probs) == 3
    assert checks.style_problems("제 투자 목적은 노후 대비")
    assert checks.style_problems("NAVER 웹툰 실적에 대해 알려주세요")


def _design_slot(slot, company="삼성전자", st="A1", keys=()):
    return {"slot": slot, "target_company": company, "sentence_type": st, "evidence_keys": list(keys),
            "as_of_date": "2026-10-23"}


def _memo(slot, text, company="삼성전자", ids=()):
    return {"slot": slot, "target_company": company, "memo_text_raw": text, "companies_mentioned": checks.mentions(text),
            "evidence_ids": list(ids)}


def test_check_person_rules():
    design = {"slots": [_design_slot(1), _design_slot(2, st="B10"), _design_slot(3, st="B7")]}
    good = [_memo(1, "삼전 hbm 기사 계속 체크"), _memo(2, "엔비디아나 살까"), _memo(3, "ㅋㅋㅋ")]
    probs, _ = checks.check_person(design, good, set(), {}, {}, 0.9)
    assert probs == []
    bad = [_memo(1, "hbm 기사 계속 체크", ids=["news_articles:999"]), _memo(2, "삼전 대신 엔비디아"), _memo(3, "ㅋㅋㅋ")]
    probs, _ = checks.check_person(design, bad, set(), {}, {}, 0.9)
    assert any("언급 없음" in p for p in probs)
    assert any("B10" in p for p in probs)
    assert any("근거 자료에 없는 ID" in p for p in probs)


def test_similar_pairs_flag_only():
    memos = [{"slot": 1, "memo_text_raw": "삼전 hbm 기사 계속 체크"}, {"slot": 2, "memo_text_raw": "삼전 hbm 기사 계속 체크함"}]
    assert checks.similar_pairs(memos, 0.9) and checks.similar_pairs(memos, 0.99) == []


def test_rounded_and_relative_percent():
    ev = [{"numbers": [18.8], "dates": [], "text": ""}]
    assert checks.number_problems("삼전 고점 대비 20% 가까이 빠짐", ev, "2026-10-23", None, False) == []
    assert checks.number_problems("삼전 10% 빠지면 알림", [], "2026-10-23", (55000, 88000), True) == []
    assert checks.number_problems("삼전 10% 빠지면 알림", [], "2026-10-23", (55000, 88000), False)


def test_natural_ro_seo_is_not_self_intro():
    assert checks.style_problems("kb 배당주로서 매력 있는지 보기") == []
    assert checks.style_problems("은퇴자로서 배당이 중요") != []


def test_hundreds_unit():
    assert [n["value"] for n in checks.parse_numbers("8만8천9백원")] == [88900]
