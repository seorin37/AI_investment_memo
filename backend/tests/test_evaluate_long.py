"""memos_long 평가: 판정 조각을 모두 저장하고 다른 정답 세트로 다시 채점 (DB·LLM 없음)."""

import json
import tempfile
import unittest
from pathlib import Path

from pipelines.tracking.evaluate_long import (align_memo, fragment, judgment_record, rescore, score, sentence_records,
                                              write_out)


def judged(idx, text, span, decision):
    return fragment({"sentence_index": idx, "text": text, "span": list(span), "cleaned_text": text, "decision": decision,
                     "category": None, "reason_code": None, "items": [], "merge_into": None, "judged_by": "llm",
                     "confidence": None, "sub_sentences": [], "other_symbol": None})


BODY = "HBM 매출 계속 볼게요 실적 발표도 챙길게요. 오를 것 같아요."
FRAGS = [judged(0, "HBM 매출 계속 볼게요", (0, 13), "normal"),
         judged(1, "실적 발표도 챙길게요.", (14, 26), "normal"),
         judged(2, "오를 것 같아요.", (27, 36), "full_fallback")]


def memo(sentences):
    return {"memo_id": "M1", "company_primary": "SK하이닉스", "memo_body": BODY, "memo_body_clean": BODY,
            "sentences": [{"text": t, "intended_type": c, "expected_decision": d} for t, c, d in sentences]}


V1 = memo([("HBM 매출 계속 볼게요 실적 발표도 챙길게요.", "A1", "추적"), ("오를 것 같아요.", "B2", "추적 안 함")])
V2 = memo([("HBM 매출 계속 볼게요", "A1", "추적"), ("실적 발표도 챙길게요.", "A3", "추적"), ("오를 것 같아요.", "B2", "추적 안 함")])


class EvaluateLongTest(unittest.TestCase):
    def test_fragments_keep_every_overlap(self):
        rows = align_memo(V1, FRAGS)
        self.assertEqual([f["sentence_index"] for f in rows[0]["fragments"]], [0, 1])   # 겹치는 조각 둘 다
        self.assertEqual(rows[0]["segmentation"], "gold_split")
        self.assertEqual(rows[0]["best"].sentence_index, 0)                             # 채점은 가장 많이 겹친 조각 (13자 > 12자)
        self.assertEqual([f["overlap"] for f in rows[0]["fragments"]], [13, 12])
        self.assertEqual([f["sentence_index"] for f in rows[1]["fragments"]], [2])

    def test_rescore_with_new_gold_uses_saved_fragments(self):
        """v1으로 저장한 조각 판정을 정답을 쪼갠 v2에 다시 맞춰도 문장마다 판정이 있다 (P067-L2 같은 경우)."""
        logic = {0: "pending_llm", 1: "pending_llm", 2: "full_fallback"}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            recs = sentence_records(V1, "000660", FRAGS, None, logic)
            write_out(out, recs, [judgment_record(V1, "000660", FRAGS, logic, None)], score(recs))
            saved = json.loads((out / "judgments.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(len(saved["judged"]), 3)                                   # 조각 3개 모두 저장
            self.assertNotIn("_pred", (out / "sentences.jsonl").read_text(encoding="utf-8"))
            recs2, info = rescore([V2], out / "judgments.jsonl")
        self.assertEqual(info, {"memos_missing": [], "memo_body_changed": []})
        self.assertEqual([r["pred_text"] for r in recs2], [f.to_dict()["text"] for f in FRAGS])
        self.assertEqual(score(recs2)["no_judgment"], 0)
        self.assertEqual(score(recs2)["score"]["decision_accuracy"], 1.0)

    def test_rescore_skips_changed_body(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            write_out(out, [], [judgment_record(V1, "000660", FRAGS, {}, None)], {})
            changed = {**V2, "memo_body": BODY + " 추가", "memo_body_clean": BODY + " 추가"}
            recs, info = rescore([changed, {**V2, "memo_id": "M9"}], out / "judgments.jsonl")
        self.assertEqual((recs, info["memo_body_changed"], info["memos_missing"]), ([], ["M1"], ["M9"]))


if __name__ == "__main__":
    unittest.main()
