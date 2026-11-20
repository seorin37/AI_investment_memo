"""메모 문장 판정 테스트 (WO-020, WO-021) — 로직 단계·LLM 인터페이스·평가. DB·GPU·외부 API 없음."""

import json
import re
import unittest

from pipelines.common.config import REPO_ROOT
from pipelines.tracking import llm
from pipelines.tracking.clean import clean, is_meaningless
from pipelines.tracking.evaluate import evaluate, load_gold
from pipelines.tracking.judge import PENDING, judge_memo
from pipelines.tracking.lexicon import load_lexicon
from pipelines.tracking.price import find_amounts, parse_price
from pipelines.tracking.segment import split_sentences

LEX = load_lexicon()


def judge_one(text, symbol="005930"):
    results = judge_memo(text, symbol, LEX)
    assert len(results) == 1, results
    return results[0]


class SegmentTest(unittest.TestCase):
    def test_newline_and_punctuation_with_spans(self):
        text = "HBM 실적 보기. 배당도 체크?\n- 7만 돌파 시 알림"
        segs = split_sentences(text)
        self.assertEqual([s.text for s in segs], ["HBM 실적 보기.", "배당도 체크?", "- 7만 돌파 시 알림"])
        for s in segs:
            self.assertEqual(text[s.span[0]:s.span[1]], s.text)

    def test_decimal_point_is_not_boundary(self):
        self.assertEqual(len(split_sentences("영업이익률 3.5% 유지되는지 보기")), 1)

    def test_blank_lines_skipped(self):
        self.assertEqual([s.index for s in split_sentences("a\n\n  \nb")], [0, 1])

    def test_flat_memo_split_by_endings(self):
        # WO-021: 사람들은 줄바꿈·문장부호 없이 이어 쓴다
        text = "씨발 클코야 삼성전자 왜케 안 오르냐 요즘 뭐 상황 안좋아 ㅅㅂ 7만 깨지면 손절함 ㅋㅋㅋ"
        segs = split_sentences(text, LEX)
        self.assertEqual([s.text for s in segs],
                         ["씨발 클코야 삼성전자 왜케 안 오르냐", "요즘 뭐 상황 안좋아", "ㅅㅂ 7만 깨지면 손절함 ㅋㅋㅋ"])
        for s in segs:
            self.assertEqual(text[s.span[0]:s.span[1]], s.text)

    def test_not_split_inside(self):
        for text in ["삼성전자 HBM 보기",                       # 종목명이 "자"로 끝남
                     "세 가지는 분기마다 확인하고 싶다",          # "~마다"
                     "실제로 지켜지는지 확인하고 싶습니다",        # "~는지"
                     "비트코인 오르니까 반도체 수요도 늘 듯",      # "~니까", 명사 "수요"
                     "지금보다 10% 빠지면 조금 더 사겠습니다",     # "~보다"
                     "다음 주 실적발표 전에 다시 들어갈지 고민",    # 명사 "다음"
                     "그거 결과 나오면 꼭 확인"]:
            self.assertEqual(len(split_sentences(text, LEX)), 1, text)

    def test_noun_and_single_syllable_endings(self):
        self.assertEqual([s.text for s in split_sentences("둘 다 체크 7만 밑이면 고민 봐야 함 날씨 좋다", LEX)],
                         ["둘 다 체크", "7만 밑이면 고민", "봐야 함", "날씨 좋다"])

    def test_filler_attached_to_previous_on_same_line(self):
        self.assertEqual([s.text for s in split_sentences("개빡치네 진짜", LEX)], ["개빡치네 진짜"])
        self.assertEqual([s.text for s in split_sentences("HBM 보기\nㅋㅋ", LEX)], ["HBM 보기", "ㅋㅋ"])


class CleanTest(unittest.TestCase):
    def test_profanity_and_vocative_removed_original_kept(self):
        text = "씨발 클코야 삼성전자 왜케 안 오르냐"
        c = clean(text, LEX)
        self.assertEqual(c.text, "삼성전자 왜케 안 오르냐")
        self.assertEqual(set(c.flags), {"profanity", "vocative"})

    def test_pii_masked(self):
        c = clean("연락 010-1234-5678 이나 a.b@c.com", LEX)
        self.assertIn("[전화번호]", c.text)
        self.assertIn("[이메일]", c.text)
        self.assertNotIn("1234", c.text)
        self.assertEqual(c.flags, ("pii_masked",))

    def test_meaningless_after_clean(self):
        self.assertTrue(is_meaningless(clean("개빡치네 진짜", LEX).text, LEX))
        self.assertTrue(is_meaningless("ㅋㅋㅋ", LEX))
        self.assertFalse(is_meaningless("삼전 첨 사봄 ㅎㅎ", LEX))


