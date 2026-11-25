"""판단 질문 답의 주가 사실 (price_brief.py, topic.with_price_facts, 2026-11-25)."""

import unittest
from datetime import date, timedelta

from pipelines.updates.models import TopicOutcome, TrackingItem, UpdateDraft
from pipelines.updates.price_brief import alert_suggestion, brief_from_closes, wants_price_brief, won
from pipelines.updates.response import item_response
from pipelines.updates.results import draft_to_dict
from pipelines.updates.topic import NO_RECENT_NEWS, with_price_facts

ITEM = TrackingItem("121", "000660", "topic", "SK하이닉스 최근 주가 흐름", memo_text="하이닉스 싸진 거 같은데 살까 말까",
                    company_name="SK하이닉스", category="ask")


def closes(n, last=1_000_000, step=1_000):
    """최신순 n일 종가: 오늘이 last, 하루 전마다 step만큼 낮다 (계속 오름)."""
    d0 = date(2026, 11, 24)
    return [(d0 - timedelta(days=i), last - step * i) for i in range(n)]


class BriefTest(unittest.TestCase):
    def test_full_year(self):
        out = brief_from_closes("SK하이닉스", closes(260))
        self.assertEqual(len(out), 3)
        self.assertIn("11월 24일 종가는 1,000,000원", out[0])
        self.assertIn("전 거래일보다 0.1% 올랐어요", out[0])   # 999,000 → 1,000,000
        self.assertIn("한 달 전", out[1])
        self.assertIn("52주 종가 범위", out[2])
        self.assertIn("아래에서 100% 지점", out[2])           # 계속 올라 오늘이 최고

    def test_short_history(self):
        self.assertEqual(len(brief_from_closes("A", closes(10))), 1)        # 한 달·52주는 자료 모자라 생략
        self.assertIn("최근 130거래일", brief_from_closes("A", closes(130))[2])
        self.assertEqual(brief_from_closes("A", []), [])

    def test_no_advice_words(self):
        text = " ".join(brief_from_closes("A", closes(260, step=2_000)))
        for w in ("싸", "비싸", "사세요", "매수", "바닥", "오를", "전망"):
            self.assertNotIn(w, text)


class WantsBriefTest(unittest.TestCase):
    def test_by_item_description(self):
        for d in ("SK하이닉스 최근 주가 흐름과 최근 나온 공시·뉴스", "삼성전자 지금 주가가 최근 1개월·52주 범위에서 어디쯤인지",
                  "SK하이닉스 최근 주가를 움직인 소식과 앞으로 예정된 일정"):
            self.assertTrue(wants_price_brief(d), d)
        for d in ("SK하이닉스 배당 지급 일정", "HBM4 공급 계약 소식", ""):      # 같은 메모에 '손절'이 있어도 이 질문엔 안 붙는다
            self.assertFalse(wants_price_brief(d), d)


class WithPriceFactsTest(unittest.TestCase):
    FACTS = ["가 사실 1.", "가 사실 2."]

    def test_price_only_answer_when_no_news(self):
        out = with_price_facts(ITEM, TopicOutcome("no_candidates"), self.FACTS)
        self.assertEqual(out.kind, "update")
        self.assertEqual(out.draft.origin, "code")
        self.assertEqual([f["text"] for f in out.draft.facts], self.FACTS)
        self.assertEqual(out.draft.explanation, NO_RECENT_NEWS)
        r = item_response(ITEM, out.kind, [], draft_to_dict(out.draft), has_data=False)
        self.assertEqual(r.type, "update_card")                    # 소식 자료가 없어도 주가 답은 보인다

    def test_prepends_to_llm_answer(self):
        d = UpdateDraft(item=ITEM, type="news", title="t", summary="기사 사실.", reason="", card_schema="v2",
                        facts=[{"text": "SK하이닉스 종가는 111만원이에요.", "ref": "news:1"}, {"text": "기사 사실.", "ref": "news:1"}],
                        source_list=[{"kind": "news", "ref": "news:1"}])
        out = with_price_facts(ITEM, TopicOutcome("update", draft=d), self.FACTS)
        self.assertEqual([f["text"] for f in out.draft.facts], [*self.FACTS, "기사 사실."])   # 기사 속 옛 종가는 뺀다
        self.assertEqual(out.draft.title, "SK하이닉스 최근 주가와 소식")
        self.assertTrue(out.draft.summary.startswith("가 사실 1."))
        self.assertEqual(out.draft.source_list[0]["ref"], "price")

    def test_system_failure_left_alone(self):
        out = with_price_facts(ITEM, TopicOutcome("no_update", fail_codes=["CALL_FAILED"]), self.FACTS)
        self.assertEqual(out.kind, "no_update")                    # 호출 실패는 다음 실행에서 다시 본다
        self.assertEqual(with_price_facts(ITEM, TopicOutcome("not_called"), self.FACTS).kind, "not_called")


class AlertSuggestionTest(unittest.TestCase):
    def item(self, kw, price):
        return TrackingItem("1", "000660", "topic", "SK하이닉스 최근 주가 흐름과 최근 나온 공시·뉴스", keywords=kw,
                            price_threshold=price, category="ask")

    def test_above_below(self):
        up = alert_suggestion(self.item(("alert:price_above",), 1_400_000))
        self.assertEqual((up["label"], up["memo_text"]), ("140만원 넘으면 알려드릴까요?", "140만원 넘으면 알려줘"))
        down = alert_suggestion(self.item(("alert:price_below",), 52_300))
        self.assertEqual(down["memo_text"], "52,300원 밑으로 가면 알려줘")

    def test_none_without_condition(self):
        self.assertIsNone(alert_suggestion(self.item((), None)))
        self.assertIsNone(alert_suggestion(self.item(("HBM",), 1_400_000)))

    def test_suggested_memo_becomes_price_alert(self):
        from app.board.analysis import _lexicon
        from pipelines.tracking.judge import judge_memo
        for kind, price in (("price_above", 1_400_000), ("price_below", 1_350_000)):
            text = alert_suggestion(self.item((f"alert:{kind}",), price))["memo_text"]
            [j] = judge_memo(text, "000660", _lexicon())
            self.assertEqual([(i["type"], i["price_threshold"]) for i in j.items], [(kind, price)], text)

    def test_won(self):
        self.assertEqual([won(1_400_000), won(1_350_000), won(52_300)], ["140만원", "135만원", "52,300원"])


if __name__ == "__main__":
    unittest.main()
