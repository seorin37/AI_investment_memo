"""물음표 없는 판단 질문도 메모 분석에서 버리지 않기, 쪼개진 문장의 같은 질문은 하나로 (2026-11-25)."""

import unittest
from unittest import mock

from app.board.analysis import _lexicon, analyze_memo
from pipelines.tracking.judge import PENDING, judge_memo


class ShortDecisionTest(unittest.TestCase):
    def test_goes_to_llm(self):
        for t in ("사야하나 고민중이야", "존버 vs 손절", "매수 고민중"):
            self.assertEqual([j.decision for j in judge_memo(t, "000660", _lexicon())], [PENDING], t)

    def test_chatter_still_dropped(self):
        for t in ("점심 뭐 먹지", "이상규 맥북 개쓰레기"):
            self.assertEqual(judge_memo(t, "000660", _lexicon())[0].category, "B5", t)

    def test_price_as_question_context_does_not_create_tracking(self):
        for text in ("140만원 넘으면 살까?", "140만원 넘으면 살까", "140만원 아래면 손절할까?",
                     "고점에서 30% 빠지면 살까?"):
            with self.subTest(text=text):
                [judgment] = judge_memo(text, "000660", _lexicon())
                self.assertEqual(judgment.decision, PENDING)
                self.assertEqual(judgment.items, [])

    def test_explicit_alert_is_retained_alongside_question(self):
        judgments = judge_memo("140만원 넘으면 알려줘. 130만원 밑이면 살까?", "000660", _lexicon())
        self.assertEqual([it["price_threshold"] for j in judgments for it in j.items], [1_400_000])
        self.assertEqual(judgments[-1].decision, PENDING)


class SameQuestionOnceTest(unittest.TestCase):
    def test_dedupe(self):
        q = "SK하이닉스 최근 주가 흐름과 최근 나온 공시·뉴스"

        def fake(judged, *_a, **_k):
            for j in judged:
                j.decision, j.category = "full_fallback", "A4"
                j.asks = [{"question": q, "kind": "check"}]
            return judged
        with mock.patch("pipelines.tracking.llm.judge_with_llm", fake):
            r = analyze_memo(1, 1, "하이닉스 살까 말까 고민중", "000660", "SK하이닉스", lambda p: "", [])
        self.assertEqual([x["question"] for x in r.questions], [q])


if __name__ == "__main__":
    unittest.main()