class PriceTest(unittest.TestCase):
    def test_amount_forms(self):
        cases = {"7만": 70000, "7만원": 70000, "70,000": 70000, "칠만": 70000, "70k": 70000, "6만 5천": 65000, "40만": 400000}
        for text, value in cases.items():
            self.assertEqual([a.value for a in find_amounts(text + " 깨지면")], [value], text)

    def test_not_prices(self):
        for text in ["10주 더 모으기", "3% 먹고 나옴", "2027년 실적", "파운드리 2나노"]:
            self.assertEqual(find_amounts(text), [], text)

    def test_condition_needs_marker(self):
        self.assertEqual(parse_price("7만 원 깨지면", LEX).direction, "below")
        self.assertEqual(parse_price("7만 돌파 시 알림", LEX).direction, "above")
        self.assertIsNone(parse_price("나오면 20만 넘을 듯", LEX))  # 예측은 조건이 아니다

    def test_unsupported(self):
        for text in ["6만 5천에서 7만 사이에서 모으기", "지금보다 10% 빠지면 사기", "52주 신저가 오면 알려줘",
                     "PBR 1배 근처면 분할 매수", "거래량 터지면 알려줘"]:
            self.assertEqual(parse_price(text, LEX).kind, "unsupported", text)
        self.assertIsNone(parse_price("PER 5배는 너무 싼 거 아닌가 싶음", LEX))

    def test_unsupported_relative_and_technical(self):
        """평가 메모 1,000개에서 규칙을 빠져나가 LLM으로 간 가격 조건들 (거래량 배수·신저가·전저점·이동평균선·기준어 없는 %)."""
        for text in ["삼성 거래량 평소 두 배 넘으면 다시 볼 생각", "naver 전저점 깨지면 알려줘...", "NAVER 신저가 깨지면 알려줘",
                     "네이버 10% 오르면 체크해야지", "하이닉스 60일선 넘으면 알려줘"]:
            self.assertEqual(parse_price(text, LEX).kind, "unsupported", text)
        # 사업 수치의 변화나 일반 문장은 가격 조건이 아니다
        for text in ["영업이익 10% 늘면 좋겠다", "배당 5% 오르면 좋겠다", "거래량 많은 종목 보기", "60일 동안 지켜보기"]:
            self.assertIsNone(parse_price(text, LEX), text)

    def test_relative_with_base_words_and_fillers(self):
        """2026-11-09 memos_long: 기준어(여기서·바닥·최근 저점)와 %·동사 사이 '더·넘게'. 상대 조건은 계속 확인 필요."""
        for text in ["여기서 10% 더 빠지면 알려줘.", "네이버 지금 바닥 근처 같은데 여기서 5% 더 빠지면 한 번 더 물타볼게요.",
                     "최근 바닥에서 10% 넘게 오르면 알려주세요.", "네이버 최근 저점 다시 깨면 알려줘...",
                     "5% 넘게 빠지면 알려줘", "10% 더 오르면 일부 팔기", "10% 이상 빠지면 알려줘", "20% 이상 더 오르면 팔기"]:
            self.assertEqual(parse_price(text, LEX).kind, "unsupported", text)
            self.assertEqual(judge_one(text).decision, "needs_confirmation", text)
        self.assertIsNone(parse_price("영업이익 10% 넘게 늘면 좋겠다", LEX))          # 사업 수치는 그대로 제외
        self.assertIsNone(parse_price("매출 10% 이상 늘면 좋겠다", LEX))

    def test_si_inside_words_is_not_condition(self):
        """'다시·역시·혹시'의 '시'는 조건 표지가 아니다 (예측 문장이 미지원 조건으로 잡히던 오탐)."""
        for text in ["이대로면 지금보다 15%는 다시 갈 거요.", "지금보다 10%는 역시 비싸다", "고점 대비 20% 혹시 모르니까"]:
            self.assertIsNone(parse_price(text, LEX), text)
        self.assertEqual(parse_price("7만 돌파 시 알림", LEX).direction, "above")      # 띄어 쓴 '시'는 그대로 조건
        self.assertEqual(parse_price("7만 돌파시 알림", LEX).direction, "above")
        self.assertEqual(parse_price("고점 대비 30% 하락 시 알림", LEX).kind, "unsupported")
        self.assertEqual(parse_price("다시 7만 깨지면 알려줘", LEX).price, 70000)


