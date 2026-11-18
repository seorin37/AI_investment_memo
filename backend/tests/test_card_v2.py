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

    def test_check_log_keeps_failed_card_and_evidence_text(self):
        """검사 기록 (2026-11-17): 떨어진 카드 JSON·코드, 형식 재요청 전 첫 카드, 카드가 쓴 근거의 원문이 outcomes에 남는다."""
        from pipelines.updates.experiment import _outcome
        bad = {"status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
               "facts": [{"text": "보통주 1주당 30,000원 분기배당을 결정했어요.", "evidence_id": "E1"}],
               "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"], "confidence": 0.9}
        older = news(day="2026-10-20")                                     # 근거는 최신순이라 공시가 E1
        out = check_topic(ITEM, [disc(), older], self._call(bad), [], CFG)
        self.assertEqual([e.candidate.kind for e in out.evidence], ["disclosure", "news"])
        self.assertEqual((out.kind, out.fail_codes), ("no_update", ["NUMBER"]))
        self.assertEqual(len(out.checks), 1)
        self.assertEqual(out.checks[0]["stage"], "card")
        self.assertEqual(out.checks[0]["codes"], ["NUMBER"])
        self.assertEqual(parse_card_v2(json.dumps(out.checks[0]["card"], ensure_ascii=False)).facts,
                         [("보통주 1주당 30,000원 분기배당을 결정했어요.", "E1")])   # 응답과 같은 모양이라 다시 읽힌다
        row = _outcome(ITEM, out)
        self.assertEqual(row["checks"], out.checks)
        by_eid = {e["eid"]: e for e in row["evidence"]}
        self.assertEqual(by_eid["E1"]["shown_text"], disc().text)        # 카드가 쓴 근거만 원문을 남긴다
        self.assertNotIn("shown_text", by_eid["E2"])
        json.dumps(row, ensure_ascii=False)                              # 그대로 jsonl에 쓸 수 있다

        long = {**bad, "headline": "가" * 40, "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E1"}]}
        answers = iter([long, {**long, "headline": "SK하이닉스 분기배당 결정"}])
        out = check_topic(ITEM, [disc()], lambda p: json.dumps(next(answers), ensure_ascii=False), [],
                          {**CFG, "format_retry": 1})
        self.assertEqual(out.kind, "update")
        self.assertEqual([(c["stage"], c["codes"]) for c in out.checks], [("card", ["FORMAT_TITLE"]), ("format_retry", [])])
        self.assertEqual(out.checks[0]["card"]["headline"], "가" * 40)   # 재요청 전 첫 카드도 남는다

        out = check_topic(ITEM, [disc()], lambda p: "JSON 아님", [], CFG)
        self.assertEqual(out.checks, [{"stage": "card", "card": None, "codes": ["FORMAT_PARSE"], "raw": "JSON 아님"}])

    def test_format_retry_memo_link(self):
        """memo_link가 두 문장이면(FORMAT_REASON) 한 번 고쳐 달라고 한다 (2026-11-18, 오늘 실행 항목 7 카드 모양)."""
        good = {"status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
                "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E1"}],
                "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"], "confidence": 0.9}
        two = {**good, "memo_link": "분기배당 발표 금액을 확인하는 공시예요. 작년 같은 시기 배당금은 제공 자료에 없어요."}
        prompts, replies = [], iter([two, good])
        out = check_topic(ITEM, [disc()], lambda p: prompts.append(p) or json.dumps(next(replies), ensure_ascii=False), [],
                          {**CFG, "format_retry": 1})
        self.assertEqual(out.kind, "update")
        self.assertEqual([(c["stage"], c["codes"]) for c in out.checks], [("card", ["FORMAT_REASON"]), ("format_retry", [])])
        self.assertIn("memo_link가 비었거나, 80자(공백 포함)를 넘었거나, 한 문장이 아니에요", prompts[1])

    def test_repair_reasons_cover_format_codes(self):
        """재요청 대상 코드마다 안내 문구가 있다 (v1 reason 길이 FORMAT_REASON도 KeyError 없이)."""
        from pipelines.updates.topic import _FORMAT_CODES, _REPAIR_REASON, _REPAIR_REASON_V2
        self.assertTrue(_FORMAT_CODES - {"FORMAT_EXPLANATION"} <= set(_REPAIR_REASON))   # v1에는 설명 문단이 없다
        self.assertTrue(_FORMAT_CODES <= set(_REPAIR_REASON_V2))

    def test_number_compare_reads_outcomes_checks(self):
        """number_check_compare가 새 형식(outcomes.jsonl 검사 기록)을 읽어 같은 검사를 다시 돌린다."""
        from pipelines.updates import checks
        from pipelines.updates.experiment import _outcome
        from pipelines.updates.number_check_compare import _runs, compare
        unit = disc(text="(단위 : 백만원) 매출 706,565")
        good = {"status": "update", "headline": "SK하이닉스 실적", "when": "2026-10-28",
                "facts": [{"text": "매출은 7,065억 6,500만원이에요.", "evidence_id": "E1"}],
                "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"], "confidence": 0.9}
        wrong = {**good, "facts": [{"text": "매출은 706,565원이에요.", "evidence_id": "E1"}]}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run_x"
            run.mkdir()
            with (run / "outcomes.jsonl").open("w", encoding="utf-8") as f:
                for payload in (good, wrong):
                    out = check_topic(ITEM, [unit], self._call(payload), [], CFG)
                    f.write(json.dumps(_outcome(ITEM, out), ensure_ascii=False) + "\n")
            self.assertEqual(_runs([tmp]), [run])
            res = compare([run], checks)                                  # 전·후 모두 지금 코드: 바뀐 카드 없음
        s = res["stats"]
        self.assertEqual((s["unique_cards"], s["from_outcomes"], s["same_pass"], s["same_fail"], s["no_evidence"]),
                         (2, 2, 1, 1, 0))


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


