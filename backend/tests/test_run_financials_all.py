"""코스피 전체 재무 실행: 결산월 기간·보고서 코드, 금융 판별, 전기 값, NULL 사유, 적재 (docs/financials-kospi-plan.md)."""

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from decimal import Decimal
from pathlib import Path

from pipelines.disclosures import financials as fm
from pipelines.disclosures import financials_dart as fd
from pipelines.disclosures import financials_loader as fl
from pipelines.disclosures.fin_classify import classify
from pipelines.disclosures.run_all import State
from pipelines.disclosures.run_financials_all import (
    fiscal_basis, fiscal_slots, fy_end_month, null_counts, pick_shares, process_company, unexplained_nulls, write_outputs,
)


MAPPING_PATH = Path(__file__).resolve().parents[2] / "configs" / "financials_mapping.yaml"


def row(sj_div, account_id, amount="", add="", *, prior="", prior_add="", nm=""):
    return {"sj_div": sj_div, "account_id": account_id, "account_nm": nm, "thstrm_amount": amount, "thstrm_add_amount": add,
            "frmtrm_amount": prior, "frmtrm_add_amount": prior_add, "currency": "KRW", "rcept_no": "20250101000001"}


def statement(*rows):
    return {"status": "000", "list": list(rows)}


GENERAL = [
    row("IS", "ifrs-full_Revenue", "300", "900", prior="250", prior_add="700"),
    row("IS", "dart_OperatingIncomeLoss", "30", "90", prior="20", prior_add="60"),
    row("IS", "ifrs-full_ProfitLossAttributableToOwnersOfParent", "20", "60", prior="10", prior_add="40"),
    row("IS", "ifrs-full_BasicEarningsLossPerShare", "2", "6", prior="1", prior_add="4"),
    row("BS", "ifrs-full_Assets", "1000", prior="900"),
    row("BS", "ifrs-full_Liabilities", "400", prior="380"),
    row("BS", "ifrs-full_Equity", "600", prior="520"),
    row("BS", "ifrs-full_EquityAttributableToOwnersOfParent", "500", prior="450"),
]


def shares(issued="100", treasury="0"):
    return {"status": "000", "list": [{"se": "합계", "istc_totqy": issued, "tesstk_co": treasury, "distb_stock_co": issued}]}


