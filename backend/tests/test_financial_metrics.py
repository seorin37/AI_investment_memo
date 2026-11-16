"""계산 지표 (financial_metrics, 마이그레이션 0017) · 이자비용 계정 순서 · 자본잉여금 대체 계정."""

import unittest
from datetime import date
from decimal import Decimal as D

from pipelines.disclosures import financial_metrics as fmx
from pipelines.disclosures import financials as fm


def P(pe, pt, interest=None, basis="income_statement", fs="consolidated", reasons=None, **v):
    base = {c: None for c in fmx.FLOW_COLS + fmx.BALANCE_COLS}
    base.update({k: D(x) if x is not None else None for k, x in v.items()})
    return fmx.Period(date.fromisoformat(pe), pt, fs, base, reasons or {},
                      D(interest) if interest is not None else None, basis if interest is not None else None)


BAL = dict(total_liabilities=50, total_equity=100, current_assets=80, current_liabilities=40, inventories=20,
           retained_earnings=150, capital_stock=50, capital_surplus=50)


def two_years(**over):
    """2024 연간·2024 q3·2025 q3 (누적). TTM(2025 q3) = 2025q3 + 2024annual - 2024q3."""
    rows = [
        P("2024-09-30", "q3", interest=6, operating_income=30, net_income=15, **BAL),
        P("2024-12-31", "annual", interest=8, operating_income=40, net_income=20, **BAL),
        P("2025-09-30", "q3", interest=9, operating_income=45, net_income=24, **BAL),
    ]
    for i, r in over.items():
        rows[int(i[1:])] = r
    return rows


class ComputeTest(unittest.TestCase):
    def rows(self, periods, quarters=None, fin=None, sector="general", fin_type=None):
        return {r.period_end: r for r in fmx.compute(periods, quarters or {}, fin or {}, sector, fin_type)}

    def test_ttm_interest_coverage_and_roe(self):
        r = self.rows(two_years())[date(2025, 9, 30)]
        # TTM 영업이익 = 45 + 40 - 30 = 55, TTM 이자 = 9 + 8 - 6 = 11 → 5배
        self.assertEqual(r.values["interest_coverage"], D("5.00"))
        self.assertEqual(r.interest_coverage_basis, "income_statement")
        # TTM 순이익 = 24 + 20 - 15 = 29 / 자본 100
        self.assertEqual(r.values["roe"], D("29.00"))

    def test_balance_ratios(self):
        r = self.rows(two_years())[date(2025, 9, 30)]
        self.assertEqual(r.values["debt_ratio"], D("50.00"))
        self.assertEqual(r.values["current_ratio"], D("200.00"))
        self.assertEqual(r.values["quick_ratio"], D("150.00"))
        self.assertEqual(r.values["reserve_ratio"], D("400.00"))  # (50 + 150) / 50

    def test_annual_uses_own_values(self):
        r = self.rows(two_years())[date(2024, 12, 31)]
        self.assertEqual(r.values["interest_coverage"], D("5.00"))  # 40 / 8

    def test_missing_prev_period(self):
        r = self.rows(two_years())[date(2024, 9, 30)]  # 2023 행 없음
        self.assertIsNone(r.values["interest_coverage"])
        self.assertEqual(r.null_reasons["interest_coverage"], "missing_prev_period")

    def test_basis_mismatch(self):
        rows = two_years(i0=P("2024-09-30", "q3", interest=6, basis="cf_paid", operating_income=30, net_income=15, **BAL))
        r = self.rows(rows)[date(2025, 9, 30)]
        self.assertEqual(r.null_reasons["interest_coverage"], "basis_mismatch")

    def test_no_interest(self):
        rows = [P("2024-12-31", "annual", interest=0, operating_income=40, net_income=20, **BAL)]
        self.assertEqual(self.rows(rows)[date(2024, 12, 31)].null_reasons["interest_coverage"], "no_interest")

    def test_interest_source_reason_passes_through(self):
        p = P("2024-12-31", "annual", operating_income=40, net_income=20, **BAL)
        p.interest_reason = "not_reported"
        self.assertEqual(self.rows([p])[date(2024, 12, 31)].null_reasons["interest_coverage"], "not_reported")

    def test_quick_ratio_without_inventory_account(self):
        bal = {**BAL, "inventories": None}
        p = P("2024-12-31", "annual", reasons={"inventories": "not_reported"}, **bal)
        self.assertEqual(self.rows([p])[date(2024, 12, 31)].values["quick_ratio"], D("200.00"))
        p2 = P("2024-12-31", "annual", reasons={"inventories": "needs_review"}, **bal)
        self.assertEqual(self.rows([p2])[date(2024, 12, 31)].null_reasons["quick_ratio"], "source_null")

    def test_non_positive_equity(self):
        p = P("2024-12-31", "annual", **{**BAL, "total_equity": -5})
        self.assertEqual(self.rows([p])[date(2024, 12, 31)].null_reasons["debt_ratio"], "non_positive_base")

    def test_quarter_margins(self):
        q = {date(2024, 12, 31): {"revenue": D(200), "operating_income": D(20), "net_income": D(-10)}}
        r = self.rows([P("2024-12-31", "annual", **BAL)], quarters=q)[date(2024, 12, 31)]
        self.assertEqual((r.values["operating_margin"], r.values["net_margin"]), (D("10.00"), D("-5.00")))
        self.assertEqual(r.null_reasons["fin_operating_revenue"], "not_applicable")

    def test_financial_company(self):
        fin = {date(2024, 12, 31): {"net_interest_income": D(70), "fee_income": D(30)}}
        q = {date(2024, 12, 31): {"revenue": None, "operating_income": D(25), "net_income": D(20)}}
        bal = {**BAL, "current_assets": None, "current_liabilities": None, "inventories": None}
        r = self.rows([P("2024-12-31", "annual", **bal)], quarters=q, fin=fin, sector="financial", fin_type="bank")[date(2024, 12, 31)]
        self.assertEqual((r.values["fin_operating_revenue"], r.fin_revenue_basis), (D(100), "nii_plus_fee"))
        self.assertEqual(r.values["operating_margin"], D("25.00"))  # 대용값 분모 (화면엔 안 띄움, 값은 저장)
        self.assertEqual(r.null_reasons["current_ratio"], "not_applicable_fin")
        self.assertEqual(r.null_reasons["quick_ratio"], "not_applicable_fin")
        self.assertEqual(r.values["debt_ratio"], D("50.00"))