class JudgeTest(unittest.TestCase):
    def test_c1_price_with_action(self):
        j = judge_one("ㅅㅂ 7만 깨지면 손절함")
        self.assertEqual((j.decision, j.category), ("partial", "C1"))
        self.assertEqual(j.items[0]["price_threshold"], 70000)
        self.assertEqual(j.context_note, "손절함")
        self.assertEqual(j.text, "ㅅㅂ 7만 깨지면 손절함")  # 원문 불변

    def test_a2_price_notify(self):
        j = judge_one("7만 돌파 시 알림")
        self.assertEqual((j.decision, j.category, j.items[0]["type"]), ("normal", "A2", "price_above"))

    def test_profanity_with_content_goes_to_llm_not_dropped(self):
        js = judge_memo("씨발 클코야 삼성전자 왜케 안 오르냐 요즘 뭐 상황 안좋아?", "005930", LEX)
        self.assertEqual([j.decision for j in js], [PENDING, PENDING])  # "~냐" 뒤에서 나뉘고, 둘 다 LLM으로
        self.assertEqual(js[0].cleaned_text, "삼성전자 왜케 안 오르냐")

    def test_price_with_other_content_also_goes_to_llm(self):
        # 분리가 덜 돼 앞에 다른 내용이 있으면 가격 항목은 확정하고 문장은 LLM에도 넘긴다
        j = judge_one("HBM 실적 계속 보고 7만 깨지면 손절")
        self.assertEqual(j.decision, PENDING)
        self.assertEqual(j.items[0]["price_threshold"], 70000)
        self.assertEqual(judge_one("ㅅㅂ 7만 깨지면 손절함 ㅋㅋㅋ").context_note, "손절함")

    def test_long_chunks_not_dropped_by_spam_or_scope(self):
        self.assertEqual(judge_one("카톡 오픈채팅 고수익 보장 링크 http://bit.ly/x 솔리다임 매각설은 계속 볼 것",
                                   symbol="000660").decision, PENDING)
        self.assertEqual(judge_one("홍콩 ELS 충당금 추가로 쌓는지 배상 끝나면 비중 늘리기 요즘 무릎이 아파서 병원 다녀옴",
                                   symbol="105560").decision, PENDING)

    def test_spam_and_out_of_scope(self):
        self.assertEqual(judge_one("리딩방 무료입장 010-1234-5678").category, "B6")
        self.assertEqual(judge_one("비트코인이나 할까").category, "B5")
        # 범위 밖 단어가 섞여도 금융 내용이 있으면 버리지 않는다
        self.assertEqual(judge_one("비트코인 오르니까 반도체 수요도 늘 듯").decision, PENDING)

    def test_other_symbol_marked(self):
        j = judge_one("삼전이 더 싸 보이는데 갈아탈까", symbol="000660")
        self.assertEqual(j.other_symbol, "005930")
        self.assertEqual(j.decision, PENDING)  # 종목 비교·판단은 LLM

    def test_alias_longest_match(self):
        self.assertEqual(LEX.find_symbols("삼성바이오 좋네"), ["207940"])
        self.assertEqual(LEX.find_symbols("KBS 뉴스"), [])

    def test_cache_reuse(self):
        cache = {"HBM 실적 보기": {"decision": "normal", "category": "A1", "reason_code": "TOPIC",
                                   "items": [{"type": "topic", "description": "HBM 실적 변화"}]}}
        j = judge_memo("HBM 실적 보기", "005930", LEX, cache)[0]
        self.assertEqual((j.decision, j.judged_by), ("normal", "cache"))


