"""WO-015 ③단계: KB금융 BIS 총자본비율 추출과 재무 검증 (DB·API 없음)."""

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pipelines.disclosures import financials_bis as fb
from pipelines.disclosures import financials_validate as fv
from pipelines.disclosures.financials import ShareCounts


HOLDING_STRUCTURED = """[KB금융 2025 사업보고서 | II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항]
[표] [지배회사에 관한 사항] / [KB금융지주] / (1) 자본적정성 관련 지표
1) BIS기준 자기자본비율 (단위: 십억원, %, %p)
열: 구분 | 2025년 | 2024년 | 2023년
구분: 자기자본(a=b+e) | 2025년: 57,846 | 2024년: 56,849 | 2023년: 53,744
구분: 총자본비율(a/f) | 2025년: 16.20 | 2024년: 16.43 | 2023년: 16.73
구분: 기본자본비율(b/f) | 2025년: 15.21 | 2024년: 15.17 | 2023년: 15.37
"""

BANK_STRUCTURED = """[표] [KB국민은행] / (1) 자본적정성 관련 지표 / 1) BIS기준 자기자본비율
(단위 : 억원, %)
열: 구분 | 2025년 | 2024년 | 2023년
구분: 총자본비율(A/B) | 2025년: 17.28 | 2024년: 17.31 | 2023년: 18.08
"""

FLAT = (
    "[지배회사에 관한 사항] (1) 자본적정성 관련 지표 1) BIS기 준 자기자본비율 (단위: 십억원, %, %p) "
    "구분 2024년 1분기 2023년 2022년 자기자본(a=b+e) 55,189 53,744 48,970 위험가중자산(f) 333,754 321,319 302,984 "
    "총자본비율(a/f) 16.54 16.73 16.16 기본자본비율(b/f) 15.24 15.37 14.86 주1) Basel Ⅲ 기준 주2) 2024년 1분기는 잠정 수 치임 "
    "[주요 종속회사에 관한 사항] [KB국민은행] (1) 자본적정성 관련 지표 1) BIS기준 자기자본비율 (단위 : 억원, %) "
    "구분 2024년 1분기 2023년 2022년 총 자기자본(A) 393,942 390,399 362,330 총자본비율(A/B) 17.31 18.08 17.46"
)


