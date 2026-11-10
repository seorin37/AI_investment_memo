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