class CountUnitTest(unittest.TestCase):
    """배수가 붙은 개수 단위 (2026-11-18 N30). 표 머리·이름표 "(단위: 천명)"·"(백만주)"의 맨숫자는 개수로 환산하고,
    환산값은 명·주·건·개를 붙인 카드 숫자하고만 맞춘다 ("30,853천명"으로 "30,853,000원"은 안 된다). v1·v2·즉시 답변 셋 다."""

    HEAD = "(단위: 천명) 30,853"
    ROW = "(단위 : 백만원)\n임직원수(단위: 천명) | 당기: 30,853"
    PASS = [(HEAD, "30,853천 명"), (HEAD, "3,085만 3천 명"), (HEAD, "30,853,000명"), (HEAD, "30,853"),
            ("[표] 고객\n(단위 : 천명)\n고객수 | 당기: 30,853", "30,853천 명"),
            (ROW, "3,085만 3천 명"), ("(단위 : 원)\n가입자(천명) | 당기: 30,853", "30,853천명"),   # 행 이름표
            ("(단위 : 백만주)\n유통주식수 | 당기: 12.5", "1,250만 주"), ("(단위: 천건) 4,321", "432만 1천 건"),
            ("(단위 : 주)\n자기주식 | 취득: 1,000,000", "100만주를"),
            ("임직원 30,853천명", "30,853천 명"), ("임직원 30,853명", "30,853명"),               # 표 머리 없는 글
            ("임직원 3만명", "30,000명"), ("가입자 30,853", "30,853명"),
            # 금액 표 안의 개수 열: 2026-11-12 A_all 항목 8 KB금융 자기주식 소각 카드 (표 머리 백만원, 소각수량은 주)
            ("[표] 자기주식 소각현황\n(단위 : 백만원)\n소각일: 2026.05.15 | 주식종류: 보통주 | 소각수량: 18,162,721 | "
             "소각금액: 2,002,230", "18,162,721주")]
    FAIL = [(HEAD, "30,853명"), (HEAD, "30,853,000원"), (HEAD, "30,853천원"),
            (ROW, "30,853명"), (ROW, "30,853,000원"), (ROW, "30,853백만원"),
            ("(단위 : 백만주)\n유통주식수 | 당기: 12.5", "12,500,000원"), ("(단위 : 백만주)\n유통주식수 | 당기: 12.5", "12.5주"),
            ("(단위 : 백만원)\n매출 | 당기: 30,853", "30,853,000,000명"),                      # 금액 환산값을 개수로
            ("임직원 30,853천명", "30,853,000원")]                                           # 표 머리 없는 글도

    def test_same_rule_in_v1_v2_answer(self):
        for name, fn in (("v2", NumberUnitTest._v2), ("v1", NumberUnitTest._v1), ("answer", NumberUnitTest._answer)):
            for src, said in self.PASS:
                self.assertFalse(fn(src, said), f"{name} 통과해야 함: {said} ← {src!r}")
            for src, said in self.FAIL:
                self.assertTrue(fn(src, said), f"{name} 실패해야 함: {said} ← {src!r}")

    def test_count_words(self):
        from pipelines.updates.checks import COUNT, _card_scan, table_unit
        self.assertEqual(_card_scan("자기주식 1,000주를 취득"), [(1000.0, COUNT)])
        self.assertEqual(_card_scan("3,085만 3천 명이에요"), [(30853000.0, COUNT)])
        for text in ("1주당 1,143원", "3개월", "주식 1,000 주식", "1,000 건설"):        # 주당·개월·주식·건설은 개수가 아니다
            self.assertNotIn(COUNT, {k for _, k in _card_scan(text)}, text)
        self.assertEqual(table_unit("백만주"), (COUNT, 1e6))
        self.assertEqual(table_unit("천원")[1], 1e3)
        self.assertIsNone(table_unit("톤"))


