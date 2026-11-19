"""분기 표 누적 기간 안내(judge.cumulative_table, M023)와 자사주 취득+소각 묶기(fin_table.event_lines, M027). 2026-11-19."""

import unittest
from datetime import date

from pipelines.updates import fin_table
from pipelines.updates.judge import CUMULATIVE_NOTE, cumulative_table, evidence_block
from pipelines.updates.models import Candidate, Evidence

PRODUCT = ("[셀트리온 2026 3분기 | II. 사업의 내용 > 2. 주요 제품 및 서비스]\n[표] 가. 주요 제품 등의 현황 (연결 기준) / "
           "(기준일: 2026.09.30) / (단위 : 백만원, %)\n사업부문: 바이오의약품 | 품목: CT-P13 바이오시밀러 외 | 매출액: 3,890,800 | 비율: 94.57")
INCOME = ("[셀트리온 2026 3분기 | II. 사업의 내용 > 4. 매출 및 수주상황]\n[표] (단위 : 백만원)\n"
          "열: 제 36 기 3분기 / 3개월 | 제 36 기 3분기 / 누적\n매출액: 1,575,548 | 4,114,227")
NOTES = ("[셀트리온 2026 3분기 | III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 6. 금융위험관리]\n[표] (단위 : 백만원)\n기초: 10 | 기말: 12")


class CumulativeNoteTest(unittest.TestCase):
    def test_business_table_in_quarterly_report_gets_note(self):
        self.assertTrue(cumulative_table("분기보고서 (2026.09)", PRODUCT))
        self.assertTrue(cumulative_table("반기보고서 (2026.06)", PRODUCT))

    def test_no_note_when_columns_say_period_or_other_cases(self):
        self.assertFalse(cumulative_table("분기보고서 (2026.09)", INCOME))      # 3개월·누적 열이 따로 있다
        self.assertFalse(cumulative_table("사업보고서 (2025.12)", PRODUCT))      # 연간 보고서
        self.assertFalse(cumulative_table("분기보고서 (2026.09)", NOTES))        # 주석 표
        self.assertFalse(cumulative_table("분기보고서 (2026.09)", PRODUCT.replace("[표]", "")))   # 표가 아닌 글
        self.assertFalse(cumulative_table("분기보고서 (2026.09)", PRODUCT.replace("(단위 : 백만원, %)", "(단위 : %)")))

    def test_note_in_evidence_block(self):
        c = Candidate(ref="disc:1#7", kind="disclosure", symbol="068270", date="2026-11-16", title="분기보고서 (2026.09)",
                      text=PRODUCT, url=None, source="DART", similarity=0.9, doc="chunk")
        block = evidence_block([Evidence("E1", c, PRODUCT)])
        self.assertIn("- 기간 안내: " + CUMULATIVE_NOTE, block)
        self.assertLess(block.index("기간 안내"), block.index("원문 발췌"))


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        rows = [("x",)] if "to_regclass" in sql else self.rows
        return type("R", (), {"fetchall": lambda _s: rows, "fetchone": lambda _s: rows[0]})()


BUY = ("treasury_buy", date(2026, 10, 27), {"amount_krw": 450_000_000_000, "amount_to_market_cap_pct": 1.12,
                                            "shares_pct": 1.12}, {})
CANCEL = ("share_cancel", date(2026, 10, 27), {"amount_krw": 450_000_000_000, "cancel_pct": 1.12,
                                               "amount_to_market_cap_pct": 1.12}, {})


class TreasuryCancelTest(unittest.TestCase):
    def test_same_day_same_amount_is_one_line(self):
        lines = fin_table.event_lines(FakeConn([BUY, CANCEL]), "055550")
        self.assertEqual(len(lines), 1)
        self.assertIn("자사주 취득", lines[0])
        self.assertIn("같은 날 같은 금액의 주식 소각 결정도 공시 · 발행주식 대비 소각 비율 1.1%", lines[0])

    def test_different_amount_or_day_stays_separate(self):
        other = ("share_cancel", date(2026, 10, 27), {"amount_krw": 100_000_000_000, "cancel_pct": 0.3}, {})
        self.assertEqual(len(fin_table.event_lines(FakeConn([BUY, other]), "X")), 2)
        later = ("share_cancel", date(2026, 12, 1), CANCEL[2], {})
        lines = fin_table.event_lines(FakeConn([BUY, later]), "X")
        self.assertEqual(len(lines), 2)
        self.assertNotIn("같은 날", lines[0])


if __name__ == "__main__":
    unittest.main()
