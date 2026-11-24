"""즉석 비교 계산 (pipelines.updates.calc, 실험 2026-11-17)."""

import unittest

from pipelines.updates.calc import compute
from pipelines.updates.judge import parse_card_v2
from pipelines.updates.models import Candidate, Evidence


def ev(eid, text, ref):
    c = Candidate(ref=ref, kind="disclosure", symbol="000000", date="2025-12-31", title="사업보고서", text=text,
                  url=None, source="DART", similarity=0.7)
    return Evidence(eid, c, text)


EVIDENCE = [ev("E1", "자본변동표: 유상증자 4조 2,087억원 반영", "disc:1#0"),
            ev("E2", "2025년 연간 (연결): 영업이익 3조 893억 2,018만 1,000원 · 2024년 연간 영업이익 1조 7,318억 7,882만 5,342원", "fin:1")]


def calc(op, a, ea, b, eb, label="a ÷ b"):
    return {"label": label, "op": op, "a": {"value": a, "evidence_id": ea}, "b": {"value": b, "evidence_id": eb}}


class CalcTest(unittest.TestCase):
    def test_div_pct_change(self):
        rows = compute([calc("div", "4조 2,087억원", "E1", "3조 893억 2,018만 1,000원", "E2"),
                        calc("pct", "4조 2,087억원", "E1", "3조 893억 2,018만 1,000원", "E2"),
                        calc("change", "3조 893억 2,018만 1,000원", "E2", "1조 7,318억 7,882만 5,342원", "E2")], EVIDENCE)
        self.assertEqual([r["ok"] for r in rows], [True, True, True])
        self.assertEqual(rows[0]["result"], "약 1.36배")
        self.assertEqual(rows[1]["result"], "136.2%")
        self.assertEqual(rows[2]["result"], "+78.4%")
        self.assertEqual((rows[0]["a_ref"], rows[0]["b_ref"]), ("disc:1#0", "fin:1"))

    def test_rejects_numbers_not_in_evidence(self):
        rows = compute([calc("div", "4조 3,000억원", "E1", "3조 893억 2,018만 1,000원", "E2"),   # 근거에 없는 값
                        calc("div", "4조 2,087억원", "E2", "3조 893억 2,018만 1,000원", "E2"),   # 다른 근거의 값
                        calc("div", "4조 2,087억원", "E9", "3조 893억 2,018만 1,000원", "E2")], EVIDENCE)   # 없는 근거 번호
        rows += compute([calc("sqrt", "4조 2,087억원", "E1", "3조 893억 2,018만 1,000원", "E2")], EVIDENCE)
        self.assertEqual([(r["ok"], r["reason"]) for r in rows],
                         [(False, "not_in_evidence"), (False, "not_in_evidence"), (False, "evidence_id"), (False, "op")])
        self.assertTrue(all(r["result"] == "" for r in rows))
        self.assertEqual(len(compute([calc("div", "1", "E1", "1", "E1")] * 5, EVIDENCE)), 3)   # 최대 3개

    def test_scaled_units_and_unit_guard(self):
        """'백만원'은 원 단위로 환산해 계산한다 (2026-11-17 N24 "약 0.00배"). 단위가 어긋나 보이면 계산하지 않는다."""
        evs = [ev("E1", "(단위 : 백만원) 기말수주잔고 합계 60,512,857", "disc:2#0"),
               ev("E2", "2025년 연간 매출액 17조 5,806억 3,325만 7,000원", "fin:2")]
        rows = compute([calc("div", "60,512,857백만원", "E1", "17조 5,806억 3,325만 7,000원", "E2")], evs)
        self.assertEqual((rows[0]["ok"], rows[0]["result"]), (True, "약 3.44배"))
        rows = compute([calc("div", "60,512,857원", "E1", "17조 5,806억 3,325만 7,000원", "E2")], evs)   # 단위를 빼먹음
        self.assertEqual((rows[0]["ok"], rows[0]["reason"]), (False, "unit_suspect"))

    def test_parse_card_reads_calc(self):
        raw = ('{"status":"update","headline":"h","when":"2025-12-31","facts":[{"text":"t","evidence_id":"E1"}],'
               '"memo_link":"m","sources":["E1"],"confidence":0.9,'
               '"calc":[{"label":"a ÷ b","op":"div","a":{"value":"1","evidence_id":"E1"},"b":{"value":"2","evidence_id":"E2"}}, "x"]}')
        card = parse_card_v2(raw)
        self.assertEqual(len(card.calc), 1)
        self.assertEqual(parse_card_v2(raw.replace(',"calc":', ',"zz":')).calc, [])     # calc 없으면 빈 목록


if __name__ == "__main__":
    unittest.main()