# 녹십자 2025 1분기 (20250515002021 청크 27) 외화 자산·부채 표: 외화와 원화 단위가 한 머리에 섞여 있다
GREENCROSS_FX = ("[녹십자 2025 1분기 | II. 사업의 내용 > 5. 위험관리 및 파생거래]\n"
                 "[표] 당분기말과 전기말 현재 당사의 환율변동 위험에 노출된 원화로 환산한 화폐성 외화 자산 및 부채는 다음과 같습니다. / ① 당분기말\n"
                 "(외화단위: 천USD, 천EUR, 천JPY, 천GBP, 천AUD, 천SGD, 천VND, 천SEK, 원화단위: 백만원)\n"
                 "열: 구분 | USD | EUR | JPY | GBP | AUD | SGD | VND | SEK | 환산금액\n"
                 "구분: 외화 자산 | USD: 84,878 | EUR: 5,857 | JPY: - | GBP: - | AUD: 39 | SGD: - | VND: 121,215 | SEK: - | 환산금액: 133,816")


class UnknownUnitTest(unittest.TestCase):
    """모르는 단위 머리 (2026-11-18): "(단위 : USD)"·"(단위 : 천)"처럼 쌍점 뒤 단위를 모르면 앞 표 단위 범위를 끊고,
    그 표 숫자는 맨숫자로만 인정한다 (DB 표 청크 중 아는 머리 뒤에 모르는 머리가 오는 청크 11,461개). 십억원은 금액 단위."""

    USD_AFTER = ("[표] 매출\n(단위 : 백만원)\n국내 매출 | 당기: 706,565\n\n"
                 "[표] 해외 법인\n(단위 : USD)\n해외 매출 | 당기: 5,000")
    PASS = [(USD_AFTER, "7,065억 6,500만원"),                    # 앞 표는 그대로 백만원
            (USD_AFTER, "5,000"),                                 # 모르는 단위 표 숫자는 맨숫자로
            ("(단위 : 십억원)\n매출 | 당기: 12", "120억원"), ("(단위: 십억원) 1,234", "1조 2,340억원"),
            ("(단위 : 천)\n매출 | 당기: 5,000", "5,000"),
            ("(단위 : 백만원)\n매출 | 당기: 1,000\n\n(단위 : USD)\n매출 | 당기: 5,000\n\n(단위 : 백만원)\n이익 | 당기: 300",
             "3억원")]                                             # 다시 아는 머리가 오면 그 단위
    FAIL = [(USD_AFTER, "50억원"), (USD_AFTER, "5,000백만원"), (USD_AFTER, "5,000원"), (USD_AFTER, "5,000명"),
            ("(단위 : 천)\n매출 | 당기: 5,000", "500만원"), ("(단위 : 천)\n매출 | 당기: 5,000", "5,000원"),
            ("(단위 : 백만원)\n매출 | 당기: 1,000\n(단위 : 백만)\n이익 | 당기: 300", "3억원"),
            ("(단위 : 백만원)\n매출 | 당기: 1,000\n(단위 : 천단위)\n이익 | 당기: 300", "3억원"),
            ("(단위 : 백만원)\n해외매출(단위: USD) | 당기: 5,000", "50억원"),   # 행 이름표의 모르는 단위
            # 행 안 칸의 모르는 단위 (실제 공시 20240814003229 청크 802 모양)
            ("(단위 : 백만원)\n항목: 수입신용장 관련 약정 | 한도단위: USD | 한도액: 350,000", "350,000백만원"),
            ("(단위 : 백만원)\n항목: 수입신용장 관련 약정 | 한도단위: USD | 한도액: 350,000", "3,500억원"),
            # 녹십자 20250515002021 청크 27: 외화·원화 단위가 섞인 머리 → USD 칸을 백만원으로 보지 않는다
            (GREENCROSS_FX, "84,878백만원"), (GREENCROSS_FX, "848억 7,800만원"),
            # 녹십자 청크 380: 이름표의 통화 표시 "[USD, 천]"
            ("[표] 외화금융자산의 통화별 내역\n(단위 : 백만원)\n외화금융자산, 기초통화금액, USD [USD, 천] | 통화 / USD: 84,878",
             "84,878백만원"),
            ("(단위 : 백만원)\n이익 | 당기: 300\n주당배당금(원) | 당기: - | 전기: -\n매출 | 당기: 1,000", "1,000원"),  # 빈 데이터 행은 머리 아님
            ("(단위 : 십억원)\n매출 | 당기: 12", "12억원")]
    PASS_REAL = [
            # LG유플러스 20260814001092 청크 134: 열 머리 행의 이름표 단위가 그 표 머리
            ("[표] [케이블TV 가입자 현황] / (2026년 3월 31일 기준)\n구분(단위 : 천명) | SO수 | 가입자 | 점유율\n"
             "㈜LG헬로비전 | 23개 | 3,340 | 28.7%", "3,340천 명"),
            ("[표] [케이블TV 가입자 현황]\n구분(단위 : 천명) | SO수 | 가입자 | 점유율\n㈜LG헬로비전 | 23개 | 3,340 | 28.7%", "334만 명"),
            # 제일기획 20260310002959 청크 21: 줄 끝 칸 "(단위 : 천주)"
            ("[표]\n(대상기간 : | 2026년 02월 13일 | ~ | 2026년 08월 12일 | ) | (단위 : 천주)\n\n[표]\n"
             "열: 구분 | 구분 | 취득형태 | 주식종류 | 거래방법 | 수량 | 결정사유\n"
             "구분: 보유수량 | 취득형태: 직접 | 주식종류: 보통주 | 거래방법: - | 수량: 13,762", "1,376만 2천 주"),
            (GREENCROSS_FX, "84,878"),
            ("(단위 : 백만원)\n이익 | 당기: 300\n주당배당금(원) | 당기: - | 전기: -\n매출 | 당기: 1,000", "10억원")]
    FAIL_REAL = [
            ("[표] [케이블TV 가입자 현황]\n구분(단위 : 천명) | SO수 | 가입자 | 점유율\n㈜LG헬로비전 | 23개 | 3,340 | 28.7%", "3,340명"),
            ("[표]\n(대상기간 : | 2026년 02월 13일 | ~ | 2026년 08월 12일 | ) | (단위 : 천주)\n\n[표]\n"
             "구분: 보유수량 | 취득형태: 직접 | 주식종류: 보통주 | 거래방법: - | 수량: 13,762", "13,762주")]

    def test_real_disclosure_shapes(self):
        """2026-11-18 운영 DB 표 모양 (unit_card_probe로 찾은 실제 청크)."""
        for name, fn in (("v2", NumberUnitTest._v2), ("v1", NumberUnitTest._v1), ("answer", NumberUnitTest._answer)):
            for src, said in self.PASS_REAL:
                self.assertFalse(fn(src, said), f"{name} 통과해야 함: {said} ← {src[-80:]!r}")
            for src, said in self.FAIL_REAL:
                self.assertTrue(fn(src, said), f"{name} 실패해야 함: {said} ← {src[-80:]!r}")

    def test_same_rule_in_v1_v2_answer(self):
        for name, fn in (("v2", NumberUnitTest._v2), ("v1", NumberUnitTest._v1), ("answer", NumberUnitTest._answer)):
            for src, said in self.PASS:
                self.assertFalse(fn(src, said), f"{name} 통과해야 함: {said} ← {src!r}")
            for src, said in self.FAIL:
                self.assertTrue(fn(src, said), f"{name} 실패해야 함: {said} ← {src!r}")