class BisExtractTest(unittest.TestCase):
    def test_structured_holding_current_column(self):
        result = fb.extract_total_capital_ratio([(475, "II", HOLDING_STRUCTURED + "\n" + BANK_STRUCTURED)], "2025-12-31")
        self.assertEqual(result.value, Decimal("16.20"))
        self.assertEqual(result.source["column"], "2025년")
        self.assertEqual(result.source["entity_marker"], "KB금융지주")  # 표 바로 앞의 주체 표시
        self.assertFalse(result.source["provisional"])

    def test_prior_column_is_not_used_for_other_period(self):
        # 2025 사업보고서 표에는 2024년 열(16.43)이 있지만 2024-06-30 대상 열(2024년 반기)은 없다
        self.assertIsNone(fb.extract_total_capital_ratio([(1, "II", HOLDING_STRUCTURED)], "2024-06-30").value)
        self.assertEqual(fb.extract_total_capital_ratio([(1, "II", HOLDING_STRUCTURED)], "2024-12-31").value, Decimal("16.43"))

    def test_bank_only_table_is_not_used(self):
        result = fb.extract_total_capital_ratio([(415, "II", BANK_STRUCTURED)], "2025-12-31")
        self.assertIsNone(result.value)
        self.assertIn("지주 표 아님 (주체 KB국민은행)", " ".join(result.source["skipped"]))

    def test_flat_format_holding_and_bank_in_one_chunk(self):
        result = fb.extract_total_capital_ratio([(354, "II", FLAT)], "2024-03-31")
        self.assertEqual(result.value, Decimal("16.54"))  # 국민은행 17.31이 아님
        self.assertEqual(result.source["column"], "2024년1분기")
        self.assertTrue(result.source["provisional"])

    def test_correction_comparison_chunk_is_excluded(self):
        corrected = "주1)<정정 전> *해당 부분 발췌\n" + HOLDING_STRUCTURED.replace("16.20", "16.99")
        result = fb.extract_total_capital_ratio([(1, "(본문)", corrected), (475, "II", HOLDING_STRUCTURED)], "2025-12-31")
        self.assertEqual(result.value, Decimal("16.20"))
        self.assertIsNone(fb.extract_total_capital_ratio([(1, "(본문)", corrected)], "2025-12-31").value)

    def test_conflicting_candidates_are_ambiguous(self):
        other = HOLDING_STRUCTURED.replace("16.20", "16.30")
        result = fb.extract_total_capital_ratio([(1, "II", HOLDING_STRUCTURED), (2, "II", other)], "2025-12-31")
        self.assertIsNone(result.value)
        self.assertIn("모호", result.reason)
        same = fb.extract_total_capital_ratio([(1, "II", HOLDING_STRUCTURED), (2, "II", HOLDING_STRUCTURED)], "2025-12-31")
        self.assertEqual(same.source["chunk_indexes"], [1, 2])

    def test_table_without_bis_title_or_entity_is_ignored(self):
        no_title = HOLDING_STRUCTURED.replace("BIS기준 ", "")
        self.assertIsNone(fb.extract_total_capital_ratio([(1, "II", no_title)], "2025-12-31").value)
        no_entity = "\n".join(line for line in HOLDING_STRUCTURED.splitlines() if "지배회사" not in line)
        self.assertIsNone(fb.extract_total_capital_ratio([(1, "II", no_entity)], "2025-12-31").value)
        self.assertIn("찾지 못함", fb.extract_total_capital_ratio([(1, "II", "총자본비율 언급만")], "2025-12-31").reason)

    def test_flat_header_from_other_table_is_not_paired(self):
        # 앞 표(유동성비율)의 머리만 있고 BIS 표에는 머리가 없는 경우 — 엉뚱한 열 머리와 짝짓지 않는다
        text = ("[지배회사에 관한 사항] 유동성비율 구분 2025년 1분기 2024년 2023년 원화유동성비율 1 2 3 "
                "1) BIS기준 자기자본비율 (단위: %) 총자본비율(a/f) 16.20 16.43 16.73")
        self.assertIsNone(fb.extract_total_capital_ratio([(1, "II", text)], "2025-03-31").value)

    def test_provisional_flag_is_scoped_to_the_table(self):
        next_table = HOLDING_STRUCTURED + "\n[표] (2) 재무건전성 관련 지표 주) 2025년은 잠정\n"
        self.assertFalse(fb.extract_total_capital_ratio([(1, "II", next_table)], "2025-12-31").source["provisional"])
        title_note = HOLDING_STRUCTURED.replace("1) BIS기준 자기자본비율", "1) BIS기준 자기자본비율 (잠정)")
        self.assertTrue(fb.extract_total_capital_ratio([(1, "II", title_note)], "2025-12-31").source["provisional"])

    def test_target_labels(self):
        self.assertEqual(fb.target_labels("2026-06-30"), {"2026년반기", "2026년반기말", "2026년상반기", "2026년상반기말", "2026년2분기", "2026년2분기말"})
        self.assertNotIn("2025년1분기", fb.target_labels("2025-12-31"))


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalar(self):
        return self.rows[0][0] if self.rows else None

    def all(self):
        return self.rows


class FakeConn:
    """bis 단계가 쓰는 SQL 네 가지만 흉내 낸다 (공시 접수번호, 청크, 저장된 비율, UPDATE)."""

    def __init__(self, state):
        self.state = state

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM disclosures" in sql:
            return FakeResult([("R1",)])
        if "FROM disclosure_chunks" in sql:
            return FakeResult(self.state["chunks"])
        if sql.startswith("SELECT solvency_ratio"):
            return FakeResult([(self.state["stored"],)])
        if sql.startswith("UPDATE"):
            self.state["stored"] = params["v"]
            return FakeResult([])
        raise AssertionError(sql)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def __init__(self, state):
        self.state = state

    def connect(self):
        return FakeConn(self.state)

    begin = connect


