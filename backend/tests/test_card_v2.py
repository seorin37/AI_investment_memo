"""v2 카드 (2026-11-10): 파싱·검사·흐름·합치기·비교 근거·미리보기. DB·LLM 없이 가짜로 돈다."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pipelines.updates.checks import check_card_v2, text_dates
from pipelines.updates.compare_prior import korean_won, period_type, prior_evidence
from pipelines.updates.judge import asks_why, build_prompt, parse_card_v2, wants_comparison
from pipelines.updates.models import Candidate, CardV2, Evidence, TrackingItem, UpdateDraft
from pipelines.updates.topic import check_topic, merge_same_source

ITEM = TrackingItem("M01:0:0", "000660", "topic", "SK하이닉스 배당", memo_text="작년보다 배당 늘었나?",
                    company_name="SK하이닉스")
CFG = {"card_schema": "v2", "min_similarity": 0.5, "title_max": 30, "max_sentences": 3, "sentence_max_chars": 60,
       "min_confidence": 0.7, "reason_max": 80, "verify_call": False, "on_check_fail": "drop"}


def disc(ref="disc:R1#0", text="1주당 배당금(원) 보통주 20,000 배당기준일 2026-11-30", day="2026-10-28"):
    return Candidate(ref, "disclosure", "000660", day, "현금ㆍ현물배당결정", text, None, "DART", 0.8, "event")


def news(ref="news:1", text="SK하이닉스 주가가 2.62% 올랐다.", day="2026-10-29"):
    return Candidate(ref, "news", "000660", day, "SK하이닉스 주주환원", text, "http://x", "한국경제", 0.8)


def ev(*cands):
    return [Evidence(f"E{i}", c, c.text) for i, c in enumerate(cands, 1)]


def card(**kw):
    base = dict(status="update", headline="SK하이닉스 분기배당 결정", when="2026-10-28",
                facts=[("보통주 1주당 20,000원 분기배당을 결정했어요.", "E1")], memo_link="메모의 '배당' 관심사와 연결돼요.",
                sources=["E1"], confidence=0.9)
    base.update(kw)
    return CardV2(**base)


class ParseTest(unittest.TestCase):
    def test_parse_v2(self):
        raw = json.dumps({"status": "update", "headline": "h", "when": "2026-10-28",
                          "facts": [{"text": "a", "evidence_id": "E1"}, {"text": "비교 자료 없음", "evidence_id": ""}],
                          "memo_link": "m", "sources": ["E1"], "confidence": 0.9}, ensure_ascii=False)
        c = parse_card_v2(raw)
        self.assertEqual(c.facts, [("a", "E1"), ("비교 자료 없음", "")])
        self.assertEqual((c.title, c.summary[0], c.reason, c.evidence), ("h", "a", "m", [("E1", "a")]))
        self.assertIsNone(parse_card_v2('{"status": "update", "headline": "h"}'))
        self.assertIsNone(parse_card_v2(raw.replace('"facts": [', '"facts": ["x", ')))

    def test_memo_flags_and_prompt(self):
        self.assertTrue(wants_comparison("작년보다 배당 늘었나?"))
        self.assertFalse(wants_comparison("HBM 소식 알려줘"))
        self.assertTrue(asks_why("왜 떨어졌어?"))
        for memo in ("KB랑 신한 중에 뭐가 나음?", "삼전이랑 하닉 뭐가 낫냐", "둘 중 어느 쪽이 좋아?"):
            self.assertTrue(wants_comparison(memo), memo)
        p = build_prompt(ITEM, ev(disc()), schema="v2")
        self.assertIn("- 비교를 원함: 예", p)
        self.assertIn("- 이유를 물음: 아니오", p)
        self.assertIn('"evidence_id": "E1"', p)
        self.assertIn("[카드 규칙]", p)                                   # v2 프롬프트 파일
        self.assertNotIn("[카드 규칙]", build_prompt(ITEM, ev(disc())))   # v1은 그대로
        with self.assertRaises(ValueError):
            build_prompt(ITEM, ev(disc()), schema="v3")


class CheckTest(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(check_card_v2(card(), ev(disc()), [], CFG), [])

    def test_numbers_must_come_from_the_cited_evidence(self):
        e = ev(disc(), news())
        mixed = card(facts=[("보통주 1주당 20,000원이고 주가는 2.62% 올랐어요.", "E1")])
        self.assertIn("NUMBER", check_card_v2(mixed, e, [], CFG))         # 2.62%는 E2의 숫자
        ok = card(facts=[("보통주 1주당 20,000원 배당을 결정했어요.", "E1"), ("주가는 2.62% 올랐어요.", "E2")],
                  sources=["E1", "E2"])
        self.assertEqual(check_card_v2(ok, e, [], CFG), [])

    def test_when_and_sources(self):
        e = ev(disc())
        self.assertIn("FORMAT_WHEN", check_card_v2(card(when="2026-10-27"), e, [], CFG))
        self.assertEqual(check_card_v2(card(when="2026-11-30"), e, [], CFG), [])   # 근거 본문의 날짜(배당기준일)
        self.assertIn("SOURCE", check_card_v2(card(sources=["E1", "E2"]), e, [], CFG))
        self.assertIn("SOURCE", check_card_v2(card(facts=[("배당을 결정했어요.", "E9")], sources=["E9"]), e, [], CFG))
        no_cmp = card(facts=[("보통주 1주당 20,000원 배당을 결정했어요.", "E1"), ("비교 자료 없음", "")])
        self.assertEqual(check_card_v2(no_cmp, e, [], CFG), [])

    def test_compare_only_card_and_format(self):
        cmp = Candidate("cmp:R1", "disclosure", "000660", "2026-10-28", "직전 같은 기간 비교", "작년 1주당 15,000원", None,
                        "DART", 1.0, "compare")
        only = card(facts=[("작년에는 1주당 15,000원이었어요.", "E1")])
        self.assertIn("SOURCE", check_card_v2(only, ev(cmp), [], CFG))
        self.assertIn("FORMAT_SUMMARY", check_card_v2(card(facts=[("배당 결정 [E1]", "E1")]), ev(disc()), [], CFG))
        self.assertIn("FORMAT_REASON", check_card_v2(card(memo_link="한 문장. 두 문장."), ev(disc()), [], CFG))
        self.assertIn("BANNED", check_card_v2(card(memo_link="호재예요."), ev(disc()), ["호재"], CFG))
        self.assertIn("LOW_CONF", check_card_v2(card(confidence=0.3), ev(disc()), [], CFG))

    def test_comparison_judgment_is_blocked(self):
        from pipelines.common.config import load_config
        cfg = {**CFG, "judgment_patterns": load_config("configs/updates.yaml")["topic"]["judgment_patterns"]}
        e = ev(disc(), news())
        two = dict(facts=[("보통주 1주당 20,000원 배당을 결정했어요.", "E1"), ("주가는 2.62% 올랐어요.", "E2")],
                   sources=["E1", "E2"])
        self.assertEqual(check_card_v2(card(**two), e, [], cfg), [])               # 두 사실을 나란히: 통과
        for link in ("배당만 보면 SK하이닉스가 더 나아요.", "KB가 나은 선택이에요.", "지금 갈아타는 게 좋아요.",
                     "SK하이닉스가 상대적으로 매력적이에요.", "삼성전자가 더 싸 보여요."):
            self.assertIn("JUDGMENT", check_card_v2(card(memo_link=link, **two), e, [], cfg), link)
        ok = card(memo_link="메모의 'KB랑 신한' 비교 관심사와 연결돼요.", **two)
        self.assertEqual(check_card_v2(ok, e, [], cfg), [])
        fact = card(facts=[("KB의 시가배당률이 신한보다 더 높아요.", "E1")])
        self.assertNotIn("JUDGMENT", check_card_v2(fact, ev(disc()), [], cfg))     # 수치를 견준 사실은 판단이 아니다

    def test_coverage_terms_need_evidence(self):
        cfg = {**CFG, "coverage_terms": ["처음", "줄곧", "계속", "연속"]}
        e = ev(news(text="SK하이닉스 주가가 2.62% 올랐다. 3거래일 연속 상승이다."))
        ok = card(when="2026-10-29", facts=[("주가가 3거래일 연속 2.62% 올랐어요.", "E1")])
        self.assertEqual(check_card_v2(ok, e, [], cfg), [])                       # '연속'이 근거에 있다
        bad = card(when="2026-10-29", facts=[("주가가 줄곧 올라 2.62% 상승했어요.", "E1")])
        self.assertIn("COVERAGE", check_card_v2(bad, e, [], cfg))
        self.assertIn("COVERAGE", check_card_v2(card(when="2026-10-29", facts=[("주가가 2.62% 올랐어요.", "E1")],
                                                     memo_link="처음으로 오른 주가예요."), e, [], cfg))

    def test_coverage_text_and_prompt(self):
        from pipelines.updates.topic import coverage_text
        self.assertEqual(coverage_text({"news_since": "2026-10-28"}, True), "10월 28일 이후 기사 기준")
        self.assertEqual(coverage_text({"news_since": "2026-10-28"}, False), "")   # 공시만 쓴 카드
        self.assertEqual(coverage_text(None, True), "")
        p = build_prompt(ITEM, ev(disc()), schema="v2", coverage={"news_since": "2026-10-28"})
        self.assertIn("# 자료 범위\n- 뉴스: 2026-10-28 이후 발행된 기사만 있어요", p)
        self.assertIn("자료 범위 밖의 원인·추이·배경은 짐작해서 쓰거나 단정하지 않습니다", p)
        self.assertNotIn("# 자료 범위", build_prompt(ITEM, ev(disc()), schema="v2"))

    def test_news_card_gets_coverage(self):
        cfg = {**CFG, "coverage": {"news_since": "2026-10-28"}}
        out = check_topic(ITEM, [news()], lambda p: json.dumps({
            "status": "update", "headline": "SK하이닉스 주가 상승", "when": "2026-10-29",
            "facts": [{"text": "SK하이닉스 주가가 2.62% 올랐어요.", "evidence_id": "E1"}],
            "memo_link": "메모의 '배당' 관심사와 연결된 주가 소식이에요.", "sources": ["E1"], "confidence": 0.9},
            ensure_ascii=False), [], cfg)
        self.assertEqual(out.draft.coverage, "10월 28일 이후 기사 기준")
        from pipelines.updates.results import draft_to_dict
        self.assertEqual(draft_to_dict(out.draft)["coverage"], "10월 28일 이후 기사 기준")

    def test_text_dates(self):
        self.assertEqual(text_dates("2026.10.28 및 2026년 11월 3일"), {"2026-10-28", "2026-11-03"})


class FlowTest(unittest.TestCase):
    def _call(self, payload):
        return lambda prompt: json.dumps(payload, ensure_ascii=False)

    def test_v2_draft_and_auto_no_comparison(self):
        out = check_topic(ITEM, [disc()], self._call({
            "status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
            "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E1"}],
            "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"], "confidence": 0.9}), [], CFG)
        self.assertEqual(out.kind, "update")
        d = out.draft
        self.assertEqual((d.card_schema, d.when, d.title), ("v2", "2026-10-28", "SK하이닉스 분기배당 결정"))
        # 메모가 비교를 원하는데 비교 문장이 없어 코드가 "비교 자료 없음"을 붙였다
        self.assertEqual(d.facts, [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "ref": "disc:R1#0"},
                                   {"text": "비교 자료 없음", "ref": ""}])
        self.assertEqual(d.sources, [("disc:R1#0", "보통주 1주당 20,000원 분기배당을 결정했어요.")])

    def test_v2_extra_evidence_and_no_update(self):
        cmp = Candidate("cmp:R1", "disclosure", "000660", "2026-10-28", "직전 같은 기간 비교", "작년 1주당 15,000원", None,
                        "DART", 1.0, "compare")
        seen = []

        def call(prompt):
            seen.append(prompt)
            return json.dumps({"status": "no_update", "headline": "", "when": "", "facts": [], "memo_link": "",
                               "sources": [], "confidence": 0.9})
        out = check_topic(ITEM, [disc()], call, [], CFG, extra_evidence=lambda e: [Evidence("E2", cmp, cmp.text)])
        self.assertEqual(out.kind, "no_update")
        self.assertIn("E2 [직전 같은 기간 비교]", seen[0])

    def test_v1_unchanged(self):
        out = check_topic(ITEM, [disc()], None, [], {**CFG, "card_schema": "v1"})
        self.assertEqual(out.kind, "not_called")


class ExplanationTest(unittest.TestCase):
    """설명 문단 시험 (topic.explanation, 2026-11-12). 기본은 꺼져 있어 기존 카드와 같다."""
    ON = {**CFG, "explanation": {"enabled": True, "max_sentences": 3, "max_chars": 200}}
    EXP = "SK하이닉스는 보통주 1주당 20,000원을 분기배당으로 주기로 했어요. 배당기준일은 2026-11-30이에요."

    def _payload(self, **kw):
        base = {"status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
                "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E1"}],
                "explanation": self.EXP, "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"], "confidence": 0.9}
        base.update(kw)
        return json.dumps(base, ensure_ascii=False)

    def test_off_by_default(self):
        self.assertEqual(check_card_v2(card(), ev(disc()), [], CFG), [])
        self.assertNotIn("explanation", build_prompt(ITEM, ev(disc()), schema="v2"))
        out = check_topic(ITEM, [disc()], lambda p: self._payload(), [], CFG)
        self.assertEqual(out.draft.explanation, "")                 # 꺼져 있으면 응답에 있어도 쓰지 않는다

    def test_checked_when_on(self):
        self.assertEqual(check_card_v2(card(explanation=self.EXP), ev(disc()), [], self.ON), [])
        self.assertIn("FORMAT_EXPLANATION", check_card_v2(card(), ev(disc()), [], self.ON))       # 비었다
        self.assertIn("FORMAT_EXPLANATION", check_card_v2(card(explanation=self.EXP + " [E1]"), ev(disc()), [], self.ON))
        self.assertIn("NUMBER", check_card_v2(card(explanation="1주당 30,000원으로 정했어요. 기준일은 2026-11-30이에요."),
                                              ev(disc()), [], self.ON))                           # 근거에 없는 숫자
        self.assertIn("BANNED", check_card_v2(card(explanation="배당을 정한 호재예요. 기준일은 2026-11-30이에요."),
                                              ev(disc()), ["호재"], self.ON))

    def test_prompt_parse_and_draft(self):
        self.assertIn("JSON 키: status, headline, when, facts, explanation, memo_link",
                      build_prompt(ITEM, ev(disc()), schema="v2", explain=True))
        seen = []

        def call(prompt):
            seen.append(prompt)
            return self._payload()
        out = check_topic(ITEM, [disc()], call, [], {**self.ON, "prompt_path_v2": "configs/update_judge_prompt_v2_explain.md"})
        self.assertEqual(out.kind, "update")
        self.assertEqual(out.draft.explanation, self.EXP)
        self.assertIn("explanation: 2~3문장, 200자 이내", seen[0])  # 시험용 프롬프트 파일에 설정값이 채워진다


class MergeTest(unittest.TestCase):
    def test_merge_same_memo_same_source(self):
        mk = lambda iid, refs, origin="llm": UpdateDraft(TrackingItem(iid, "000660", "topic", f"항목 {iid}"), "news", "t", "s",
                                                         "r", [(r, None) for r in refs], origin=origin)
        a, b, c, d = mk("M1:0:0", ["news:1"]), mk("M1:1:0", ["news:1", "news:2"]), mk("M2:0:0", ["news:1"]), \
            mk("M1:2:0", ["news:3"])
        kept, merged = merge_same_source([a, b, c, d])
        self.assertEqual([k.item.item_id for k in kept], ["M1:0:0", "M2:0:0", "M1:2:0"])
        self.assertEqual(merged, {"M1:1:0": "M1:0:0"})
        self.assertEqual(a.merged_items, [{"item_id": "M1:1:0", "description": "항목 M1:1:0"}])
        cmp_only = mk("M1:3:0", ["cmp:R1"])
        a2 = mk("M1:0:0", ["cmp:R1", "news:9"])
        self.assertEqual(merge_same_source([a2, cmp_only])[1], {})             # 비교용 근거만 겹치면 합치지 않는다


class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Conn:
    def __init__(self, table):
        self.table, self.sqls = table, []

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        for key, rows in self.table.items():
            if key in sql:
                return _Cur(rows)
        return _Cur([])


class CompareTest(unittest.TestCase):
    def test_korean_won(self):
        self.assertEqual(korean_won(24448929000000), "24조 4,489억 2,900만원")
        self.assertEqual(korean_won(20000), "2만원")
        self.assertEqual(korean_won(None), "-")
        from pipelines.updates.checks import numbers
        self.assertEqual(numbers(korean_won(24448929000000)), {24448929000000.0})

    def test_period_type(self):
        self.assertEqual(period_type("quarterly", date(2026, 9, 30)), "q3")
        self.assertEqual(period_type("half", date(2026, 6, 30)), "half")
        self.assertIsNone(period_type("major", date(2026, 9, 30)))

    def test_prelim_earnings(self):
        f = {"period_start": "2026-07-01", "period_end": "2026-09-30", "revenue": 104615483000000,
             "revenue_prev_y": 24448929000000, "revenue_prev_q": 79318746000000, "op_income": 1, "op_income_prev_y": None,
             "op_income_prev_q": None}
        conn = _Conn({"FROM disclosures d LEFT JOIN disclosure_events": [
            ("R1", "000660", date(2026, 10, 28), "연결재무제표기준영업(잠정)실적", "major", None, "prelim_earnings", f)]})
        out = prior_evidence(conn, ev(disc("disc:R1#0")))
        self.assertEqual(len(out), 1)
        e = out[0]
        self.assertEqual((e.eid, e.candidate.ref, e.candidate.doc), ("E2", "cmp:R1", "compare"))
        self.assertIn("매출액: 당기 104조 6,154억 8,300만원 · 전년 동기 24조 4,489억 2,900만원", e.shown_text)
        self.assertNotIn("영업이익", e.shown_text)                       # 비교값이 없으면 줄을 만들지 않는다

    def test_dividend_without_prior(self):
        f = {"dps_common": 20000, "record_date": "2026-11-30", "dividend_kind": "분기배당"}
        conn = _Conn({"FROM disclosures d LEFT JOIN disclosure_events": [
            ("R1", "000660", date(2026, 10, 28), "현금ㆍ현물배당결정", "major", None, "dividend", f)],
            "SELECT min(d.rcept_dt)": [(date(2026, 10, 21),)]})
        text = prior_evidence(conn, ev(disc("disc:R1#0")))[0].shown_text
        self.assertIn("이번 배당: 분기배당 보통주 1주당 20,000원", text)
        self.assertIn("2025-11-30 전후) 배당 공시는 DB에서 찾지 못했어요", text)

    def test_news_only_makes_nothing(self):
        conn = _Conn({})
        self.assertEqual(prior_evidence(conn, ev(news())), [])
        self.assertEqual(conn.sqls, [])


class NumberUnitTest(unittest.TestCase):
    """숫자 단위 (2026-11-17): 십억·백억·천억·백만·천만을 읽고, 표 머리 "(단위 : 백만원)"의 맨숫자에 카드가 "원"이나 다른 단위를
    붙이면 NUMBER. v1 카드(_check_body)·v2 카드·즉시 답변이 같은 규칙인지 셋 다 본다."""

    PASS = [("706,565백만원", "706,565백만원"), ("706,565백만원", "7,065억 6,500만원"),
            ("(단위 : 백만원) 706,565", "7,065억 6,500만원"), ("12십억원", "120억원"),
            ("(단위 : 백만원) 706,565", "706,565"),                                   # 맨숫자는 지금처럼 원래 값으로 인정
            ("배당금총액 14조 1034억 6648만 8000원", "14조 1034억 6648만 8000원"),       # 한국식 나눠 쓴 금액
            ("순이익 5조7천921억원", "5조7천921억원"), ("순이익 1조9075억원", "9075억원"),
            ("2026.11.03 매출 12.5% 늘었다", "2026년 11월 3일 매출이 12.5% 늘었어요"),     # 날짜·%
            ("3분기 매출 706,565백만원", "3분기 매출이 706,565백만원이에요"),             # 한 자리 숫자는 비교에서 뺀다
            ("(단위 : 백만원) 배당금총액(원): 1,500 매출 706,565", "1주당 1,500원이에요")]  # "(원)" 이름표 숫자는 원 금액
    FAIL = [("706,565백만원", "706,565원"), ("706,565백만원", "706,565천원"),
            ("(단위 : 백만원) 706,565", "706,565원"), ("1,234억원", "1,234원"),
            ("(단위 : 백만원) 706,565", "706,565억원")]

    @staticmethod
    def _v2(src, said):
        c = card(headline="SK하이닉스 실적", when="2026-10-28", facts=[(f"매출은 {said}이에요.", "E1")])
        return "NUMBER" in check_card_v2(c, ev(disc(text=src)), [], CFG)

    @staticmethod
    def _v1(src, said):
        from pipelines.updates.checks import check_card
        from pipelines.updates.models import Card
        c = Card("update", "SK하이닉스 실적", [f"매출은 {said}이에요. [E1]"], "메모의 실적 관심사와 연결돼요.",
                 [("E1", "실적 공시")], 0.9)
        return "NUMBER" in check_card(c, ev(disc(text=src)), [], {"min_fact_overlap": 0})

    @staticmethod
    def _answer(src, said):
        from pipelines.updates.checks import check_answer
        from pipelines.updates.models import Answer
        a = Answer("answer", "none", [f"매출은 {said}이에요. [E1]"], [("E1", "실적 공시")], 0.9)
        return "NUMBER" in check_answer(a, ev(disc(text=src)), [], {"min_fact_overlap": 0})

    def test_same_rule_in_v1_v2_answer(self):
        for name, fn in (("v2", self._v2), ("v1", self._v1), ("answer", self._answer)):
            for src, said in self.PASS:
                self.assertFalse(fn(src, said), f"{name} 통과해야 함: {src} ↔ {said}")
            for src, said in self.FAIL:
                self.assertTrue(fn(src, said), f"{name} 실패해야 함: {src} ↔ {said}")

    def test_units_and_kinds(self):
        from pipelines.updates.checks import evidence_number_sets, evidence_numbers, numbers
        self.assertEqual(numbers("706,565백만원"), {706565000000.0})
        self.assertEqual(numbers("5천억원 3천만원 2백억원 12십억원"), {5e11, 3e7, 2e10, 1.2e10})
        self.assertEqual(numbers("14조 1034억 6648만 8000원"), {14103466488000.0})
        self.assertEqual(numbers("3분기"), set())
        ev_sets = evidence_number_sets("(단위 : 백만원) 706,565")
        self.assertEqual(ev_sets.plain, {706565.0, 706565000000.0})
        self.assertEqual(ev_sets.unit, {706565000000.0})
        self.assertEqual(evidence_numbers("(단위 : 백만원) 706,565"), ev_sets.plain)   # 값만 쓰는 곳은 이전과 같다


# 2026-11-17 dry-run 항목 7 KB금융 분기배당 금액의 E2 원문 (outcomes.jsonl shown_text 그대로)
KB_DIVIDEND = (
    "[KB금융 2026 3분기 | III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 26. 배당금 (연결)]\n"
    "[표] 배당금에 대한 공시 / 당분기말\n(단위 : 백만원)\n열: 연차배당 | 분기배당\n"
    "소유주에 대한 배분으로 인식된 배당금 | 연차배당: 573,768 | 분기배당: 810,246\n"
    "소유주에 대한 배분으로 인식된 주당배당금(단위: 원) | 연차배당: 1,605\n\n"
    "[표] 전기말\n(단위 : 백만원)\n열: 연차배당 | 분기배당\n"
    "소유주에 대한 배분으로 인식된 배당금 | 연차배당: 298,285 | 분기배당: 1,004,006\n"
    "소유주에 대한 배분으로 인식된 주당배당금(단위: 원) | 연차배당: 804\n\n"
    "[표] 배당금에 대한 공시, 중간배당\n(단위 : 백만원)\n"
    "열: 배당의 구분 / 분기배당 / 분기배당 1 | 배당의 구분 / 분기배당 / 분기배당 2\n"
    "소유주에 대한 배분으로 인식된 배당금 | 배당의 구분 / 분기배당 / 분기배당 1: 405,088 | 배당의 구분 / 분기배당 / 분기배당 2: 405,158\n"
    "소유주에 대한 배분으로 인식된 주당배당금(단위: 원) | 배당의 구분 / 분기배당 / 분기배당 1: 1,143 | 배당의 구분 / 분기배당 / 분기배당 2: 1,155")
TWO_TABLES = ("[삼성전자 2026 3분기 | 연결재무제표 주석]\n[표] 매출\n(단위 : 백만원)\n매출액 | 당분기: 706,565\n\n"
              "[표] 임원 보수\n(단위 : 천원)\n보수총액 | 당분기: 12,345")


class RowUnitTest(unittest.TestCase):
    """표 행 이름표 단위·표 머리 여러 개 (2026-11-18, 결정 2 변경). 줄 앞쪽 이름표 "(단위: 원)"이 있으면 그 줄 값은 원,
    표 머리는 숫자마다 가장 가까운 앞 머리를 쓴다. v1·v2·즉시 답변 셋 다 본다."""

    PASS = [(KB_DIVIDEND, "1,143원"), (KB_DIVIDEND, "1,155원"), (KB_DIVIDEND, "1,605원"),
            (KB_DIVIDEND, "4,050억 8,800만원"), (KB_DIVIDEND, "405,088백만원"),        # 표 머리 백만원 줄은 그대로
            (KB_DIVIDEND, "1,143"),                                                     # 맨숫자는 그대로 인정
            (TWO_TABLES, "7,065억 6,500만원"), (TWO_TABLES, "12,345천원"), (TWO_TABLES, "1,234만 5천원"),
            ("(단위 : 백만원)\n배당성향(%) | 당기: 30.5", "30.5%"),
            ("(단위 : 백만원)\n발행주식수(단위: 주) | 당기: 1,000,000", "1,000,000주"),
            ("(단위 : 백만원)\n(주)한화 | 장부금액: 1,000", "10억원"),                       # "(주)"는 단위가 아니다
            ("(단위 : 백만원)\n기본주당이익(손실) (단위 : 원) | 당기: 2,345", "2,345원"),        # 띄어 쓴 이름표
            ("(단위: 백만원) [KB금융 2026 3분기 | III. 재무]\n순이익 | 당기: 706,565", "7,065억 6,500만원")]
    FAIL = [(KB_DIVIDEND, "405,088원"), (KB_DIVIDEND, "573,768원"),                    # 다른 줄의 백만원 값을 원으로
            (KB_DIVIDEND, "1,143백만원"),                                               # 원 줄 값을 백만원으로
            (TWO_TABLES, "12,345백만원"), (TWO_TABLES, "706,565천원"),                   # 다른 표의 머리를 쓰면 실패
            ("(단위 : 백만원)\n발행주식수(단위: 주) | 당기: 1,000,000", "1,000,000원"),       # 주 줄 값은 금액이 아니다
            ("(단위 : 백만원)\n발행주식수(단위: 주) | 당기: 1,000,000", "1조원"),
            ("(단위: 백만원) [KB금융 2026 3분기 | III. 재무]\n순이익 | 당기: 706,565", "706,565원")]

    def test_same_rule_in_v1_v2_answer(self):
        for name, fn in (("v2", NumberUnitTest._v2), ("v1", NumberUnitTest._v1), ("answer", NumberUnitTest._answer)):
            for src, said in self.PASS:
                self.assertFalse(fn(src, said), f"{name} 통과해야 함: {said} ← {src[-60:]!r}")
            for src, said in self.FAIL:
                self.assertTrue(fn(src, said), f"{name} 실패해야 함: {said} ← {src[-60:]!r}")

    def test_kb_card_from_dryrun(self):
        """dry-run에서 NUMBER로 떨어졌던 KB금융 카드 문장 그대로."""
        c = card(headline="KB금융 3분기 분기배당 금액 확인", when="2026-11-16",
                 facts=[("분기배당 1의 주당배당금은 1,143원이에요.", "E1"), ("분기배당 2의 주당배당금은 1,155원이에요.", "E1")])
        self.assertNotIn("NUMBER", check_card_v2(c, ev(disc(text=KB_DIVIDEND)), [], CFG))


class PreviewTest(unittest.TestCase):
    def test_v2_card_and_compare_page(self):
        from pipelines.updates.preview import build_preview
        from pipelines.updates.preview_compare import build, load
        from pipelines.updates.results import draft_to_dict
        from pipelines.updates.used_refs import card_refs

        d = UpdateDraft(ITEM, "disclosure", "SK하이닉스 분기배당 결정", "s", "메모의 '배당'과 연결돼요.",
                        [("disc:R1#0", "q"), ("cmp:R1", "q2")], card_schema="v2", when="2026-10-28",
                        facts=[{"text": "1주당 20,000원이에요.", "ref": "disc:R1#0"}, {"text": "비교 자료 없음", "ref": ""}])
        self.assertEqual(card_refs(d), ["disc:R1#0"])                           # 비교용 근거는 쓴 근거로 적지 않는다
        c = draft_to_dict(d)
        self.assertEqual((c["headline"], c["when"], c["memo_link"]), (d.title, "2026-10-28", d.reason))
        v1 = draft_to_dict(UpdateDraft(ITEM, "news", "t", "s", "r"))
        self.assertNotIn("facts", v1)                                            # v1 모양 그대로
        html = build_preview([c], {"disc:R1#0": {"kind": "disclosure", "title": "배당결정", "date": "2026-10-28"}}, [])
        self.assertIn("확인된 사실", html)
        self.assertIn("직전 같은 기간 비교", html)
        with tempfile.TemporaryDirectory() as tmp:
            runs = []
            for name, cards in (("run_a", [v1]), ("run_b", [c])):
                r = Path(tmp) / name
                r.mkdir()
                (r / "cards.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in cards), encoding="utf-8")
                (r / "outcomes.jsonl").write_text(json.dumps({"item_id": "M09:0:0", "description": "다른 항목",
                                                              "symbol": "005930", "kind": "no_update",
                                                              "merged_into": "M01:0:0"}), encoding="utf-8")
                (r / "summary.json").write_text("{}", encoding="utf-8")
                runs.append(load(r))
            page = build(runs[0], runs[1], ("v1", "v2"))
            self.assertIn("카드 비교", page)
            self.assertIn("M01:0:0 카드로 합쳤어요", page)


if __name__ == "__main__":
    unittest.main()