class ForecastAttributionTest(unittest.TestCase):
    """전망 근거 (2026-11-18 N08 결정): 증권사·회사·기관·언론의 전망은 "누가 무엇을 전망했다"로 전하면 통과,
    주체 없는 미래 단정·판단은 실패 (PREDICTION·BANNED). 운영 설정(configs/updates.yaml)의 금지어·패턴으로 본다."""

    EV = ("KB증권은 4분기 영업이익을 1조 2,000억원으로 전망했다. 김동원 KB증권 애널리스트는 4분기 영업이익을 104조원으로 예측했다. "
          "모건스탠리는 데이터센터 투자가 3조달러에 이를 것으로 내다봤다. 회사는 4분기 출하량이 늘 것이라고 밝혔다.")
    PASS = ["KB증권은 4분기 영업이익을 1조 2,000억원으로 전망했어요.",
            "김동원 KB증권 애널리스트는 4분기 영업이익을 104조원으로 예측했어요.",
            "모건스탠리는 데이터센터 투자가 3조달러에 이를 것으로 내다봤어요.",
            "회사는 4분기 출하량이 늘 것이라고 밝혔어요.",
            "SK하이닉스는 4분기 출하량이 늘 것으로 예상한다고 밝혔어요."]
    FAIL = ["4분기 영업이익은 1조 2,000억원으로 전망돼요.",                 # 주체 없는 전망
            "4분기 영업이익이 늘어날 전망이에요.", "주가가 오를 거예요.", "4분기 영업이익이 늘 것으로 보여요.",
            "영업이익은 1조 2,000억원으로 전망했어요.",                     # 주어가 지표 (전망한 주체가 아님)
            "KB증권은 1조 2,000억원으로 전망했고 주가도 오를 거예요.",       # 전달 문장 안의 주체 없는 단정
            "KB증권은 영업이익 개선을 전망했어요. 호재예요.",              # 판단
            # 막연한 주어 (2026-11-18): 시장·증권가·전문가들·업계 관계자·일각·이름 없는 직함
            "시장은 4분기 영업이익을 1조 2,000억원으로 전망했어요.",
            "증권가는 4분기 영업이익을 1조 2,000억원으로 내다봤어요.",
            "전문가들은 4분기 영업이익을 1조 2,000억원으로 예상했어요.",
            "업계 관계자는 4분기 영업이익을 1조 2,000억원으로 전망했어요.",
            "일각에서는 4분기 영업이익을 1조 2,000억원으로 전망했어요.",
            "투자자들은 4분기 영업이익을 1조 2,000억원으로 예상했어요.",
            "애널리스트는 4분기 영업이익을 104조원으로 예측했어요.",
            "한 연구원은 4분기 영업이익을 104조원으로 예측했어요."]

    @classmethod
    def setUpClass(cls):
        from pipelines.common.config import load_config
        real = load_config("configs/updates.yaml")
        cls.cfg, cls.banned = {**CFG, **real["topic"], "verify_call": False}, list(real["banned"])

    def _codes(self, fact="KB증권은 4분기 영업이익을 1조 2,000억원으로 전망했어요.", headline="KB증권 4분기 실적 보고서"):
        c = card(headline=headline, when="2026-10-28", facts=[(fact, "E1")], memo_link="메모의 '4분기 실적' 관심사와 연결돼요.")
        return set(check_card_v2(c, ev(news(text=self.EV, day="2026-10-28")), self.banned, self.cfg))

    def test_attributed_pass_unattributed_fail(self):
        for s in self.PASS:
            self.assertFalse(self._codes(fact=s) & {"PREDICTION", "BANNED"}, s)
        for s in self.FAIL:
            self.assertTrue(self._codes(fact=s) & {"PREDICTION", "BANNED"}, s)

    def test_headline(self):
        self.assertFalse(self._codes(headline="KB증권, 4분기 영업이익 1조 2,000억원 전망") & {"PREDICTION", "BANNED"})
        self.assertFalse(self._codes(headline="김동원 애널리스트, 4분기 영업이익 104조원 전망") & {"PREDICTION", "BANNED"})
        for h in ("SK하이닉스 4분기 영업이익 1조 2,000억원 전망", "SK하이닉스, 4분기 영업이익 1조 2,000억원 전망",
                  "4분기 영업이익 개선 전망", "증권가, 4분기 영업이익 1조 2,000억원 전망", "시장, 4분기 영업이익 개선 전망",
                  "애널리스트, 4분기 영업이익 104조원 전망"):                                   # 맨 앞이 출처가 아니면 주체 없는 전망
            self.assertIn("PREDICTION", self._codes(headline=h), h)

    def test_attributed_forecast_unit(self):
        from pipelines.updates.checks import attributed_forecast
        self.assertTrue(attributed_forecast("HBM 매출이 8% 늘 것으로 KB증권은 전망했어요."))   # 앞 주어가 지표여도 출처 주어가 있으면
        self.assertFalse(attributed_forecast("HBM 매출이 8% 늘 것으로 전망했어요."))
        self.assertFalse(attributed_forecast("KB증권, 4분기 영업이익 1조 2,000억원 전망"))    # 제목 형식은 headline일 때만
        self.assertTrue(attributed_forecast("KB증권, 4분기 영업이익 1조 2,000억원 전망", headline=True))
        # 출처 주어의 전달 동사 (지난 C_all·C2_all 항목 3 카드 문장 그대로)
        self.assertTrue(attributed_forecast("김 애널리스트는 이 과거 주가 통계를 반등 전망의 근거로 제시했어요."))
        self.assertTrue(attributed_forecast("메모에서 궁금해한 친구의 '상승 전망' 근거와 관련해, 이번 자료는 KB증권이 반등 전망의 "
                                            "근거로 제시한 과거 주가 통계예요."))
        self.assertFalse(attributed_forecast("이 통계는 반등 전망의 근거로 제시됐어요."))            # 출처 주어 없음
        self.assertFalse(attributed_forecast("KB증권은 보고서를 제시했고 주가는 오를 전망이에요."))  # 주체 없는 단정이 섞임
        self.assertFalse(attributed_forecast("두 수치는 향후 1년간 예상 이익을 기준으로 제시된 것이에요."))
        self.assertFalse(attributed_forecast("매출이 줄어들었어요."))                               # "들었"은 띄어 쓴 때만

    # 2026-11-18 안 A 재실행에서 예측 표현으로 걸린 카드 6장 (forecast_rule_rerun, 문장 그대로).
    # 전달 동사(들었·전했)·소유격 주체·제목 맨 앞 이름은 통과, 자료를 주체 없이 "~ 전망이에요"로 가리킨 문장은 그대로 실패
    # (검사를 풀지 않고 지시문 [전망 근거]에 "주체를 넣는다"를 넣었다)
    RERUN_CARDS = [
        ("A 항목 3", "KB증권, 4분기 영업이익 104조원 전망",
         ["김동원 KB증권 애널리스트는 SK하이닉스의 4분기 영업이익을 104조원으로 전망했어요.",
          "김동원 KB증권 애널리스트는 판가 상승과 출하량 증가를 실적 전망의 근거로 들었어요."],
         "SK하이닉스 주가 상승 전망의 근거를 확인하려는 관심사와 연결되는 실적 전망이에요.", "",
         ["SK하이닉스 주가 상승 전망의 근거를 확인하려는 관심사와 연결되는 실적 전망이에요."]),
        ("A_all 항목 3", "KB증권, SK하이닉스 4분기 영업이익 전망",
         ["김동원 KB증권 애널리스트는 4분기 영업이익을 104조원으로 예상했어요.",
          "매일경제는 판가 상승과 출하량 증가를 실적 전망의 배경으로 전했어요."],
         "메모의 '상승 전망의 근거 확인'과 연결되는 증권사의 실적 전망과 그 배경이에요.", "",
         ["메모의 '상승 전망의 근거 확인'과 연결되는 증권사의 실적 전망과 그 배경이에요."]),   # "증권사"는 막연한 주어
        ("B 항목 3", "KB증권, SK하이닉스 실적 전망 제시",
         ["김동원 KB증권 애널리스트는 HBM4 판매 비중이 HBM3E를 넘어설 것으로 예측했어요."],
         "메모의 '상승 전망의 근거 확인'과 연결되는 증권사 실적 전망과 그 전제인 판매가격·출하량 예상에 관한 내용이에요.", "",
         ["메모의 '상승 전망의 근거 확인'과 연결되는 증권사 실적 전망과 그 전제인 판매가격·출하량 예상에 관한 내용이에요."]),
        ("C2_all 항목 10", "머스크, 중국 메모리 대규모 생산 전망",
         ["머스크는 중국이 2028년 엄청난 양의 메모리 반도체를 생산할 것이라고 전망했어요.",
          "머스크는 중국이 관련 제조 기술을 확보하면 대규모 증산에 나설 수 있다고 전망했어요."],
         "메모에서 '중국 메모리 업체 증설'을 주목하셨는데, 이번 자료는 중국의 메모리 공급 확대 가능성에 대한 머스크의 전망이에요.",
         "머스크는 중국 업체들이 기술을 확보하면 생산 규모를 급격히 확대할 수 있다고 주장했어요. "
         "이는 중국 업체의 실제 증설 발표가 아니라 기술 확보를 조건으로 한 생산 확대 전망이에요.",
         ["이는 중국 업체의 실제 증설 발표가 아니라 기술 확보를 조건으로 한 생산 확대 전망이에요."]),
        ("C_all 항목 3", "KB증권, 하이닉스 4분기 이익 전망 제시",
         ["김동원 KB증권 애널리스트는 4분기 영업이익을 104조원으로 예상했어요.",
          "KB증권은 4분기 D램·낸드 출하량이 3분기보다 각각 24%, 5% 늘 것으로 봤어요."],
         "메모에서는 주가 상승 전망의 근거를 궁금해하셨는데, 이번 자료는 KB증권이 제시한 실적 전망과 그 배경을 담고 있어요.",
         "김동원 애널리스트는 평균판매가격 상승과 출하량 증가를 실적 전망의 배경으로 제시했어요. "
         "이 수치들은 발표된 4분기 실적이 아니라 해당 애널리스트의 예상치예요.",
         ["이 수치들은 발표된 4분기 실적이 아니라 해당 애널리스트의 예상치예요."]),          # "해당 애널리스트"는 이름 없음
        ("오늘 실행 항목 3", "KB증권, SK하이닉스 4분기 이익 전망",
         ["SK하이닉스의 3분기 영업이익은 83조원이었어요.", "김동원 KB증권 애널리스트는 4분기 영업이익을 104조원으로 전망했어요.",
          "김동원 KB증권 애널리스트는 4분기 D램 출하량이 3분기보다 24% 늘 것으로 예상했어요."],
         "SK하이닉스 주가 상승 전망의 근거를 확인하려는 관심사와 연결되는 실적·출하량 전망이에요.", "",
         ["SK하이닉스 주가 상승 전망의 근거를 확인하려는 관심사와 연결되는 실적·출하량 전망이에요."]),
    ]

    def test_rerun_cards(self):
        import re
        from pipelines.updates.checks import _banned_hit, forecast_subjects, prediction_text
        for name, head, facts, link, exp, still in self.RERUN_CARDS:
            names = forecast_subjects(facts)
            texts = [head, *facts, link] + [s for s in re.split(r"(?<=[.!?])\s+", exp) if s.strip()]
            flagged = [t for t in texts if prediction_text([t], self.cfg, names) or _banned_hit([t], self.banned, self.cfg, names)]
            self.assertEqual(flagged, still, name)

    def test_possessive_and_headline_name(self):
        from pipelines.updates.checks import attributed_forecast
        self.assertTrue(attributed_forecast("이번 자료는 KB증권의 실적 전망을 다룬 기사예요."))     # 지시문 예시
        self.assertTrue(attributed_forecast("이 수치는 김동원 애널리스트의 예상치예요."))
        self.assertFalse(attributed_forecast("이번 자료는 증권가의 실적 전망이에요."))               # 막연한 주어
        self.assertFalse(attributed_forecast("이번 자료는 SK하이닉스의 실적 전망이에요."))           # 대상일 수 있다 (names에 없으면)
        self.assertFalse(attributed_forecast("KB증권의 전망이에요. 주가는 오를 거예요."))           # 나머지에 주체 없는 단정
        self.assertTrue(attributed_forecast("머스크, 중국 메모리 대규모 생산 전망", headline=True, names={"머스크"}))
        self.assertFalse(attributed_forecast("머스크, 중국 메모리 대규모 생산 전망", headline=True))
        # 전달 동사 문장의 주체도 사실 문장의 전망 주체(names)면 인정 (2026-11-18 항목 10 재실행 memo_link)
        link = "메모에서 우려한 중국 메모리 업체의 증설과 관련해, 머스크가 중국의 기술 확보 이후 공급 확대 가능성을 언급한 기사예요."
        self.assertTrue(attributed_forecast(link, names={"머스크"}))
        self.assertFalse(attributed_forecast(link))
        self.assertFalse(attributed_forecast("업계가 중국의 공급 확대 가능성을 언급한 기사예요.", names={"업계"}))   # 막연한 주어는 names여도 X
        # 최종 재실행(2026-11-18) 문장: 소유격과 전망 사이 낱말 4개, 관형절 주체 "X가 제시한 … 전망이에요"
        self.assertTrue(attributed_forecast("메모에서 우려한 중국 업체 증설과 관련해, 머스크의 중국 메모리 공급 확대 전망을 다룬 기사예요.",
                                            names={"머스크"}))
        self.assertTrue(attributed_forecast("이는 발표된 4분기 실적이 아니라 김동원 애널리스트가 제시한 전망이에요."))
        self.assertTrue(attributed_forecast("이번 기사가 전한 내용은 중국 업체의 증설 확정 발표가 아니라 머스크가 제시한 공급 확대 전망이에요.",
                                            names={"머스크"}))
        self.assertFalse(attributed_forecast("이는 시장이 제시한 전망이에요."))                      # 막연한 주어
        self.assertFalse(attributed_forecast("이는 애널리스트가 제시한 전망이에요."))                # 이름 없는 직함