class BisStepTest(unittest.TestCase):
    def run_bis(self, chunks, stored):
        from pipelines.common.config import REPO_ROOT
        from pipelines.disclosures import financials_pipeline as fp

        state = {"chunks": chunks, "stored": stored}
        with tempfile.TemporaryDirectory() as tmp:
            config = {"targets": {"periods": ["2025-12-31"]},
                      "paths": {"logs_dir": "logs", "financials_raw_dir": "f", "shares_raw_dir": "s", "financials_dir": "out"}}
            args = fp.build_arg_parser().parse_args(["--symbols", "105560", "--root", tmp, "--mapping", str(REPO_ROOT / "configs" / "financials_mapping.yaml")])
            run = fp.Run(args, config, engine=FakeEngine(state))
            run.bis()
        return state["stored"], run.failures

    def test_success_updates_value(self):
        stored, failures = self.run_bis([(475, "II", HOLDING_STRUCTURED)], None)
        self.assertEqual((stored, failures), (Decimal("16.20"), []))

    def test_failed_extraction_keeps_existing_value(self):
        stored, failures = self.run_bis([(1, "II", "총자본비율 언급만")], Decimal("16.20"))
        self.assertEqual(stored, Decimal("16.20"))
        self.assertIn("기존 값 16.20 유지", failures[0])

    def test_failed_extraction_without_existing_value_stays_null(self):
        stored, failures = self.run_bis([(1, "II", "총자본비율 언급만")], None)
        self.assertEqual((stored, failures), (None, []))


def fin_row(period_end, ptype, revenue=None, assets=None, liabilities=None, equity=None, eps=None, net_income=None):
    return {"period_type": ptype, "revenue": revenue, "total_assets": assets, "total_liabilities": liabilities,
            "total_equity": equity, "eps": eps, "net_income": net_income}


