"""금융사 비율(BIS·K-ICS·NCR) 추출 — 실제 정기보고서 청크를 줄인 조각 (DB 없음)."""

import unittest
from decimal import Decimal

from pipelines.disclosures import financials_ratios as fr
from pipelines.disclosures import run_financial_ratios as rr

S5 = "II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항"
NOTE = "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 44. 위험관리 (연결)"

# 구조화 표, 제N기 열 (삼성화재 2026 반기)
KICS_TERM = (
    "[표] 나. 지급여력비율 (단위 : 억원, %) 열: 구 분 | 제77기 반기 | 제76기 | 제75기 "
    "구 분: 지급여력금액(A) | 제77기 반기: 439,879 | 제76기: 293,000 | 제75기: 241,639 "
    "구 분: 지급여력비율(A/B) | 제77기 반기: 282.78 | 제76기: 262.87 | 제75기: 264.46 [표] 註) 지급여력비율은 …"
)
# 평문 표: 열 머리와 값 셀이 따로 (삼성생명 2026 1분기)
KICS_FLAT = (
    "[표] 마. 지급여력비율 (단위 : 백만원, %) 구 분 | 제 71 기 1분기(FY2026 1Q) | 제 70 기(FY2025) | 제 69 기(FY2024) "
    "지급여력(A) | 82,425,850 | 65,740,178 | 44,336,081 지급여력기준(B) | 39,264,356 | 33,207,526 | 23,980,612 "
    "지급여력비율(A/B) | 209.9 | 198.0 | 184.9"
)
# 연결 표 다음 지배회사 표, 값에 쉼표와 % (키움증권 2025 사업보고서)
NCR_TWO_TABLES = (
    "[표] [연결회사에 관한 사항] / 가. 자본적정성 관련 지표 (1) 순자본비율 (단위 : 백만원) 열: 구 분 | 제27기 | 제26기 | 제25기 "
    "구 분: 영업용순자본(A) | 제27기: 4,676,809 | 제26기: 3,511,468 | 제25기: 3,138,396 "
    "구 분: 순자본비율[(A-B)/C] | 제27기: 1,549.25% | 제26기: 1,301.64% | 제25기: 1,272.31% [표] 주) … "
    "/ [지배회사에 관한 사항]■ 키움증권(주) / 가. 자본적정성 관련 지표 (1) 순자본비율 (단위 : 백만원) 열: 구 분 | 제27기 | 제26기 | 제25기 "
    "구 분: 순자본비율[(A-B)/C] | 제27기: 1,355.12% | 제26기: 1,003.45% | 제25기: 1,013.29%"
)
# 열 머리가 기간이 아님 — 제목의 기준일을 본다 (현대차증권 2026 반기)
NCR_SINGLE = (
    "[표] 가. 순자본비율 / (기준일 : 2026.06.30) (단위 : 백만원, %) 구 분 | 금액(비율) 1. 영업용순자본 | 1,304,340 "
    "2. 총위험액 | 563,103 3. 잉여자본 (1-2) | 741,237 순자본비율(=(3/5)*100) | 579.43 [표] ※ 상기 순자본비율은 …"
)
# 지주 연결 표 + 자회사 목록 표의 셀 값 (신한지주 2026 반기)
BIS_HOLDING = (
    "[표] 가. 자본적정성 현황(1) 그룹 BIS기준 자기자본비율 / 연결기준 (단위 : 십억원) 열: 구 분 | 2026년 6월 말 | 2025년 말 | 2024년 말 "
    "구 분: 자기자본(A) | 2026년 6월 말: 55,546.3 | 2025년 말: 55,612.0 | 2024년 말: 53,903.4 "
    "구 분: BIS기준 자기자본비율(A/B) | 2026년 6월 말: 15.74% | 2025년 말: 15.94% | 2024년 말: 15.74% [표] 주) | Basel Ⅲ 기준임"
)
BIS_SUBSIDIARIES = (
    "[표] (2) 주요 자회사 열: 구 분 | 지표명 | 2026년 6월 말 | 2025년 말 | 2024년 말 "
    "구 분: 신한은행 | 지표명: BIS기준 자기자본비율 | 2026년 6월 말: 17.7 | 2025년 말: 17.4 | 2024년 말: 17.6"
)
# 은행 표, 분기 잠정치 주석 (제주은행 2025 1분기)
BIS_BANK_Q1 = (
    "[표] 가. BIS 비율 (단위 : 백만원, %) 열: 구 분 | 제66기 1분기 | 제65기 | 제64기 "
    "구 분: 위험가중자산(B) | 제66기 1분기: 3,218,269 | 제65기: 3,155,224 | 제64기: 2,928,892 "
    "구 분: BIS기준 총 자기자본비율 | 제66기 1분기: 17.49 | 제65기: 17.63 | 제64기: 17.51  [표] (주1) 바젤 Ⅲ 기준임(주2) 제66기 1분기말 현황은 잠정치임"
)
# 재무제표 주석의 소수 표기 (기업은행 2025 사업보고서)
BIS_NOTE = "총자본비율 | 공시금액: 0.1478 총자본비율 | 보통주자본비율 | 공시금액: 0.1148"