class LLMInterfaceTest(unittest.TestCase):
    def setUp(self):
        self.js = judge_memo("HBM 실적 보기\nㅋㅋ\n그거 4분기에 확인", "005930", LEX)

    def test_prompt_marks_pending_and_context(self):
        prompt = llm.build_prompt("005930", "삼성전자", self.js)
        self.assertIn("0. [판정] HBM 실적 보기", prompt)
        self.assertIn("1. [맥락] ㅋㅋ", prompt)

    def test_parse_rejects_invalid_rows(self):
        raw = "설명...\n" + json.dumps([
            {"sentence_index": 0, "decision": "normal", "category": "A1", "items": [{"type": "topic", "description": "HBM 실적"}], "confidence": 0.9},
            {"sentence_index": 2, "decision": "normal", "category": "Z9", "items": []},  # 없는 분류
            {"sentence_index": 2, "decision": "normal", "category": "A3", "items": [{"type": "volume"}]},
        ], ensure_ascii=False)
        rows = llm.parse_response(raw)
        self.assertEqual([r["sentence_index"] for r in rows], [0])
        self.assertEqual(llm.parse_response("JSON 아님"), [])

    def test_short_keys_and_category_consistency(self):
        raw = json.dumps([
            {"i": 0, "cat": "A1", "dec": "normal", "items": [{"d": "HBM 실적", "k": ["HBM"]}], "conf": 0.9},
            {"i": 2, "cat": "A3", "dec": "normal", "merge": {"s": 0, "n": 0}, "ref": "HBM 실적", "conf": 0.9},
            {"i": 3, "cat": "B4", "dec": "normal", "items": [{"d": "공부"}], "conf": 0.9},  # 모순: B인데 추적
        ], ensure_ascii=False)
        rows = {r["sentence_index"]: r for r in llm.parse_response(raw)}
        self.assertEqual(rows[0]["items"][0]["description"], "HBM 실적")
        self.assertEqual(rows[2]["merge_into"], {"sentence_index": 0, "item_index": 0})
        self.assertEqual((rows[3]["decision"], rows[3]["items"], rows[3]["reason_code"]), ("full_fallback", [], "SELF_TODO"))

    def test_missing_or_low_confidence_becomes_confirmation(self):
        rows = [{"sentence_index": 0, "decision": "normal", "category": "A1", "items": [], "confidence": 0.95},
                {"sentence_index": 2, "decision": "normal", "category": "A3", "items": [], "confidence": 0.3}]
        out = llm.apply_llm(self.js, rows)
        self.assertEqual(out[0].decision, "normal")
        self.assertEqual(out[1].decision, "full_fallback")  # 로직 판정은 그대로
        self.assertEqual((out[2].decision, out[2].reason_code), ("needs_confirmation", "LOW_CONFIDENCE"))

    def test_rule_price_item_kept_after_llm(self):
        js = judge_memo("HBM 실적 계속 보고 7만 깨지면 손절", "005930", LEX)
        rows = [{"sentence_index": 0, "decision": "partial", "category": "C1", "confidence": 0.9,
                 "items": [{"type": "topic", "description": "HBM 실적 변화"},
                           {"type": "price_below", "description": "7만 아래", "price_threshold": 70000}]}]
        out = llm.apply_llm(js, rows)[0]
        self.assertEqual(sorted(it["type"] for it in out.items), ["price_below", "topic"])

    def test_price_item_without_threshold_becomes_confirmation(self):
        """LLM이 상대 조건을 가격 항목으로 내면서 조건가를 비우면 카드 단계로 넘기지 않는다."""
        for threshold in (None, "30%", 0, True):
            js = judge_memo("HBM 실적 보기\nㅋㅋ\n그거 4분기에 확인", "005930", LEX)
            rows = [{"sentence_index": 0, "decision": "normal", "category": "A2", "confidence": 0.9,
                     "items": [{"type": "price_below", "description": "고점 대비 30% 하락", "price_threshold": threshold}]}]
            out = llm.apply_llm(js, rows)[0]
            self.assertEqual((out.decision, out.reason_code), ("needs_confirmation", "PRICE_THRESHOLD_MISSING"), threshold)
        js = judge_memo("HBM 실적 보기", "005930", LEX)
        ok = [{"sentence_index": 0, "decision": "normal", "category": "A2", "confidence": 0.9,
               "items": [{"type": "price_below", "description": "7만 아래", "price_threshold": 70000}]}]
        self.assertEqual(llm.apply_llm(js, ok)[0].decision, "normal")

    def test_single_call_only_when_pending(self):
        calls = []
        llm.judge_with_llm(judge_memo("ㅋㅋ", "005930", LEX), "005930", "삼성전자", lambda p: calls.append(p) or "[]")
        self.assertEqual(calls, [])
        llm.judge_with_llm(self.js, "005930", "삼성전자", lambda p: calls.append(p) or "[]")
        self.assertEqual(len(calls), 1)


class EvaluateTest(unittest.TestCase):
    def test_gold_set_rule_stage_safety(self):
        gold = load_gold(REPO_ROOT / "eval" / "memo_eval_v0" / "memo_eval_v0.jsonl")
        self.assertEqual(len(gold), 35)
        s = evaluate(gold, LEX)["summary"]
        self.assertEqual(s["segmentation_sentence_match"], 1.0)
        self.assertEqual(s["missed_tracking"], 0)   # 로직이 추적 의도를 버리면 안 된다
        self.assertEqual(s["flat_missed_tracking"], 0)  # 한 줄로 이어 써도 버리면 안 된다
        self.assertEqual(s["over_tracking"], 0)
        self.assertEqual(s["pii_recall"], 1.0)
        self.assertEqual(s["price_extra"], 0)