def rows_of(*items):
    return [{"account_id": a, "account_nm": n, "sj_div": sj, "thstrm_amount": v, "thstrm_add_amount": add, "currency": "KRW"}
            for a, n, sj, v, add in items]


class InterestChainTest(unittest.TestCase):
    def test_income_statement_first(self):
        rows = rows_of(("ifrs-full_InterestExpense", "이자비용", "CIS", "100", "300"),
                       ("ifrs-full_InterestPaidClassifiedAsOperatingActivities", "이자지급", "CF", "-250", None))
        self.assertEqual(fm.pick_interest_cost(rows, "q3"), (D(300), "income_statement", None))  # 분기는 누적 필드

    def test_cf_adjustment_then_paid(self):
        rows = rows_of(("dart_AdjustmentsForInterestExpenses", "이자비용", "CF", "3040", None),
                       ("ifrs-full_InterestPaidClassifiedAsOperatingActivities", "이자지급", "CF", "-1750", None))
        self.assertEqual(fm.pick_interest_cost(rows, "q3"), (D(3040), "cf_adjustment", None))
        paid = rows_of(("ifrs-full_InterestPaidClassifiedAsOperatingActivities", "이자지급", "CF", "-1750", None),
                       ("ifrs-full_InterestPaidClassifiedAsFinancingActivities", "이자지급", "CF", "-50", None))
        self.assertEqual(fm.pick_interest_cost(paid, "annual"), (D(1800), "cf_paid", None))  # 영업+재무 분류 합, 양수

    def test_finance_costs_not_used(self):
        rows = rows_of(("ifrs-full_FinanceCosts", "금융비용", "IS", "999", None))
        self.assertEqual(fm.pick_interest_cost(rows, "annual"), (None, None, "not_reported"))

    def test_cf_prior_quarter_unavailable(self):
        rows = rows_of(("ifrs-full_InterestPaidClassifiedAsOperatingActivities", "이자지급", "CF", "-1", None))
        self.assertEqual(fm.pick_interest_cost(rows, "q1", prior=True), (None, None, "not_reported"))


class CapitalSurplusTest(unittest.TestCase):
    def setUp(self):
        self.rule = next(r for r in fm.load_mapping("../configs/financials_mapping.yaml").financials if r.column == "capital_surplus")

    def pick(self, *items):
        return fm.pick(rows_of(*items), self.rule, "000001", "2025-12-31", "f.json", ptype="annual")

    def test_standard_id(self):
        self.assertEqual(self.pick(("dart_CapitalSurplus", "자본잉여금", "BS", "500", None)).value, D(500))

    def test_name_pattern(self):
        p = self.pick(("ifrs-full_AdditionalPaidinCapital", "Ⅱ. 자본잉여금", "BS", "70", None),
                      ("ifrs-full_AdditionalPaidinCapital", "자본잉여금", "BS", "70", None))
        self.assertEqual((p.value, p.source["fallback"]), (D(70), "name_pattern"))

    def test_share_premium_sum(self):
        p = self.pick(("ifrs-full_SharePremium", "주식발행초과금", "BS", "300", None),
                      ("dart_OtherCapitalSurplus", "기타자본잉여금", "BS", "20", None))
        self.assertEqual((p.value, p.source["fallback"]), (D(320), "sum_ids"))

    def test_other_paid_in_capital_stays_null(self):
        p = self.pick(("ifrs-full_AdditionalPaidinCapital", "기타불입자본", "BS", "900", None))
        self.assertIsNone(p.value)

    def test_other_capital_surplus_alone_not_used(self):
        self.assertIsNone(self.pick(("dart_OtherCapitalSurplus", "기타자본잉여금", "BS", "20", None)).value)


if __name__ == "__main__":
    unittest.main()
