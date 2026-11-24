"""재무 표 배당 지표 줄 (fin_table.dividend_lines, 2026-11-19 M009 "현대차 배당성향이 어느 정도야?")."""

import unittest
from datetime import date

from pipelines.updates import fin_table
from pipelines.updates.fin_table import _div_row, dividend_lines

TABLE = """[표] 라. 최근 3사업연도 배당에 관한 사항 / ※ 주요배당지표
열: 구 분 | 주식의 종류 | 당기 / 제59기 3분기 | 전기 / 제58기 | 전전기 / 제57기
구 분: (연결)당기순이익(백만원) | 당기 / 제59기 3분기: 9,000,000 | 전기 / 제58기: 13,000,000 | 전전기 / 제57기: 12,000,000
구 분: (연결)현금배당성향(%) | 당기 / 제59기 3분기: 30.0 | 전기 / 제58기: 27.7 | 전전기 / 제57기: 25.1
구 분: 현금배당수익률(%) | 주식의 종류: 보통주 | 당기 / 제59기 3분기: 2.5 | 전기 / 제58기: 1.9 | 전전기 / 제57기: 5.9
구 분: 현금배당수익률(%) | 주식의 종류: 우선주 | 당기 / 제59기 3분기: 4.7 | 전기 / 제58기: 3.5 | 전전기 / 제57기: 7.3
구 분: 주당 현금배당금(원) | 주식의 종류: 보통주 | 당기 / 제59기 3분기: 7,500 | 전기 / 제58기: 10,000 | 전전기 / 제57기: 12,000
구 분: 주당 현금배당금(원) | 주식의 종류: 우선주 | 당기 / 제59기 3분기: 7,550 | 전기 / 제58기: 10,050 | 전전기 / 제57기: 12,050"""


class FakeConn:
    def __init__(self, chunks, kind="quarterly", end=date(2026, 9, 30), fy_end=date(2025, 12, 31)):
        self.chunks, self.kind, self.end, self.fy_end = chunks, kind, end, fy_end
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if sql == fin_table.DIVIDEND_SQL:
            rows = [("분기보고서 (2026.09)", self.kind, self.end, c) for c in self.chunks]
        elif sql == fin_table.FY_SQL:
            rows = [(self.fy_end,)] if self.fy_end else []
        elif "to_regclass" in sql:
            rows = [(None,)]                                # 0017·0018 표 없는 DB로 친다
        else:
            rows = []
        return type("R", (), {"fetchall": lambda _s: rows, "fetchone": lambda _s: rows[0] if rows else None})()


class DividendLinesTest(unittest.TestCase):
    def test_reads_payout_dps_and_yield_with_periods(self):
        line = dividend_lines(FakeConn([TABLE]), "005380")[0]
        self.assertIn("현금배당성향(연결): 2026년 3분기까지 누적 30.0% · 2025년 연간 27.7% · 2024년 연간 25.1%", line)
        self.assertIn("보통주 주당 현금배당금: 2026년 3분기까지 누적 7,500원 · 2025년 연간 10,000원", line)
        self.assertIn("보통주 현금배당수익률: 2026년 3분기까지 누적 2.5%", line)
        self.assertNotIn("7,550", line)                     # 우선주 줄은 쓰지 않는다
        self.assertNotIn("4.7%", line)

    def test_table_split_across_chunks(self):
        head, tail = TABLE.split("구 분: (연결)현금배당성향", 1)
        line = dividend_lines(FakeConn([head, "구 분: (연결)현금배당성향" + tail]), "005380")[0]
        self.assertIn("27.7%", line)

    def test_annual_report_and_non_december_fiscal_year(self):
        line = dividend_lines(FakeConn([TABLE], kind="annual", end=date(2025, 12, 31)), "X")[0]
        self.assertIn("2025년 연간 30.0% · 2024년 연간 27.7% · 2023년 연간 25.1%", line)
        line = dividend_lines(FakeConn([TABLE], fy_end=date(2026, 3, 31)), "X")[0]
        self.assertIn("이번 사업연도 누적 30.0% · 직전 사업연도 27.7% · 전전 사업연도 25.1%", line)

    def test_separate_only_and_dashes(self):
        table = TABLE.replace("(연결)현금배당성향", "(별도)현금배당성향").replace(
            "주당 현금배당금(원) | 주식의 종류: 보통주 | 당기 / 제59기 3분기: 7,500 | 전기 / 제58기: 10,000 | 전전기 / 제57기: 12,000",
            "주당 현금배당금(원) | 주식의 종류: 보통주 | 당기 / 제59기 3분기: - | 전기 / 제58기: - | 전전기 / 제57기: -")
        line = dividend_lines(FakeConn([table]), "X")[0]
        self.assertIn("현금배당성향(별도): 2026년 3분기까지 누적 30.0%", line)
        self.assertNotIn("주당 현금배당금", line)          # 세 칸이 다 '-'면 줄을 뺀다

    def test_odd_shape_is_dropped(self):
        self.assertIsNone(_div_row("구 분: (연결)현금배당성향(%) | 당기 / 제59기 3분기: 30.0", "(연결)현금배당성향(%)", None))
        self.assertEqual(dividend_lines(FakeConn([]), "X"), [])
        self.assertEqual(dividend_lines(FakeConn(["배당 정책 문단만 있고 표는 없음"]), "X"), [])

    def test_only_for_dividend_questions(self):
        conn = FakeConn([TABLE])
        fin_table.company_table(conn, "005380", "현대차", question="영업이익률 얼마야?")
        self.assertNotIn(fin_table.DIVIDEND_SQL, conn.sql)
        conn = FakeConn([TABLE])
        fin_table.company_table(conn, "005380", "현대차", question="배당성향이 어느 정도야?")
        self.assertIn(fin_table.DIVIDEND_SQL, conn.sql)


if __name__ == "__main__":
    unittest.main()