class RelativeParseTest(unittest.TestCase):
    """상대 가격 조건 풀어 보기 (확인 질문 선택지용, 판정은 그대로)."""

    def test_cases(self):
        from pipelines.tracking.price import RelativeCondition, parse_relative
        cases = {
            "삼성전자 고점에서 30% 넘게 빠지면 바로 알려주세요.": RelativeCondition("high", 30.0, "below", "고점"),
            "최근 바닥에서 10% 넘게 오르면 알려줘": RelativeCondition("low", 10.0, "above", "최근 바닥"),
            "여기서 10% 더 빠지면 추가 매수": RelativeCondition("current", 10.0, "below", "여기"),
            "지금 고점 대비 20% 내려오면": RelativeCondition("high", 20.0, "below", "고점"),
            "10% 오르면 체크": RelativeCondition("current", 10.0, "above", ""),
            "평단에서 15프로 떨어지면 손절": RelativeCondition("cost", 15.0, "below", "평단"),
            "전고점 뚫으면 알려줘": RelativeCondition("high", 0.0, "above", "전고점"),
            "52주 신저가 찍으면": RelativeCondition("low", 0.0, "below", "52주 신저가"),
            "신고가 찍으면 알려줘": RelativeCondition("high", 0.0, "above", "신고가"),
            "삼전 고점 대비 20% 넘넘게 빠지면 알림.": RelativeCondition("high", 20.0, "below", "고점"),   # 오타 '넘넘게'
            "전고점 다시 넘어서면 알려주세요": RelativeCondition("high", 0.0, "above", "전고점"),
        }
        for text, want in cases.items():
            self.assertEqual(parse_relative(text), want, text)
        self.assertIsNone(parse_relative("HBM 실적 계속 볼게요"))


if __name__ == "__main__":
    unittest.main()


