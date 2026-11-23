"""판단 질문 답 끝 고정 문장·질문 답의 관련 기사 제외 (2026-11-23, docs/memo-decision-question-design.md)."""

import json
import unittest
from dataclasses import replace

from pipelines.updates.decision_note import _load, add_decision_note, is_decision_question
from pipelines.updates.models import Candidate, TrackingItem, UpdateDraft
from pipelines.updates.topic import check_topic

NOTE = "사고파는 결정은 정해 드리지 않아요. 위 자료로 판단해 보세요."
ITEM = TrackingItem("M01:0:0", "000660", "topic", "SK하이닉스 최근 주가 흐름과 최근 나온 공시·뉴스",
                    memo_text="하닉 지금 탑승 가능?", company_name="SK하이닉스", category="ask")
CFG = {"card_schema": "v2", "min_similarity": 0.5, "title_max": 30, "max_sentences": 3, "sentence_max_chars": 60,
       "min_confidence": 0.7, "reason_max": 80, "verify_call": False, "on_check_fail": "drop",
       "related_news_min_similarity": 0.6}


def disc():
    return Candidate("disc:R1#0", "disclosure", "000660", "2026-10-28", "현금ㆍ현물배당결정",
                     "1주당 배당금(원) 보통주 20,000 배당기준일 2026-11-30", None, "DART", 0.8, "event")


def news(ref="news:9", title="SK하이닉스 350만 간다"):
    return Candidate(ref, "news", "000660", "2026-10-29", title, "증권사가 목표가를 올렸다.", "http://x", "한국경제", 0.8)


def reply():
    return lambda prompt: json.dumps({
        "status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
        "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E2"}],
        "memo_link": "물으신 최근 공시예요.", "sources": ["E2"], "confidence": 0.9}, ensure_ascii=False)


class MarkerTest(unittest.TestCase):
    def test_lexicon_has_markers_and_note(self):
        markers, note = _load()
        self.assertGreater(len(markers), 30)
        self.assertEqual(note, NOTE)

    def test_decision_questions(self):
        for text in ["이거 가격 괜찮은거야??", "SK하이닉스 나만 없는데 지금이라도 사야되나?", "하이닉스 이거 오르나",
                     "삼전 존버할까 그냥 던질까", "네이버 물렸는데 물타기 ㄱ?", "하닉 여기서 더 빠짐?",
                     "kb 지금 고점이야 저점이야", "현대차 반등각 나오나", "삼전 10만전자 갈 수 있을까"]:
            self.assertTrue(is_decision_question(text), text)

    def test_not_decision_questions(self):
        for text in ["HBM이 정확히 뭐야?", "지금 엔비디아 때문에 많이 떨어졌던데", "환율 때문에 삼전이 약한 거래",
                     "다음 분기 실적 발표 나오면 영업이익 확인", "사업 보고서 배당 내용 알려줘", "팔로우한 종목 정리"]:
            self.assertFalse(is_decision_question(text), text)


class AddNoteTest(unittest.TestCase):
    def _draft(self, memo, explanation="종가는 1,183,000원이에요."):
        return UpdateDraft(item=replace(ITEM, memo_text=memo), type="news", title="t", summary="요약이에요.",
                           reason="r", explanation=explanation)

    def test_appends_to_explanation_once(self):
        d = self._draft("하닉 지금 탑승 가능?")
        self.assertTrue(add_decision_note(d, {}))
        self.assertEqual(d.explanation, f"종가는 1,183,000원이에요. {NOTE}")
        self.assertEqual(d.summary, "요약이에요.")
        self.assertEqual(d.decision_note, NOTE)
        self.assertFalse(add_decision_note(d, {}))                       # 두 번 붙이지 않는다
        self.assertEqual(d.explanation.count(NOTE), 1)

    def test_summary_when_no_explanation(self):
        d = self._draft("오를까?", explanation="")
        add_decision_note(d, {})
        self.assertEqual(d.summary, f"요약이에요. {NOTE}")

    def test_skips_other_questions_and_switch_off(self):
        d = self._draft("HBM이 뭐야?")
        self.assertFalse(add_decision_note(d, {}))
        self.assertEqual(d.explanation, "종가는 1,183,000원이에요.")
        d = self._draft("사야 되나?")
        self.assertFalse(add_decision_note(d, {"decision_note": False}))


class AskFlowTest(unittest.TestCase):
    def test_ask_answer_gets_note_and_no_related_news(self):
        out = check_topic(ITEM, [disc(), news()], reply(), [], CFG)
        self.assertEqual(out.kind, "update")
        self.assertEqual(out.draft.related_news, [])                      # 질문 답에는 관련 기사 목록을 만들지 않는다
        self.assertTrue(out.draft.summary.endswith(NOTE))
        self.assertEqual([r for r, _ in out.draft.sources], ["disc:R1#0"])  # 답에 쓴 근거는 그대로

    def test_topic_card_still_gets_related_news(self):
        item = replace(ITEM, category="A1", memo_text="배당 소식 알려줘")
        out = check_topic(item, [disc(), news()], reply(), [], CFG)
        self.assertEqual(out.kind, "update")
        self.assertEqual([r for r, _ in out.draft.related_news], ["news:9"])
        self.assertNotIn(NOTE, out.draft.summary)


if __name__ == "__main__":
    unittest.main()
