"""WO-016 의결권 현황·자본금 주석 주식 수 fallback 단위 테스트."""

import unittest

from pipelines.disclosures.financials_shares import parse_capital_issued, parse_capital_note, parse_voting_rights


STRUCTURED = """[표] (기준일 : | 2026년 03월 31일 | ) | (단위 : 주)
구 분: 발행주식총수(A) | 주식의 종류: 보통주 | 주식수: 156,852,638 | 비고: -
구 분: 발행주식총수(A) | 주식의 종류: 종류주 | 주식수: - | 비고: -
구 분: 의결권없는 주식수(B) | 주식의 종류: 보통주 | 주식수: 7,139,909 | 비고: -
구 분: 의결권없는 주식수(B) | 주식의 종류: 종류주 | 주식수: - | 비고: -
구 분: 정관에 의하여 의결권 행사가 배제된 주식수(C) | 주식의 종류: 보통주 | 주식수: - | 비고: -
"""

FLAT = """라. 의결권 현황 (기준일 : 2024년 03월 31일 ) (단위 : 주)
구 분 주식의 종류 주식수 비고 발행주식총수(A) 보통주 403,511,072 - 우선주 - -
의결권없는 주식수(B) 보통주 20,747,247 자기주식 우선주 - -
정관에 의하여 의결권 행사가 배제된 주식수(C) 보통주 - -
"""

CAPITAL = """[표] 주식수에 대한 공시 당분기말
발행주식수(소각주식수 제외)(주) | 보통주: 5,919,637,922 | 우선주: 815,974,664
분기말 유통주식수(주) | 보통주: 5,828,224,765 | 우선주: 802,437,676
[표] 전기말
발행주식수(소각주식수 제외)(주) | 보통주: 9 | 우선주: 9
분기말 유통주식수(주) | 보통주: 8 | 우선주: 8
"""


class VotingRightsTest(unittest.TestCase):
    def test_structured_table(self):
        parsed = parse_voting_rights(STRUCTURED, "2026-03-31")
        self.assertEqual((parsed.counts.issued, parsed.counts.treasury, parsed.counts.outstanding),
                         (156852638, 7139909, 149712729))
        self.assertEqual(parsed.source["a_rows"][0]["count"], "156,852,638")

    def test_kb_flat_table(self):
        parsed = parse_voting_rights(FLAT, "2024-03-31")
        self.assertEqual((parsed.counts.issued, parsed.counts.treasury), (403511072, 20747247))
        self.assertEqual(parsed.source["b_rows"][0]["note"], "자기주식")

    def test_period_mismatch(self):
        parsed = parse_voting_rights(STRUCTURED, "2026-06-30")
        self.assertIsNone(parsed.counts)
        self.assertIn("일치하지 않음", parsed.reason)

    def test_date_header_may_be_in_adjacent_chunk_context(self):
        header = "라. 의결권 현황 (기준일 : | 2026년 03월 31일 | )"
        table_without_date = STRUCTURED.splitlines()[1:]
        parsed = parse_voting_rights(header + "\n" + "\n".join(table_without_date), "2026-03-31")
        self.assertEqual(parsed.counts.outstanding, 149712729)

    def test_non_treasury_b_note_is_rejected(self):
        text = STRUCTURED.replace("7,139,909 | 비고: -", "7,139,909 | 비고: 상호주")
        parsed = parse_voting_rights(text, "2026-03-31")
        self.assertIsNone(parsed.counts)
        self.assertIn("자기주식 근거가 아님", parsed.reason)


class CapitalNoteTest(unittest.TestCase):
    def test_current_period_only(self):
        parsed = parse_capital_note(CAPITAL, "2025-09-30")
        self.assertEqual((parsed.counts.issued, parsed.counts.treasury, parsed.counts.outstanding),
                         (6735612586, 104950145, 6630662441))

    def test_incomplete_note_is_rejected(self):
        parsed = parse_capital_note(CAPITAL.replace("우선주: 802,437,676", "우선주: -"), "2025-09-30")
        self.assertIsNone(parsed.counts)
        missing = parse_capital_note("발행주식수(주) | 보통주: 10", "2025-09-30")
        self.assertIsNone(missing.counts)

    def test_issued_only_variants_for_cross_check(self):
        samsung = "[표] 주식에 대한 공시 당분기말 소각주식 수를 제외한 발행주식수 | 보통주: 100 | 우선주: 20 [표] 전기말"
        sk = "[표] 주식의 분류에 대한 공시 / 당분기말 보통주 발행주식수 (단위 : 주) | 보통주: 728,002,365 [표] 전기말"
        kb = "14-A. 자본 주식의 분류에 대한 공시 당반기말 보통주 발행할 주식의 총수 1,000,000,000 1주의 금액 5,000 발행주식수 381,462,103 자본금 1 전기말"
        self.assertEqual(parse_capital_issued(samsung, "2025-03-31"), 120)
        self.assertEqual(parse_capital_issued(sk, "2024-03-31"), 728002365)
        self.assertEqual(parse_capital_issued(kb, "2025-06-30"), 381462103)


if __name__ == "__main__":
    unittest.main()