def extract(column, chunks, period_end, period_type):
    return fr.extract_ratio(column, [(i, sec, t) for i, sec, t in chunks], period_end, period_type)


class LabelTest(unittest.TestCase):
    def test_classify(self):
        cases = {
            "제77기 반기": ("half", None, 77), "제76기": ("annual", None, 76), "제 71 기 1분기(FY2026 1Q)": ("q1", 2026, 71),
            "FY2025 1분기": ("q1", 2025, None), "2025년 말": ("annual", 2025, None), "'26년2분기말": ("half", 2026, None),
            "제60(당)기 2분기 말": ("half", None, 60), "2026년 상반기": ("half", 2026, None), "제82기 상반기": ("half", None, 82),
        }
        for label, (kind, year, term) in cases.items():
            parsed = fr.classify_label(label)
            self.assertEqual((parsed.kind, parsed.year, parsed.term), (kind, year, term), label)
        month = fr.classify_label("2026년 6월 말")
        self.assertEqual((month.kind, month.year, month.month), ("month", 2026, 6))
        self.assertEqual((fr.classify_label("2026.06").kind, fr.classify_label("2026.06").month), ("month", 6))
        self.assertIsNone(fr.classify_label("금액(비율)"))

    def test_is_current(self):
        self.assertTrue(fr.is_current(fr.classify_label("2026년 6월 말"), "2026-06-30", "half"))
        self.assertFalse(fr.is_current(fr.classify_label("2025년 말"), "2026-06-30", "half"))
        self.assertFalse(fr.is_current(fr.classify_label("제76기"), "2026-06-30", "half"))
        # 3월 결산(신영증권): 2026-06-30은 1분기, FY 표기는 1년 차이를 허용
        self.assertTrue(fr.is_current(fr.classify_label("제 73 기 1분기(연결기준)"), "2026-06-30", "q1"))

    def test_parse_number(self):
        self.assertEqual(fr.parse_number("1,912.64%"), Decimal("1912.64"))
        self.assertEqual(fr.parse_number("13,65"), Decimal("13.65"))  # 소수점 자리에 쉼표 (BNK 2026 반기)
        self.assertEqual(fr.parse_number("835"), Decimal("835"))