class MemoLinkNumberTest(unittest.TestCase):
    """memo_link 숫자는 쓴 근거나 메모 문장 중 하나에 있으면 인정 (2026-11-18). headline·facts는 근거만.
    C2_gold run_20261113_124759 항목 M15:1:0 카드: memo_link가 메모의 "13% 아래"를 인용했는데 13%가 근거 E1에 없어 NUMBER였다."""

    MEMO = "CET1 비율 13% 아래로 내려가면 주주환원 축소 가능성"
    E1 = ("[KB금융 2025 사업보고서 | III. 재무에 관한 사항 > 6. 배당에 관한 사항]\n[표] - 2차 주주환원 결정 : 연중 축적되는 이익을 통해 "
          "하반기 CET1비율 13.5%를 초과하는 자본에 상응하는 금액을 추가 주주환원 재원으로 활용(자사주 매입/소각)")
    LINK = "메모의 '13% 아래' 하락이나 주주환원 축소를 확인하는 내용은 아니며, CET1과 추가 주주환원 재원을 연결하는 기준에 관한 공시예요."
    HEAD = "하반기 CET1 13.5% 초과분, 추가 환원 재원"
    FACT = "회사는 하반기 CET1비율 13.5% 초과 자본을 추가 환원 재원으로 활용한다고 밝혔어요."

    def _card(self, **kw):
        return card(**{"headline": self.HEAD, "when": "2026-03-10", "facts": [(self.FACT, "E1")], "memo_link": self.LINK, **kw})

    def _number(self, c, memo=MEMO):
        return "NUMBER" in check_card_v2(c, ev(disc(text=self.E1, day="2026-03-10")), [], CFG, memo)

    def test_memo_number_in_memo_link(self):
        self.assertFalse(self._number(self._card()))                                     # 실제 카드: 통과
        self.assertTrue(self._number(self._card(), memo=""))                              # 메모 없이는 이전처럼 실패
        self.assertTrue(self._number(self._card(memo_link="메모의 '14% 아래'와는 다른 기준이에요.")))   # 어디에도 없는 숫자
        self.assertTrue(self._number(self._card(headline="CET1 13% 기준 공시")))           # 제목은 근거만
        self.assertTrue(self._number(self._card(facts=[("CET1 13% 아래면 환원을 줄여요.", "E1")])))   # 사실 문장도 근거만

    def test_topic_passes_memo_text(self):
        from dataclasses import replace
        payload = {"status": "update", "headline": self.HEAD, "when": "2026-03-10",
                   "facts": [{"text": self.FACT, "evidence_id": "E1"}],
                   "memo_link": self.LINK, "sources": ["E1"], "confidence": 0.9}
        call = lambda p: json.dumps(payload, ensure_ascii=False)                        # noqa: E731
        src = [disc(text=self.E1, day="2026-03-10")]
        out = check_topic(replace(ITEM, memo_text=self.MEMO), src, call, [], CFG)
        self.assertNotIn("NUMBER", out.checks[0]["codes"])
        out = check_topic(ITEM, src, call, [], CFG)                                       # 메모에 13이 없는 항목
        self.assertIn("NUMBER", out.checks[0]["codes"])


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