class FiscalPeriodTest(unittest.TestCase):
    def test_period_type_follows_fiscal_year_end(self):
        self.assertEqual([fm.period_type(p) for p in ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31")], ["q1", "half", "q3", "annual"])
        self.assertEqual([fm.period_type(p, 3) for p in ("2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31")], ["q1", "half", "q3", "annual"])
        with self.assertRaises(ValueError):
            fm.period_type("2025-05-31", 12)

    def test_march_fiscal_year_report_codes(self):
        # 동원모빌리티(3월 결산) 실제 응답: 2024 11013 = 분기(2024.06), 2024 11014 = (2024.12), 2025 11011 = 사업(2025.03)
        codes = {p: (fd.Target("018500", "c", p, 3).bsns_year, fd.Target("018500", "c", p, 3).reprt_code)
                 for p in ("2024-06-30", "2024-12-31", "2025-03-31")}
        self.assertEqual(codes, {"2024-06-30": ("2024", "11013"), "2024-12-31": ("2024", "11014"), "2025-03-31": ("2025", "11011")})

    def test_fiscal_slots(self):
        dec = fiscal_slots(12, "2024-01-01", "2026-06-30", 10)
        self.assertEqual((dec[0], dec[-1], len(dec)), ("2024-03-31", "2026-06-30", 10))
        self.assertEqual(fiscal_slots(2, "2024-01-01", "2026-06-30", 3), ["2025-11-30", "2026-02-28", "2026-05-31"])
        self.assertEqual(fiscal_slots(12, "2026-01-01", "2026-06-30", 10), ["2026-03-31", "2026-06-30"])  # 범위 밖은 자름

    def test_prior_period_and_fy_end(self):
        self.assertEqual(fm.prior_period_end("2024-03-31"), "2023-03-31")
        self.assertEqual(fm.prior_period_end("2025-02-28"), "2024-02-29")
        self.assertEqual(fy_end_month({"acc_mt": "03"}), 3)
        self.assertEqual(fy_end_month({"acc_mt": ""}), 12)


def reports(*items):
    """(kind, 'YYYY.MM', rcept_no) → fiscal_basis 입력."""
    return [(kind, fm.month_end(int(ym[:4]), int(ym[5:7])), rcept) for kind, ym, rcept in items]


class FiscalBasisTest(unittest.TestCase):
    """결산월은 공시 목록 우선 (2026-11-13: acc_mt가 틀린 8곳)."""

    def test_changed_fiscal_year_uses_disclosures(self):
        # MH머트리얼즈(001080): acc_mt 12인데 사업보고서는 2024.06·2025.06·2026.06
        mh = reports(("quarterly", "2024.03", "20240516000239"), ("annual", "2024.06", "20250930000631"),
                     ("quarterly", "2024.09", "20250805000315"), ("half", "2024.12", "20250805000321"),
                     ("annual", "2025.06", "20250918000340"), ("half", "2025.12", "20260219002720"),
                     ("annual", "2026.06", "20260910000496"))
        basis = fiscal_basis({"acc_mt": "12"}, mh)
        self.assertEqual((basis.fy_end_month, basis.cycle, basis.source, basis.excluded), (6, 12, "disclosures", None))
        self.assertIn("acc_mt 12월", basis.note)
        self.assertEqual(basis.rcept_periods["20250805000321"], "2024-12-31")

    def test_june_fiscal_year_report_codes_match_cached_responses(self):
        # 실제 캐시: 2024_11011=제72기(2024.06), 2024_11013=제73기 1분기(2024.09), 2024_11012=반기(2024.12), 2025_11014=3분기(2025.03)
        slots = fiscal_slots(6, "2024-01-01", "2026-06-30", 10)
        self.assertEqual((slots[0], slots[-1], len(slots)), ("2024-03-31", "2026-06-30", 10))
        codes = {p: (fd.Target("001080", "c", p, 6).bsns_year, fd.Target("001080", "c", p, 6).reprt_code)
                 for p in ("2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31")}
        self.assertEqual(codes, {"2024-06-30": ("2024", "11011"), "2024-09-30": ("2024", "11013"),
                                 "2024-12-31": ("2024", "11012"), "2025-03-31": ("2025", "11014")})

    def test_six_month_reit_is_excluded(self):
        # 코람코라이프인프라리츠(357120): 사업보고서 5·11월, 반기 2·8월, acc_mt 11
        reit = reports(("half", "2025.02", "a"), ("annual", "2025.05", "b"), ("half", "2025.08", "c"), ("annual", "2025.11", "d"),
                       ("half", "2026.02", "e"), ("annual", "2026.05", "f"), ("half", "2026.08", "g"))
        basis = fiscal_basis({"acc_mt": "11"}, reit)
        self.assertEqual((basis.fy_end_month, basis.cycle, basis.excluded), (5, 6, "fiscal_cycle_6"))
        # NH올원리츠(400760)처럼 acc_mt와 최근 사업보고서 월이 같아도 6개월 주기면 제외
        same = reports(("annual", "2025.06", "a"), ("half", "2025.09", "b"), ("annual", "2025.12", "c"))
        self.assertEqual(fiscal_basis({"acc_mt": "12"}, same).excluded, "fiscal_cycle_6")

    def test_three_month_reit_is_excluded(self):
        # 대신밸류리츠(0030R0): 사업보고서만 3개월마다
        reit = reports(*[("annual", ym, str(i)) for i, ym in enumerate(["2025.05", "2025.08", "2025.11", "2026.02"])])
        self.assertEqual(fiscal_basis({"acc_mt": "08"}, reit).excluded, "fiscal_cycle_3")

    def test_fallbacks(self):
        self.assertEqual(fiscal_basis({"acc_mt": "12"}, reports(("half", "2025.09", "a"))).fy_end_month, 3)  # 반기 + 6
        empty = fiscal_basis({"acc_mt": "03"}, [])
        self.assertEqual((empty.fy_end_month, empty.source, empty.cycle, empty.note), (3, "acc_mt", 12, ""))
        self.assertEqual(fiscal_basis({"acc_mt": "x"}, []).fy_end_month, 12)
        normal = fiscal_basis({"acc_mt": "12"}, reports(("annual", "2024.12", "a"), ("half", "2025.06", "b"), ("annual", "2025.12", "c")))
        self.assertEqual((normal.fy_end_month, normal.cycle, normal.note), (12, 12, ""))


class PickSharesTest(unittest.TestCase):
    def test_shares_file_for_other_period_is_swapped(self):
        # MH머트리얼즈 실제 캐시: shares 2024_11014 = 2024.09 보고서, 2024_11013 = 2024.03 보고서 (재무 API와 반대)
        basis = fiscal_basis({"acc_mt": "12"}, reports(("quarterly", "2024.03", "R0331"), ("annual", "2024.06", "R0630"),
                                                       ("quarterly", "2024.09", "R0930")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for code, rcept in (("11013", "R0331"), ("11014", "R0930")):
                (root / f"001080_2024_{code}.json").write_text(json.dumps({"status": "000", "list": [{"rcept_no": rcept}]}), encoding="utf-8")
            data, name = pick_shares(root, fd.Target("001080", "c", "2024-03-31", 6), basis)  # q3 → 11014
            self.assertEqual((data["list"][0]["rcept_no"], name), ("R0331", "001080_2024_11013.json"))
            self.assertEqual(pick_shares(root, fd.Target("001080", "c", "2024-09-30", 6), basis)[1], "001080_2024_11014.json")
            self.assertEqual(pick_shares(root, fd.Target("001080", "c", "2024-06-30", 6), basis), (None, None))  # 파일 없음
            (root / "001080_2024_11011.json").write_text(json.dumps({"status": "000", "list": [{"rcept_no": "R0930"}]}), encoding="utf-8")
            self.assertEqual(pick_shares(root, fd.Target("001080", "c", "2024-06-30", 6), basis), (None, None))  # 다른 기간뿐


class ProcessCompanyFiscalTest(unittest.TestCase):
    """process_company: 리츠 제외, 응답 접수번호 기간 교차 검증 (DART·DB 호출 없음)."""

    def ctx(self, root: Path, report_list):
        return SimpleNamespace(
            engine=None, reports_index=lambda: {"999990": report_list}, api_key="k", session=None,
            company_dir=root, statements_dir=root, shares_dir=root, start="2024-01-01", end="2024-12-31", slots=4,
            args=SimpleNamespace(no_prior=True), mapping=None, state_dir=root,
        )

    def test_reit_returns_excluded_without_collecting(self):
        reit = [("annual", "2024-05-31", "a"), ("half", "2024-08-31", "b"), ("annual", "2024-11-30", "c")]
        with tempfile.TemporaryDirectory() as tmp,                 mock.patch.object(fd, "fetch_company", return_value=({"acc_mt": "11", "induty_code": "68112"}, 0)),                 mock.patch.object(fd, "collect") as collect:
            row, review = process_company(self.ctx(Path(tmp), reit), "999990", "c")
        collect.assert_not_called()
        self.assertEqual((row["status"], row["excluded"], row["targets"], row["periods"], review), ("done", "fiscal_cycle_6", [], 0, []))
        self.assertNotIn("fin_type", row)  # classification.csv에 general로 잡히지 않게

    def test_response_for_other_period_is_dropped(self):
        # 결산월을 잘못 알면 2024 11012(반기) 요청에 다른 기간 보고서가 온다 → 그 기간은 버리고 검증 실패로 남긴다
        listing = [("half", "2024-06-30", "20240814000001"), ("quarterly", "2024-09-30", "20241114000001"),
                   ("annual", "2023-12-31", "20240314000001")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "999990_2024_11012_CFS.json"
            path.write_text(json.dumps(statement({**GENERAL[0], "rcept_no": "20241114000001"})), encoding="utf-8")
            with mock.patch.object(fd, "fetch_company", return_value=({"acc_mt": "12"}, 0)),                     mock.patch.object(fd, "collect", return_value=fd.CollectReport()),                     mock.patch.object(fd, "cached_statement",
                                      side_effect=lambda d, t: ("CFS", path) if t.period_end == "2024-06-30" else None):
                row, _ = process_company(self.ctx(root, listing), "999990", "c")
        self.assertEqual(row["status"], "error")
        item = row["failed_items"][0]
        self.assertEqual((item["stage"], item["period_end"]), ("validate", "2024-06-30"))
        self.assertIn("2024-09-30", item["reason"])


class ClassifyTest(unittest.TestCase):
    DEPOSITS = [{"account_id": "ifrs-full_DepositsFromCustomers"}]
    INSURANCE = [{"account_id": "ifrs-full_InsuranceRevenue"}]

    def test_holding_code_needs_financial_accounts(self):
        self.assertIsNone(classify("64992", [{"account_id": "ifrs-full_Revenue"}]).fin_type)  # LG·SK
        self.assertEqual(classify("64992", self.DEPOSITS).fin_type, "holding")  # KB금융
        self.assertEqual(classify("64992", self.INSURANCE).fin_type, "holding")  # 보험 지주
        self.assertIsNone(classify("649", [{"account_id": "ifrs-full_Revenue"}]).fin_type)  # 효성·HDC (3자리 코드)
        self.assertEqual(classify("649", self.DEPOSITS).fin_type, "holding")

    def test_symbol_overrides(self):
        self.assertEqual(classify("661", [], "030210").fin_type, "securities")  # 다올투자증권
        self.assertEqual(classify("661", []).fin_type, "other")  # 고정 없으면 코드 규칙 그대로
        self.assertIsNone(classify("64999", [], "487570").fin_type)  # HS효성
        self.assertIn("종목 고정", classify("64999", [], "487570").basis)

    def test_industry_codes(self):
        self.assertEqual(classify("64121", self.DEPOSITS), classify("64121", self.DEPOSITS))
        self.assertEqual(classify("64121", self.DEPOSITS).fin_type, "bank")
        self.assertIsNone(classify("64121", self.DEPOSITS).review)
        self.assertEqual(classify("65110", self.INSURANCE).fin_type, "insurance")
        self.assertEqual(classify("66121", []).fin_type, "securities")
        self.assertEqual(classify("64911", []).fin_type, "other")
        self.assertIsNone(classify("26110", []).fin_type)

    def test_mismatch_is_flagged_for_review(self):
        self.assertIn("예수부채", classify("64121", []).review)
        self.assertIn("보험수익", classify("65110", []).review)
        flagged = classify("46900", self.DEPOSITS)
        self.assertIsNone(flagged.fin_type)
        self.assertIn("예수부채", flagged.review)


class MapPeriodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = fm.load_mapping(MAPPING_PATH)

    def map(self, rows, period_end="2024-12-31", **kwargs):
        kwargs.setdefault("fin_type", None)
        return fm.map_period("000001", period_end, kwargs.pop("fs_div", "CFS"), statement(*rows), "f.json", shares(), "s.json", self.mapping, **kwargs)

    def test_every_null_has_a_reason(self):
        for kwargs in ({}, {"prior": True}, {"fin_type": "bank"}, {"fin_type": "securities"}):
            period = self.map(GENERAL, **kwargs)
            self.assertEqual(unexplained_nulls(period), [], kwargs)

    def test_annual_prior_uses_frmtrm_amount(self):
        period = self.map(GENERAL, prior=True)
        self.assertEqual((period.period_end, period.period_type, period.prior), ("2023-12-31", "annual", True))
        self.assertEqual((period.values["revenue"], period.values["total_assets"], period.values["eps"]), (Decimal("250"), Decimal("900"), Decimal("1.00")))
        self.assertIsNone(period.values["bps"])
        self.assertEqual(period.null_reasons["bps"], "not_reported")

    def test_quarter_prior_flows_only(self):
        period = self.map(GENERAL, "2024-09-30", prior=True)
        self.assertEqual(period.period_end, "2023-09-30")
        self.assertEqual(period.values["revenue"], Decimal("700"))  # frmtrm_add_amount (전년 누적)
        self.assertIsNone(period.values["total_assets"])  # 분기 frmtrm_amount는 직전 사업연도 말 → 쓰지 않음
        self.assertEqual(period.null_reasons["total_assets"], "not_reported")
        self.assertFalse(any("total_assets" in line for line in period.review))  # 예상된 NULL은 검토 목록에 없음

    def test_securities_revenue_moves_to_fin_column(self):
        period = self.map(GENERAL, fin_type="securities")
        self.assertIsNone(period.values["revenue"])
        self.assertEqual(period.null_reasons["revenue"], "not_applicable")
        self.assertEqual(period.fin_values["securities_operating_revenue"], Decimal("300"))
        self.assertEqual(period.fin_null_reasons["net_interest_income"], "not_applicable")

    def test_general_company_has_no_fin_values(self):
        period = self.map(GENERAL)
        self.assertIsNone(period.fin_values)
        self.assertEqual(period.values["revenue"], Decimal("300"))
        self.assertEqual(period.values["bps"], Decimal("5.00"))

    def test_separate_statement_falls_back_to_total_profit_and_equity(self):
        rows = [r for r in GENERAL if r["account_id"] not in ("ifrs-full_ProfitLossAttributableToOwnersOfParent",
                                                               "ifrs-full_EquityAttributableToOwnersOfParent")]
        rows.append(row("IS", "ifrs-full_ProfitLoss", "25", "75"))
        separate = self.map(rows, fs_div="OFS")
        self.assertEqual((separate.values["net_income"], separate.values["bps"]), (Decimal("25"), Decimal("6.00")))
        consolidated = self.map(rows)
        self.assertIsNone(consolidated.values["net_income"])  # 연결은 지배주주분이 없으면 대체하지 않는다
        self.assertEqual(consolidated.null_reasons["net_income"], "not_reported")

    def test_unmapped_account_name_is_no_standard_id(self):
        rows = [r for r in GENERAL if r["account_id"] != "ifrs-full_BasicEarningsLossPerShare"]
        rows.append(row("IS", fm.NO_STANDARD_ID, "2", "6", nm="기본주당이익"))
        period = self.map(rows)
        self.assertIsNone(period.values["eps"])
        self.assertEqual(period.null_reasons["eps"], "no_standard_id")
        item = next(i for i in period.review_items if i["column"] == "eps")
        self.assertEqual(item["unmapped"], [{"account_nm": "기본주당이익", "sj_div": "IS", "value": "2"}])

    def test_null_counts(self):
        counts = null_counts([self.map(GENERAL), self.map(GENERAL, prior=True)])
        self.assertEqual(counts["financials.bps"], {"not_reported": 1})
        self.assertEqual(counts["financials.inventories"], {"not_reported": 2})


class OutputsTest(unittest.TestCase):
    def test_csv_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = State(root / "state.json")
            state.companies.update({
                "105560": {"status": "done", "fin_type": "holding", "induty_code": "64992", "fy_end_month": 12, "basis": "b",
                           "no_data": [], "failed_items": [], "updated_at": "t"},
                "999990": {"status": "partial", "fin_type": None, "induty_code": "26110", "fy_end_month": 3, "basis": "b",
                           "no_data": ["2026-06-30"], "failed_items": [{"stage": "load", "period_end": "", "reason": "x"}], "updated_at": "t"},
            })
            (root / "review").mkdir()
            (root / "review" / "999990.json").write_text(json.dumps([{
                "period_end": "2025-03-31", "table": "financials", "column": "eps", "null_code": "no_standard_id", "reason": "r",
                "unmapped": [{"account_nm": "주당이익", "value": "5"}], "file": "f.json"}]), encoding="utf-8")
            write_outputs(state, {"105560": "KB금융"}, root)

            def read(name):
                return (root / name).read_text(encoding="utf-8-sig").splitlines()

            self.assertEqual(read("failed.csv")[1].split(",")[:3], ["999990", "", "DB 적재"])
            self.assertEqual(read("classification.csv")[1].split(",")[:5], ["105560", "KB금융", "64992", "12", "holding"])
            self.assertEqual(read("classification.csv")[2].split(",")[4], "general")
            self.assertEqual(read("no_data.csv")[1], "999990,,2026-06-30")
            self.assertIn("주당이익=5", read("review.csv")[1])


def _engine_or_skip():
    try:
        from pipelines.common.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine
    except Exception as exc:  # DB 없음·설정 없음
        raise unittest.SkipTest(f"DB 연결 불가: {type(exc).__name__}")


class LoaderDbTest(unittest.TestCase):
    """실제 DB, 트랜잭션 롤백. 대상 기간 밖(1999년) 날짜만 쓴다."""

    def test_null_reasons_prior_rows_ratio_and_sector(self):
        from sqlalchemy import text

        engine = _engine_or_skip()
        mapping = fm.load_mapping(MAPPING_PATH)
        rows = [{**r, "rcept_no": "19990101000001"} for r in GENERAL]
        direct = fm.map_period("105560", "1999-12-31", "CFS", statement(*rows), "f", shares(), "s", mapping, fin_type="bank")
        prior_rows = [{**r, "frmtrm_amount": "1"} for r in rows]
        # 1999 보고서의 전기 값(1998)과 2000 보고서의 전기 값(1999 = 이미 직접 받은 기간)
        older = fm.map_period("105560", "1999-12-31", "CFS", statement(*prior_rows), "f", None, None, mapping, fin_type="bank", prior=True)
        clash = fm.map_period("105560", "2000-12-31", "CFS", statement(*prior_rows), "f", None, None, mapping, fin_type="bank", prior=True)
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                fl.preflight(conn, ["105560"])
                self.assertTrue(fl.upsert_financials(conn, direct))
                fl.upsert_financials_fin(conn, direct)
                self.assertTrue(fl.upsert_financials(conn, older))
                self.assertFalse(fl.upsert_financials(conn, clash, keep_direct=True))  # 직접 받은 1999년을 덮지 않음
                self.assertFalse(fl.upsert_financials_fin(conn, clash, keep_direct=True))
                self.assertEqual(fl.set_ratio(conn, "105560", "1999-12-31", "annual", "bis_ratio", None, "extract_failed"), 1)
                fl.upsert_financials_fin(conn, direct)  # 재적재해도 비율 사유는 유지
                fl.update_stock_sector(conn, "105560", "bank")

                fin = conn.execute(text("SELECT total_assets, null_reasons FROM financials WHERE symbol = '105560' AND period_end = '1999-12-31'")).one()
                self.assertEqual(fin.total_assets, Decimal("1000"))
                self.assertEqual(fin.null_reasons["revenue"], "not_applicable")
                self.assertNotIn("total_assets", fin.null_reasons)
                old = conn.execute(text("SELECT total_assets FROM financials WHERE symbol = '105560' AND period_end = '1998-12-31'")).scalar()
                self.assertEqual(old, Decimal("1"))
                reasons = conn.execute(text("SELECT null_reasons FROM financials_fin WHERE symbol = '105560' AND period_end = '1999-12-31'")).scalar()
                self.assertEqual(reasons["bis_ratio"], "extract_failed")
                self.assertEqual(reasons["loans"], "not_reported")
                fl.set_ratio(conn, "105560", "1999-12-31", "annual", "bis_ratio", Decimal("15.5"), None)
                reasons = conn.execute(text("SELECT null_reasons FROM financials_fin WHERE symbol = '105560' AND period_end = '1999-12-31'")).scalar()
                self.assertNotIn("bis_ratio", reasons)
                stock = conn.execute(text("SELECT sector::text, fin_type FROM stocks WHERE symbol = '105560'")).one()
                self.assertEqual(tuple(stock), ("financial", "bank"))
            finally:
                outer.rollback()


if __name__ == "__main__":
    unittest.main()