class ExtractTest(unittest.TestCase):
    def test_term_columns_current_only(self):
        result = extract("kics_ratio", [(104, S5, KICS_TERM)], "2026-06-30", "half")
        self.assertEqual(result.value, Decimal("282.78"))
        self.assertEqual(result.source["column"], "제77기 반기")
        # 2025 사업보고서 기간으로 이 표를 보면 첫 열이 당기가 아니라 쓰지 않는다
        self.assertIsNone(extract("kics_ratio", [(104, S5, KICS_TERM)], "2025-12-31", "annual").value)

    def test_flat_table_header(self):
        result = extract("kics_ratio", [(156, S5, KICS_FLAT)], "2026-03-31", "q1")
        self.assertEqual(result.value, Decimal("209.90"))
        self.assertIn("1분기", result.source["column"])

    def test_first_table_is_consolidated(self):
        result = extract("ncr_ratio", [(200, S5, NCR_TWO_TABLES)], "2025-12-31", "annual")
        self.assertEqual(result.value, Decimal("1549.25"))
        self.assertEqual(result.source["alternatives"], ["#200 순자본비율[(A-B)/C] 제27기=1355.12"])

    def test_title_date_when_header_is_not_period(self):
        result = extract("ncr_ratio", [(62, S5, NCR_SINGLE)], "2026-06-30", "half")
        self.assertEqual(result.value, Decimal("579.43"))
        self.assertEqual(result.source["column"], "기준일 2026.06")

    def test_subsidiary_cell_is_not_a_row(self):
        result = extract("bis_ratio", [(421, S5, BIS_HOLDING), (422, S5, BIS_SUBSIDIARIES)], "2026-06-30", "half")
        self.assertEqual(result.value, Decimal("15.74"))
        self.assertEqual(result.source["alternatives"], [])  # 신한은행 17.7은 `지표명:` 셀 값이라 후보가 아님
        self.assertIsNone(extract("bis_ratio", [(422, S5, BIS_SUBSIDIARIES)], "2026-06-30", "half").value)

    def test_provisional_flag(self):
        result = extract("bis_ratio", [(50, S5, BIS_BANK_Q1)], "2025-03-31", "q1")
        self.assertEqual(result.value, Decimal("17.49"))
        self.assertTrue(result.source["provisional"])
        self.assertFalse(extract("kics_ratio", [(156, S5, KICS_FLAT)], "2026-03-31", "q1").source["provisional"])

    def test_notes_and_correction_chunks_are_ignored(self):
        self.assertIsNone(extract("bis_ratio", [(1749, NOTE, BIS_NOTE)], "2025-12-31", "annual").value)
        corrected = "[정정전] " + KICS_TERM.replace("282.78", "250.00")
        result = extract("kics_ratio", [(0, "(본문)", corrected), (104, S5, KICS_TERM)], "2026-06-30", "half")
        self.assertEqual(result.value, Decimal("282.78"))

    def test_regulation_text_and_compound_names(self):
        rule = "- 보통주자본비율 4.5% 이상 - 기본자기자본비율 6.0% 이상 - 총자본비율 8.0% 이상"
        self.assertIsNone(extract("bis_ratio", [(144, S5, rule)], "2025-12-31", "annual").value)
        base = KICS_TERM.replace("구 분: 지급여력비율(A/B)", "구 분: 기본자본 지급여력비율")
        self.assertIsNone(extract("kics_ratio", [(1, S5, base)], "2026-06-30", "half").value)
        transitional = KICS_TERM + " 구 분: - 경과조치 前 기준 지급여력비율 | 제77기 반기: 129.68 | 제76기: 126.06"
        self.assertEqual(extract("kics_ratio", [(1, S5, transitional)], "2026-06-30", "half").value, Decimal("282.78"))

    def test_section_priority(self):
        summary = "IV. 이사의 경영진단 및 분석의견 > 2. 개요"
        other = KICS_TERM.replace("282.78", "282.70")
        result = extract("kics_ratio", [(10, summary, other), (104, S5, KICS_TERM)], "2026-06-30", "half")
        self.assertEqual(result.value, Decimal("282.78"))

    def test_out_of_range_needs_review(self):
        result = extract("bis_ratio", [(1, S5, BIS_HOLDING.replace("15.74%", "157.4%", 1))], "2026-06-30", "half")
        self.assertIsNone(result.value)
        self.assertEqual(result.null_code, "needs_review")

    def test_corroborated_by_prose(self):
        prose = (5, "II. 사업의 내용 > 2. 영업의 현황", "지급여력비율(K-ICS 기준)은 2026년 6월말 기준 282.78%(연결기준)")
        self.assertTrue(extract("kics_ratio", [prose, (104, S5, KICS_TERM)], "2026-06-30", "half").source["corroborated"])
        self.assertFalse(extract("kics_ratio", [(104, S5, KICS_TERM)], "2026-06-30", "half").source["corroborated"])