class OpenAIClientTest(unittest.TestCase):
    """HTTP는 가짜로 바꾼다 — 네트워크·API 키 없음 (WO-022)."""

    class FakeResponse:
        def __init__(self, status, body=None):
            self.status_code, self._body, self.text = status, body or {}, json.dumps(body or {})

        def json(self):
            return self._body

    def make(self, responses):
        from pipelines.tracking.openai_client import OpenAIClient

        sent = []

        class Session:
            def post(_self, url, headers, json, timeout):
                sent.append((url, headers, json))
                return responses.pop(0)

        client = OpenAIClient(api_key="TEST-KEY", model="m", session=Session())
        return client, sent

    def ok_body(self, text):
        return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30}}

    def test_success_records_usage_and_json_mode(self):
        client, sent = self.make([self.FakeResponse(200, self.ok_body("[]"))])
        self.assertEqual(client("p"), "[]")
        url, headers, body = sent[0]
        self.assertIn("api.openai.com/v1/chat/completions", url)
        self.assertEqual(headers["Authorization"], "Bearer TEST-KEY")
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["temperature"], 0)
        self.assertIn("JSON", body["messages"][0]["content"])      # json_object 모드는 메시지에 JSON이라는 말이 필요하다
        self.assertEqual((client.calls[0].prompt_tokens, client.calls[0].output_tokens, client.calls[0].ok), (120, 30, True))

    def test_retry_on_quota_then_success(self):
        from unittest import mock

        client, sent = self.make([self.FakeResponse(429), self.FakeResponse(200, self.ok_body("[1]"))])
        with mock.patch("pipelines.common.retry.time.sleep"):
            self.assertEqual(client("p"), "[1]")
        self.assertEqual(len(sent), 2)

    def test_key_not_in_repr(self):
        client, _ = self.make([])
        self.assertNotIn("TEST-KEY", repr(client))

    def test_temperature_dropped_when_model_rejects_it(self):
        reject = self.FakeResponse(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0 with this model."}})
        client, sent = self.make([reject, self.FakeResponse(200, self.ok_body("[2]"))])
        self.assertEqual(client("p"), "[2]")
        self.assertIn("temperature", sent[0][2])
        self.assertNotIn("temperature", sent[1][2])

    def test_out_of_credit_is_not_retried(self):
        credit = self.FakeResponse(429, {"error": {"code": "insufficient_quota", "message": "quota"}})
        client, sent = self.make([credit])
        with self.assertRaises(RuntimeError):
            client("p")
        self.assertEqual(len(sent), 1)
        self.assertFalse(client.calls[0].ok)

    def test_reasoning_tokens_recorded_separately(self):
        body = self.ok_body("[]")
        body["usage"] = {"prompt_tokens": 100, "completion_tokens": 250,
                         "completion_tokens_details": {"reasoning_tokens": 200}}
        client, _ = self.make([self.FakeResponse(200, body), self.FakeResponse(200, self.ok_body("[]"))])
        client("p")
        client("q")
        self.assertEqual((client.calls[0].output_tokens, client.calls[0].reasoning_tokens), (250, 200))
        self.assertIsNone(client.calls[1].reasoning_tokens)                  # 세부 내역이 없는 응답
        from pipelines.tracking.openai_client import usage_totals

        self.assertEqual(usage_totals(client.calls),
                         {"llm_calls": 2, "prompt_tokens": 220, "output_tokens": 280, "reasoning_tokens": 200})

    def test_reasoning_effort_only_when_env_set(self):
        from unittest import mock

        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("LLM_REASONING_EFFORT", None)
            client, sent = self.make([self.FakeResponse(200, self.ok_body("[]"))])
            client("p")
            self.assertNotIn("reasoning_effort", sent[0][2])
            env["LLM_REASONING_EFFORT"] = "low"
            client, sent = self.make([self.FakeResponse(200, self.ok_body("[]"))])
            client("p")
            self.assertEqual(sent[0][2]["reasoning_effort"], "low")


class EvaluateLLMTest(unittest.TestCase):
    def test_perfect_fake_llm_scores(self):
        from pipelines.tracking.evaluate_llm import evaluate_llm

        gold = load_gold(REPO_ROOT / "eval" / "memo_eval_v0" / "memo_eval_v0.jsonl")
        # 호출은 정답 순서대로, 로직 미판정 문장이 있는 메모에서만 일어난다
        queue = [m for m in gold if any(j.decision == PENDING for j in judge_memo(m["text"], m["symbol"], LEX))]

        def fake(prompt):  # 정답을 그대로 돌려주는 가짜 LLM
            memo = queue.pop(0)
            pending = [int(m.group(1)) for m in re.finditer(r"^(\d+)\. \[판정\]", prompt, re.MULTILINE)]
            out = []
            for s in memo["sentences"]:
                if s["sentence_index"] in pending:
                    out.append({"sentence_index": s["sentence_index"], "decision": s["decision"],
                                "category": None if s["category"] == "-" else s["category"],
                                "reason_code": s["reason_code"], "merge_into": s["merge_into"],
                                "items": [it for it in s["items"] if it["type"] == "topic"], "confidence": 0.9})
            return json.dumps(out, ensure_ascii=False)

        s = evaluate_llm(gold, LEX, fake)["summary"]
        self.assertEqual(s["final_decision_accuracy"], 1.0)
        self.assertEqual(s["missed_tracking"], 0)
        self.assertEqual(s["tracked_units_match"], 1.0)
        self.assertEqual(s["merge_accuracy"], 1.0)


class TeamSetFixesTest(unittest.TestCase):
    """팀원 평가셋에서 드러난 약점 (WO-025)."""

    def split(self, text):
        return [s.text for s in split_sentences(text, LEX)]

    def test_slang_stock_name_not_split(self):
        self.assertEqual(LEX.find_symbols("6만전자 오면"), ["005930"])
        self.assertEqual(LEX.find_symbols("곧 50만닉스 간다"), ["000660"])
        self.assertEqual(LEX.find_symbols("케이비 NIM"), ["105560"])
        self.assertEqual(len(self.split("6만전자 오면 줍줍 고민해볼까 ㅋㅋ")), 1)

    def test_laugh_mid_line_is_boundary_but_profanity_jamo_is_not(self):
        self.assertEqual(self.split("아니 씨발 외국인 왜 계속 팔아 ㅋㅋ 요즘 수급 어케 되는거야"),
                         ["아니 씨발 외국인 왜 계속 팔아 ㅋㅋ", "요즘 수급 어케 되는거야"])
        self.assertEqual(self.split("아 ㅅㅂ 오늘 -8% 실화냐. ㅋㅋㅋㅋㅋ"), ["아 ㅅㅂ 오늘 -8% 실화냐. ㅋㅋㅋㅋㅋ"])
        self.assertEqual(self.split("어제 6만9천에 10주 물타기함 ㅠㅠ 개쫄리네"), ["어제 6만9천에 10주 물타기함 ㅠㅠ", "개쫄리네"])

    def test_profanity_chunk_attached(self):
        self.assertEqual(self.split("경영진 진짜 일 안하네 개XX들. 그거 결과 나오면 다시 판단하자"),
                         ["경영진 진짜 일 안하네 개XX들.", "그거 결과 나오면 다시 판단하자"])
        self.assertIn("profanity", clean("경영진 진짜 일 안하네 개XX들.", LEX).flags)

    def test_two_price_conditions(self):
        j = judge_one("30만 뚫으면 일부 익절, 25만 깨지면 손절 이렇게 가자", symbol="000660")
        self.assertEqual((j.decision, j.category), ("partial", "C1"))
        self.assertEqual([(i["type"], i["price_threshold"]) for i in j.items],
                         [("price_above", 300000), ("price_below", 250000)])

    def test_recovery_question_is_price_condition(self):
        j = judge_one("20만원대 회복 언제하냐 진짜", symbol="035420")
        # 가격 항목은 로직이 확정하고, 뒤에 남은 말("하냐 진짜")이 있어 최종 판정은 LLM에 맡긴다 (안전한 쪽)
        self.assertEqual((j.decision, j.items[0]["type"], j.items[0]["price_threshold"]), (PENDING, "price_above", 200000))

    def test_more_conditions_after_price_go_to_llm(self):
        j = judge_one("KB 9만원 밑으로 빠지면 추매, 근데 CET1 13% 밑이면 그땐 다시 생각해봐야", symbol="105560")
        self.assertEqual(j.decision, PENDING)  # CET1 조건은 LLM이 판단
        self.assertEqual(j.items[0]["price_threshold"], 90000)

    def test_trap_numbers_are_not_conditions(self):
        for text in ["어제 6만9천에 10주 물타기함 ㅠㅠ", "아 ㅅㅂ 오늘 -8% 실화냐.", "곧 50만닉스 간다 ㅋㅋㅋ",
                     "밸류업 공시대로 주주환원율 50% 진짜 맞추는지 매 분기 체크"]:
            self.assertEqual(judge_one(text).items, [], text)

    def test_team_set_rule_stage_safety(self):
        gold = load_gold(REPO_ROOT / "eval" / "memo_eval_team_v1" / "memo_eval_team_v1.jsonl")
        s = evaluate(gold, LEX)["summary"]
        self.assertEqual((s["missed_tracking"], s["over_tracking"], s["flat_missed_tracking"]), (0, 0, 0))
        self.assertGreaterEqual(s["segmentation_sentence_match"], 0.95)


class PromptLeakTest(unittest.TestCase):
    """프롬프트 예시가 평가 문장과 겹치면 점수가 부풀려진다 (시험 문제를 미리 알려 주는 셈, WO-028)."""

    def test_prompt_examples_do_not_overlap_eval_sentences(self):
        guide = llm.load_guide()
        examples = [q for q in re.findall(r'"([^"]+)"', guide) if len(q) >= 4]
        sentences = []
        for name in ("memo_eval_v0/memo_eval_v0.jsonl", "memo_eval_team_v1/memo_eval_team_v1.jsonl"):
            for memo in load_gold(REPO_ROOT / "eval" / name):
                sentences += [s["text"] for s in memo["sentences"]]
        leaks = [(q, s) for q in examples for s in sentences if q in s or (len(s) >= 8 and s in guide)]
        self.assertEqual(leaks, [])


class ProfanityPrefixTest(unittest.TestCase):
    """강조 접두사가 붙은 욕설과 욕만 남은 문장 (WO-029)."""

    def test_prefixed_profanity_removed(self):
        for text in ["삼성 개씨발", "맥북 개쓰레기", "존나씨발 또 빠짐"]:
            self.assertIn("profanity", clean(text, LEX).flags, text)
        self.assertEqual(clean("삼성 개씨발", LEX).text, "삼성")

    def test_only_stock_name_left_after_profanity_is_emotion(self):
        j = judge_one("삼성 개씨발", symbol="000660")
        self.assertEqual((j.decision, j.category), ("full_fallback", "B1"))
        self.assertEqual(j.text, "삼성 개씨발")  # 원문 불변

    def test_stock_name_alone_without_profanity_goes_to_llm(self):
        self.assertEqual(judge_one("삼성").decision, PENDING)

    def test_profanity_with_content_still_goes_to_llm(self):
        self.assertEqual(judge_one("삼성 개씨발 왜 계속 빠지냐").decision, PENDING)

    def test_ordinary_words_starting_with_gae_not_flagged(self):
        for text in ["개인 투자자 순매수 확인", "개장 전 공시 체크", "개발 일정 보기"]:
            self.assertEqual(clean(text, LEX).flags, (), text)


class DomainVocabTest(unittest.TestCase):
    """공시 청크로 만든 도메인 단어 사전 (WO-030)."""

    def test_vocab_loaded_and_has_domain_terms(self):
        self.assertGreater(len(LEX.domain_vocab), 10000)
        for w in ["hbm", "수율", "파운드리", "배당", "외국인"]:
            self.assertIn(w, LEX.domain_vocab, w)
        for w in ["맥북", "떡상"]:
            self.assertNotIn(w, LEX.domain_vocab, w)

    def test_no_domain_short_sentence_dropped_without_api(self):
        j = judge_one("이상규 맥북 개쓰레기", symbol="000660")
        self.assertEqual((j.decision, j.category), ("full_fallback", "B5"))
        self.assertIn("no_domain", j.flags)

    def test_everyday_question_dropped(self):
        # WO-031: "뭐"는 일상 말이라 보호 표현이 아니다
        for text in ["이민성 뭐하냐", "점심 뭐 먹지"]:
            self.assertEqual(judge_one(text, symbol="000660").decision, "full_fallback", text)
        # 이유를 묻는 질문과 도메인 단어가 있는 질문은 유지
        for text in ["왜 이렇게 빠지냐", "요즘 수급 뭐가 문제야?"]:
            self.assertNotEqual(judge_one(text, symbol="000660").decision, "full_fallback", text)

    def test_intent_or_pronoun_sentences_kept(self):
        for text in ["친구가 무조건 간다는데 ㄹㅇ", "이거 계속 체크해줘", "이거 중요함.", "그거 결과 나오면 다시 판단하자"]:
            self.assertNotEqual(judge_one(text).decision, "full_fallback", text)

    def test_domain_word_sentences_kept(self):
        for text in ["HBM4 수율 계속 보고싶음", "외국인 순매도 이어지는 듯"]:
            self.assertNotEqual(judge_one(text).decision, "full_fallback", text)

    def test_both_eval_sets_never_drop_tracked(self):
        for name in ("memo_eval_v0/memo_eval_v0.jsonl", "memo_eval_team_v1/memo_eval_team_v1.jsonl"):
            s = evaluate(load_gold(REPO_ROOT / "eval" / name), LEX)["summary"]
            self.assertEqual((s["missed_tracking"], s["over_tracking"], s["flat_missed_tracking"]), (0, 0, 0), name)

class KospiMemoRuleTest(unittest.TestCase):
    """2026-11-19 코스피 메모 dry-run (별칭 사전 26종목 밖 종목). 팀원 수정(내려오면·증자·해군) 위에서."""

    def test_price_with_ieon(self):
        # '밑이면'·'아래이면': 방향어 뒤 '이면' (K05 "엘전 12만 밑이면 산다"가 항목도 응답도 없이 빠졌다)
        for text, value in (('12만 밑이면 산다', 120000), ('12만원 밑이면 산다', 120000), ('5만 아래이면 산다', 50000)):
            p = parse_price(text, LEX)
            self.assertEqual((p.direction, p.price), ('below', value), text)
        self.assertEqual(parse_price('10만 이상이면 팔자', LEX).direction, 'above')
        j = judge_one('엘전 12만 밑이면 산다', symbol='066570')
        self.assertEqual([(i['type'], i['price_threshold']) for i in j.items], [('price_below', 120000)])
        self.assertEqual(parse_price('5만 아래로 내려오면 알림', LEX).price, 50000)          # 팀원 수정 그대로

    def test_latin_company_name_not_sentence_end(self):
        # "LG전자 인도 법인 …"이 "LG전자"에서 잘려 "LG전자 관련 소식" 항목이 생겼다 (K04)
        for text in ('LG전자 인도 법인 상장 이후 지분가치 반영되는지, 4분기 실적 가이던스 나오면 확인',
                     'LG전자 실적 확인', '대덕전자 실적 확인', 'SK텔레콤 배당 확인'):
            self.assertEqual(len(split_sentences(text)), 1, text)
        self.assertEqual([s.text for s in split_sentences('결국 TSMC다 삼성은 멀었음')], ['결국 TSMC다', '삼성은 멀었음'])
        self.assertEqual(len(split_sentences('유상증자 한다던데 괜찮나')), 1)                 # 팀원 수정 그대로
