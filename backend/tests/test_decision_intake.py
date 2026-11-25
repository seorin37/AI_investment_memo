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