class TargetTest(unittest.TestCase):
    def test_target_column(self):
        self.assertEqual(fr.target_column("000810", "insurance"), "kics_ratio")
        self.assertEqual(fr.target_column("055550", "holding"), "bis_ratio")
        self.assertIsNone(fr.target_column("071050", "holding"))  # 한국금융지주
        self.assertIsNone(fr.target_column("029780", "other"))


class FakeResult:
    rowcount = 1

    def __init__(self, rows):
        self.rows = rows

    def scalar(self):
        return self.rows[0][0] if self.rows else None

    def all(self):
        return self.rows


class FakeConn:
    def __init__(self, state):
        self.state = state

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM disclosures" in sql:
            return FakeResult([(self.state["rcept_no"],)] if self.state["rcept_no"] else [])
        if "FROM disclosure_chunks" in sql:
            return FakeResult(self.state["chunks"])
        if sql.startswith("UPDATE financials_fin"):
            self.state["updates"].append((params["c"], params["v"], params["code"]))
            return FakeResult([])
        raise AssertionError(sql)


def fin_row(fin_type="insurance", **stored):
    row = {"symbol": "000810", "name": "삼성화재", "fin_type": fin_type, "period_end": "2026-06-30", "period_type": "half",
           "bis_ratio": None, "kics_ratio": None, "ncr_ratio": None, "null_reasons": {}}
    row.update(stored)
    return row


class RunnerTest(unittest.TestCase):
    def decide_and_write(self, row, chunks, rcept_no="R1"):
        state = {"rcept_no": rcept_no, "chunks": chunks, "updates": []}
        conn = FakeConn(state)
        decisions = rr.decide(conn, row)
        failures = rr.write_row(conn, row, decisions)
        return decisions, sorted(state["updates"]), failures

    def test_value_and_not_applicable(self):
        decisions, updates, failures = self.decide_and_write(fin_row(), [(104, S5, KICS_TERM)])
        self.assertEqual(decisions["kics_ratio"]["value"], Decimal("282.78"))
        self.assertEqual(updates, [("bis_ratio", None, "not_applicable"), ("kics_ratio", Decimal("282.78"), None),
                                   ("ncr_ratio", None, "not_applicable")])
        self.assertEqual(failures, [])

    def test_failure_keeps_existing_value(self):
        _, updates, failures = self.decide_and_write(fin_row(kics_ratio=Decimal("282.78")), [(1, S5, "지급여력비율 언급만")])
        self.assertNotIn("kics_ratio", [u[0] for u in updates])
        self.assertIn("기존 값 282.78 유지", failures[0])

    def test_missing_report(self):
        decisions, updates, _ = self.decide_and_write(fin_row(), [], rcept_no=None)
        self.assertEqual(decisions["kics_ratio"]["reason"], "정기보고서 본문 미수집")
        self.assertIn(("kics_ratio", None, "extract_failed"), updates)

    def test_unchanged_row_is_not_rewritten(self):
        row = fin_row(kics_ratio=Decimal("282.78"), null_reasons={"bis_ratio": "not_applicable", "ncr_ratio": "not_applicable"})
        _, updates, _ = self.decide_and_write(row, [(104, S5, KICS_TERM)])
        self.assertEqual(updates, [])

    def test_jumps(self):
        def item(period, value):
            return {"symbol": "a", "name": "a", "period_end": period, "ratios": {"ncr_ratio": {"value": Decimal(value)}}}
        flagged = rr.jumps([item("2026-03-31", "400"), item("2026-06-30", "700"), item("2025-12-31", "390")])
        self.assertEqual([f["period_end"] for f in flagged], ["2026-06-30"])


if __name__ == "__main__":
    unittest.main()
