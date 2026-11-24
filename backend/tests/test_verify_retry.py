"""실험(2026-11-18): 검수 범위(verify_scope)·검수 실패 시 한 번 다시 쓰기(verify_retry) (topic._judge_v2)."""

import json
import unittest

from pipelines.updates.models import Candidate
from pipelines.updates.topic import check_topic

from tests.test_card_v2 import CFG, ITEM, disc

ON = {**CFG, "verify_call": True, "explanation": {"enabled": True, "max_sentences": 3, "max_chars": 200}}
GOOD = "SK하이닉스는 보통주 1주당 20,000원을 분기배당으로 주기로 했어요. 배당기준일은 2026-11-30이에요."
BAD = "SK하이닉스는 보통주 1주당 20,000원을 분기배당으로 주기로 했어요. 배당기준일은 당일이에요."


def payload(exp):
    return json.dumps({"status": "update", "headline": "SK하이닉스 분기배당 결정", "when": "2026-10-28",
                       "facts": [{"text": "보통주 1주당 20,000원 분기배당을 결정했어요.", "evidence_id": "E1"}],
                       "explanation": exp, "memo_link": "메모의 '배당' 관심사와 연결돼요.", "sources": ["E1"],
                       "confidence": 0.9}, ensure_ascii=False)


class FakeLLM:
    """카드 호출은 answers를 차례로, 검수 호출은 '당일'이 든 문장만 막는다."""

    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if "검수기입니다" in prompt:
            sents = prompt.rsplit("[검수할 문장]", 1)[1].strip().splitlines()
            return json.dumps({"results": [{"index": i, "supported": "당일" not in s, "reason": "근거에 없음"}
                                           for i, s in enumerate(sents)]}, ensure_ascii=False)
        return self.answers.pop(0)

    def verified(self):
        return [p.rsplit("[검수할 문장]", 1)[1].strip().splitlines() for p in self.prompts if "검수기입니다" in p]


class VerifyRetryTest(unittest.TestCase):
    def test_without_retry_card_is_dropped(self):
        llm = FakeLLM(payload(BAD))
        out = check_topic(ITEM, [disc()], llm, [], ON)
        self.assertEqual((out.kind, out.fail_codes), ("no_update", ["VERIFY_UNSUPPORTED"]))
        self.assertEqual(len(llm.prompts), 2)                       # 카드 1 + 검수 1, 다시 쓰지 않는다

    def test_retry_fixes_blocked_sentence(self):
        llm = FakeLLM(payload(BAD), payload(GOOD))
        out = check_topic(ITEM, [disc()], llm, [], {**ON, "verify_retry": 1})
        self.assertEqual(out.kind, "update")
        self.assertTrue(out.retried)
        self.assertEqual(out.draft.explanation, GOOD)
        repair = llm.prompts[2]
        self.assertIn("# 수정 요청", repair)                          # usage.stage_of → format_retry (카드 모델로 감)
        self.assertIn("배당기준일은 당일이에요. → 근거에 없음", repair)  # 막힌 문장과 이유를 알려 준다
        self.assertEqual(len(llm.verified()), 2)                    # 다시 쓴 카드도 검수한다

    def test_retry_still_blocked_is_dropped_with_both_notes(self):
        llm = FakeLLM(payload(BAD), payload(BAD))
        out = check_topic(ITEM, [disc()], llm, [], {**ON, "verify_retry": 1})
        self.assertEqual((out.kind, out.fail_codes), ("no_update", ["VERIFY_UNSUPPORTED"]))
        self.assertTrue(any(n.startswith("(다시 쓴 뒤)") for n in out.verify_notes))
        self.assertEqual(len(llm.prompts), 4)                       # 다시 쓰기는 한 번뿐

    def test_retry_no_update_is_kept_as_no_update(self):
        no = json.dumps({"status": "no_update", "headline": "", "when": "", "facts": [], "explanation": "",
                         "memo_link": "", "sources": [], "confidence": 0.9})
        out = check_topic(ITEM, [disc()], FakeLLM(payload(BAD), no), [], {**ON, "verify_retry": 1})
        self.assertEqual(out.kind, "no_update")

    def test_scope_explanation_skips_facts(self):
        llm = FakeLLM(payload(GOOD))
        check_topic(ITEM, [disc()], llm, [], {**ON, "verify_scope": "explanation"})
        self.assertEqual(llm.verified(), [["0. SK하이닉스는 보통주 1주당 20,000원을 분기배당으로 주기로 했어요.",
                                           "1. 배당기준일은 2026-11-30이에요."]])
        llm = FakeLLM(payload(GOOD))
        check_topic(ITEM, [disc()], llm, [], ON)                    # 기본: facts + 설명 문단
        self.assertEqual(len(llm.verified()[0]), 3)

    def test_ask_overrides_scope_only_for_ask(self):
        cfg = {**ON, "ask_overrides": {"verify_scope": "explanation"}}
        llm = FakeLLM(payload(GOOD))
        check_topic(ITEM, [disc()], llm, [], cfg)                   # 알림 항목은 그대로 facts까지
        self.assertEqual(len(llm.verified()[0]), 3)


if __name__ == "__main__":
    unittest.main()