class ValidateChecksTest(unittest.TestCase):
    def test_accounting_identity(self):
        rows = {("a", "2025-12-31"): fin_row("2025-12-31", "annual", assets=Decimal(10), liabilities=Decimal(4), equity=Decimal(6)),
                ("a", "2025-09-30"): fin_row("2025-09-30", "q3", assets=Decimal(10), liabilities=Decimal(4), equity=Decimal(5)),
                ("a", "2025-06-30"): fin_row("2025-06-30", "half", assets=Decimal(10))}
        check = fv.check_accounting_identity(rows)
        self.assertFalse(check["ok"])
        self.assertEqual([v["row"][1] for v in check["detail"]["violations"]], ["2025-06-30", "2025-09-30"])

    def test_cumulative_monotonic(self):
        rows = {("a", "2025-03-31"): fin_row("", "q1", revenue=Decimal(5)), ("a", "2025-06-30"): fin_row("", "half", revenue=Decimal(4)),
                ("a", "2025-12-31"): fin_row("", "annual", revenue=Decimal(20)), ("a", "2026-03-31"): fin_row("", "q1", revenue=Decimal(1)),
                ("kb", "2025-03-31"): fin_row("", "q1", revenue=None)}
        check = fv.check_cumulative_monotonic(rows, ["a"])
        self.assertFalse(check["ok"])
        self.assertEqual(check["detail"]["violations"][0]["earlier"][0], "2025-03-31")  # 연도가 바뀌면(2026 q1) 비교하지 않음
        self.assertEqual(len(check["detail"]["violations"]), 1)

    def test_row_counts(self):
        check = fv.check_row_counts({("a", "p1"): {}}, {}, ["a", "b"], ["b"], ["p1"])
        self.assertFalse(check["ok"])
        self.assertEqual(check["detail"]["missing"], [("b", "p1")])
        self.assertEqual(check["detail"]["missing_fin"], [("b", "p1")])
        extra = fv.check_row_counts({("a", "p1"): {}, ("a", "p9"): {}}, {}, ["a"], [], ["p1"])
        self.assertEqual((extra["ok"], extra["detail"]["extra"]), (False, [("a", "p9")]))

    def test_statement_values(self):
        chunk = ("[표] 제 18 기 2025.01.01 부터 2025.12.31 까지 / 제 17 기 2024.01.01 부터 2024.12.31 까지\n(단위 : 백만원)\n"
                 "열: 제 18 기 | 제 17 기\n매출액 (주4,24) | 제 18 기: 97,146,675 | 제 17 기: 66,192,960\n"
                 "신용손실충당금 반영전 영업이익 | 제 18 기: 10,880,589 | 제 17 기: 1\n영업이익(손실) | 제 18 기: (7,730) | 제 17 기: 2\n")
        values = fv.statement_values(chunk, "2025-12-31")
        self.assertEqual(values["매출액"], (Decimal("97146675"), 10**6))
        self.assertEqual(values["영업이익(손실)"], (Decimal("-7730"), 10**6))
        self.assertNotIn("영업이익", values)  # '반영전 영업이익'은 영업이익이 아님
        self.assertEqual(fv.statement_values(chunk, "2024-12-31"), {})  # 첫 기수가 대상 기간이 아니면 쓰지 않음

    def test_eps_warning(self):
        rows = {("a", "2025-12-31"): fin_row("", "annual", eps=Decimal("100"), net_income=Decimal("1000")),
                ("b", "2025-12-31"): fin_row("", "annual", eps=Decimal("100"), net_income=Decimal("2000"))}
        shares = {("a", "2025-12-31"): ShareCounts(10, 0, 10, "합계"), ("b", "2025-12-31"): ShareCounts(10, 0, 10, "합계")}
        check = fv.check_eps(rows, shares)
        self.assertEqual(check["severity"], "warning")
        self.assertEqual([w["row"][0] for w in check["detail"]["over_10pct"]], ["b"])

    def test_null_report_uses_provenance_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.jsonl"
            path.write_text(json.dumps({"symbol": "a", "period_end": "p", "table": "financials", "column": "revenue", "reason": "금융지주"}, ensure_ascii=False) + "\n", encoding="utf-8")
            base = {c: Decimal(1) for c in fv.FINANCIALS_VALUES}
            rows = {("a", "p"): {**base, "revenue": None}, ("b", "p"): {**base, "eps": None}}
            check = fv.null_report(rows, {}, path)
            self.assertEqual(check["detail"]["details"]["financials.revenue"], ["a p: 금융지주"])
            self.assertEqual(check["detail"]["unexplained"], ["b p: 사유 기록 없음"])
            self.assertFalse(check["ok"])

    def test_share_issuance_note_cross_check_records_match_mismatch_and_unavailable(self):
        note = ("당분기말 발행주식수(소각주식수 제외)(주) | 보통주: 100 | 우선주: 20\n"
                "분기말 유통주식수(주) | 보통주: 90 | 우선주: 20 [표] 전기말")

        class Conn:
            def execute(self, statement, params=None):
                return FakeResult([(7, note)] if params["r"] != "EMPTY" else [])

        shares = {
            ("ok", "2025-09-30"): ShareCounts(120, 10, 110, "의결권 현황 표"),
            ("bad", "2025-09-30"): ShareCounts(121, 11, 110, "의결권 현황 표"),
            ("none", "2025-09-30"): ShareCounts(120, 10, 110, "의결권 현황 표"),
            ("api", "2025-09-30"): ShareCounts(120, 10, 110, "합계"),
        }
        rcepts = {("ok", "2025-09-30"): "R1", ("bad", "2025-09-30"): "R2", ("none", "2025-09-30"): "EMPTY"}
        check = fv.check_share_issuance_notes(Conn(), shares, rcepts)
        self.assertFalse(check["ok"])
        self.assertEqual([row["row"][0] for row in check["detail"]["matched"]], ["ok"])
        self.assertEqual([row["row"][0] for row in check["detail"]["mismatches"]], ["bad"])
        self.assertEqual([row["row"][0] for row in check["detail"]["unavailable"]], ["none"])


if __name__ == "__main__":
    unittest.main()
