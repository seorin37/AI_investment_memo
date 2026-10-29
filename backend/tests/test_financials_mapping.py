"""WO-015 ②단계: 재무 원본 → financials / financials_fin 매핑·적재 (실제 API 호출 없음).

DB 테스트는 DATABASE_URL로 연결되면 트랜잭션 롤백으로 실행하고, 연결할 수 없으면 skip한다.
"""

import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from pipelines.common.config import REPO_ROOT
from pipelines.disclosures import financials as fm
from pipelines.disclosures import financials_loader as fl
from pipelines.disclosures import financials_pipeline as fp


MAPPING_PATH = REPO_ROOT / "configs" / "financials_mapping.yaml"


def row(sj_div, account_id, amount="", add="", currency="KRW", rcept_no="20250101000001"):
    return {"sj_div": sj_div, "account_id": account_id, "thstrm_amount": amount, "thstrm_add_amount": add, "currency": currency, "rcept_no": rcept_no}


def rule(**overrides):
    spec = {"sj_div": ["IS", "CIS"], "kind": "flow", "ids": ["a"]}
    spec.update(overrides)
    return fm._rule("col", spec)


def shares(status="000", **rows):
    return {"status": status, "list": [{"se": se, "istc_totqy": v[0], "tesstk_co": v[1], "distb_stock_co": v[2]} for se, v in rows.items()]}


class ParseAmountTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(fm.parse_amount("1,234,567"), Decimal("1234567"))
        self.assertEqual(fm.parse_amount("(1,000)"), Decimal("-1000"))
        self.assertEqual(fm.parse_amount("-2500"), Decimal("-2500"))
        self.assertEqual(fm.parse_amount(" 15410 "), Decimal("15410"))
        for empty in ("", "-", " - ", None, "N/A", "()", "NaN", "Infinity"):
            self.assertIsNone(fm.parse_amount(empty), empty)


class PickTest(unittest.TestCase):
    def test_flow_uses_cumulative_for_quarters_and_annual_amount_for_annual(self):
        rows = [row("IS", "a", amount="100", add="250")]
        self.assertEqual(fm.pick(rows, rule(), "s", "2025-06-30", "f").value, Decimal("250"))
        self.assertEqual(fm.pick(rows, rule(), "s", "2025-12-31", "f").value, Decimal("100"))
        picked = fm.pick(rows, rule(), "s", "2025-09-30", "f")
        self.assertEqual(picked.source["field"], "thstrm_add_amount")

    def test_missing_cumulative_value_is_null_with_reason(self):
        picked = fm.pick([row("IS", "a", amount="100", add="")], rule(), "s", "2025-03-31", "f")
        self.assertIsNone(picked.value)
        self.assertIn("누적값 미확인", picked.reason)

    def test_balance_uses_bs_only_and_ignores_sce_total(self):
        rows = [row("SCE", "ifrs-full_Equity", amount="39169"), row("BS", "ifrs-full_Equity", amount="40219")]
        balance = fm._rule("total_equity", {"sj_div": ["BS"], "kind": "balance", "ids": ["ifrs-full_Equity"]})
        self.assertEqual(fm.pick(rows, balance, "s", "2024-12-31", "f").value, Decimal("40219"))
        self.assertEqual(fm.pick(rows, balance, "s", "2024-06-30", "f").value, Decimal("40219"))  # 잔액은 분기도 thstrm_amount
        self.assertIsNone(fm.pick(rows[:1], balance, "s", "2024-12-31", "f").value)
        with self.assertRaises(ValueError):
            fm._rule("total_equity", {"sj_div": ["BS", "SCE"], "kind": "balance", "ids": ["ifrs-full_Equity"]})

    def test_is_and_cis_both_searched_and_priority(self):
        cis_only = [row("CIS", "b", amount="7")]
        self.assertEqual(fm.pick(cis_only, rule(ids=["a", "b"]), "s", "2025-12-31", "f").value, Decimal("7"))
        both = [row("IS", "a", amount="1"), row("CIS", "b", amount="2")]
        picked = fm.pick(both, rule(ids=["a", "b"]), "s", "2025-12-31", "f")
        self.assertEqual((picked.value, picked.source["account_id"]), (Decimal("1"), "a"))
        same = [row("IS", "a", amount="5"), row("CIS", "a", amount="5")]
        self.assertEqual(fm.pick(same, rule(), "s", "2025-12-31", "f").source["sj_div"], "CIS,IS")

    def test_ambiguous_and_currency_and_missing(self):
        ambiguous = [row("IS", "a", amount="1"), row("CIS", "a", amount="2")]
        self.assertIn("모호", fm.pick(ambiguous, rule(), "s", "2025-12-31", "f").reason)
        usd = [row("IS", "a", amount="1", currency="USD")]
        self.assertIn("KRW", fm.pick(usd, rule(), "s", "2025-12-31", "f").reason)
        self.assertIn("후보 account_id 없음", fm.pick([row("BS", "a", amount="1")], rule(), "s", "2025-12-31", "f").reason)

    def test_overrides_null_rules_sign_and_per_share(self):
        rows = [row("IS", "a", amount="10"), row("IS", "x", amount="99")]
        self.assertEqual(fm.pick(rows, rule(overrides={"005930": ["x"]}), "005930", "2025-12-31", "f").value, Decimal("99"))
        self.assertEqual(fm.pick(rows, rule(sign=-1), "s", "2025-12-31", "f").value, Decimal("-10"))
        nulled = fm.pick(rows, rule(null_symbols={"105560": "금융"}), "105560", "2025-12-31", "f")
        self.assertEqual((nulled.value, nulled.source["expected_null"]), (None, True))
        period_null = fm.pick(rows, rule(null_periods={"s 2024-03-31": "결정"}), "s", "2024-03-31", "f")
        self.assertIsNone(period_null.value)
        self.assertEqual(fm.pick(rows, rule(null_periods={"s 2024-03-31": "결정"}), "s", "2024-06-30", "f").value, None)  # 누적 필드 비어 있음
        eps = rule(kind="per_share")
        self.assertEqual(fm.pick([row("IS", "a", amount="1234.567")], eps, "s", "2025-12-31", "f").value, Decimal("1234.57"))
        self.assertIn("정수가 아님", fm.pick([row("IS", "a", amount="1.5")], rule(), "s", "2025-12-31", "f").reason)


class SharesAndBpsTest(unittest.TestCase):
    def test_total_row_preferred(self):
        counts = fm.parse_share_counts(shares(보통주=("100", "10", "90"), 우선주=("20", "-", "20"), 합계=("120", "10", "110")))
        self.assertEqual((counts.issued, counts.treasury, counts.outstanding, counts.basis), (120, 10, 110, "합계"))

    def test_without_total_sums_common_and_preferred(self):
        counts = fm.parse_share_counts(shares(보통주=("1,000", "100", "900"), 우선주=("200", "-", "200")))
        self.assertEqual((counts.issued, counts.treasury, counts.outstanding, counts.basis), (1200, 100, 1100, "보통주+우선주"))
        no_preferred = fm.parse_share_counts(shares(보통주=("1,000", "100", "900")))
        self.assertEqual(no_preferred.issued, 1000)

    def test_unreported_quarter_and_013(self):
        counts = fm.parse_share_counts(shares(합계=("-", "-", "-")))
        self.assertIsNone(counts.issued)
        self.assertIsNone(fm.compute_bps(Decimal("100"), counts))
        self.assertIsNone(fm.parse_share_counts({"status": "013", "message": "없음"}))

    def test_treasury_dash_is_zero_only_when_outstanding_equals_issued(self):
        self.assertEqual(fm.parse_share_counts(shares(합계=("6,792", "-", "6,792"))).treasury, 0)
        self.assertIsNone(fm.parse_share_counts(shares(합계=("6,792", "-", "6,700"))).treasury)

    def test_compute_bps(self):
        counts = fm.ShareCounts(issued=300, treasury=0, outstanding=300, basis="합계")
        self.assertEqual(fm.compute_bps(Decimal("1000"), counts), Decimal("3.33"))
        self.assertIsNone(fm.compute_bps(None, counts))
        self.assertIsNone(fm.compute_bps(Decimal("1"), None))
        self.assertIsNone(fm.compute_bps(Decimal("1"), fm.ShareCounts(10, 10, 0, "합계")))


class RealMappingTest(unittest.TestCase):
    """configs/financials_mapping.yaml 자체와 실제 응답 형태에 대한 회귀 테스트."""

    @classmethod
    def setUpClass(cls):
        cls.mapping = fm.load_mapping(MAPPING_PATH)

    def test_columns_match_db_spec(self):
        self.assertEqual({r.column for r in self.mapping.financials} | {"bps"}, set(fl.FINANCIALS_VALUES))
        self.assertEqual({r.column for r in self.mapping.financials_fin}, set(fl.FIN_VALUES))
        self.assertEqual(self.mapping.fin_symbols, ("105560",))
        for r in self.mapping.financials + self.mapping.financials_fin:
            self.assertNotIn("ifrs-full_FinanceCosts", r.ids)  # 금융비용 합계를 이자비용으로 쓰지 않는다

    def statement(self, extra=()):
        return general_statement(extra)

    def test_general_company(self):
        period = fm.map_period("000660", "2025-09-30", "CFS", self.statement(), "f.json", shares(합계=("100", "0", "100")), "s.json", self.mapping)
        v = period.values
        self.assertEqual(v["revenue"], Decimal("900"))  # 3분기 누적
        self.assertEqual(v["net_income"], Decimal("60"))  # 지배주주 (ProfitLoss 75 아님)
        self.assertEqual(v["total_equity"], Decimal("600"))  # BS (SCE 550 아님)
        self.assertEqual(v["capital_surplus"], Decimal("40"))
        self.assertIsNone(v["inventories"])
        self.assertIsNone(v["interest_expense"])  # FinanceCosts 미사용
        self.assertEqual(v["eps"], Decimal("6.00"))
        self.assertEqual(v["bps"], Decimal("5.00"))  # 500 / 100
        self.assertEqual((period.fs_div, period.period_type, period.rcept_no, period.fin_values), ("consolidated", "q3", "20250101000001", None))
        self.assertTrue(any("inventories" in line for line in period.review))
        bps = next(p for p in period.provenance if p["column"] == "bps")
        self.assertEqual((bps["shares_basis"], bps["issued"], bps["owners_equity"]["account_id"]), ("합계", 100, "ifrs-full_EquityAttributableToOwnersOfParent"))

    def test_samsung_capital_surplus_override_and_separate_label(self):
        period = fm.map_period("005930", "2025-12-31", "OFS", self.statement(), "f.json", None, None, self.mapping)
        self.assertEqual(period.values["capital_surplus"], Decimal("44"))
        self.assertEqual(period.fs_div, "separate")
        self.assertIsNone(period.values["bps"])
        self.assertTrue(any("주식 총수 데이터 없음" in line for line in period.review))

    def test_naver_2024_q1_continuing_operations_fallback(self):
        continuing = [
            row("CIS", "ifrs-full_ProfitLossFromContinuingOperations", "75", "75"),
            row("CIS", "ifrs-full_IncomeFromContinuingOperationsAttributableToOwnersOfParent", "60", "60"),
            row("CIS", "ifrs-full_ProfitLossFromContinuingOperationsAttributableToNoncontrollingInterests", "15", "15"),
            row("CIS", "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations", "6", "6"),
        ]
        statement = self.statement(continuing)
        statement["list"] = [r for r in statement["list"] if r["account_id"] not in ("ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs-full_BasicEarningsLossPerShare")]
        period = fm.map_period("035420", "2024-03-31", "CFS", statement, "f.json", None, None, self.mapping)
        self.assertEqual((period.values["net_income"], period.values["eps"]), (Decimal("60"), Decimal("6.00")))
        sources = {p["column"]: p for p in period.provenance}
        self.assertTrue(sources["net_income"]["condition_ok"])
        self.assertTrue(sources["net_income"]["component_sum_ok"])
        self.assertEqual(sources["eps"]["fallback_account"], "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations")
        self.assertFalse(any("net_income" in line or "financials.eps" in line for line in period.review))

    def test_continuing_operations_fallback_rejects_mismatch_and_keeps_normal_account(self):
        continuing = [
            row("CIS", "ifrs-full_ProfitLossFromContinuingOperations", "74", "74"),
            row("CIS", "ifrs-full_IncomeFromContinuingOperationsAttributableToOwnersOfParent", "60", "60"),
            row("CIS", "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations", "6", "6"),
        ]
        statement = self.statement(continuing)
        statement["list"] = [r for r in statement["list"] if r["account_id"] not in ("ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs-full_BasicEarningsLossPerShare")]
        rejected = fm.map_period("035420", "2024-03-31", "CFS", statement, "f.json", None, None, self.mapping)
        self.assertIsNone(rejected.values["net_income"])
        self.assertIsNone(rejected.values["eps"])
        self.assertTrue(any("대체 조건 불충족" in line for line in rejected.review))

        normal = fm.map_period("035420", "2024-03-31", "CFS", self.statement(continuing), "f.json", None, None, self.mapping)
        self.assertEqual((normal.values["net_income"], normal.values["eps"]), (Decimal("60"), Decimal("6.00")))
        self.assertNotIn("fallback_rule", next(p for p in normal.provenance if p["column"] == "net_income"))

    def test_api_share_counts_take_priority_over_fallback(self):
        fallback = fm.ShareCounts(issued=999, treasury=99, outstanding=900, basis="의결권 현황 표")
        period = fm.map_period("000660", "2025-09-30", "CFS", self.statement(), "f.json",
                               shares(합계=("100", "10", "90")), "s.json", self.mapping,
                               fallback_shares=fallback, fallback_shares_source={"source": "voting_rights"})
        self.assertEqual(period.values["bps"], Decimal("5.56"))  # 500 / (100 - 10), fallback이면 0.56
        source = next(p for p in period.provenance if p["column"] == "bps")
        self.assertEqual(source["shares_basis"], "합계")
        self.assertNotIn("shares_fallback", source)

    def test_kb_financial(self):
        kb_rows = [
            row("CIS", "ifrs-full_ProfitLossFromOperatingActivities", "85", "85"),
            row("CIS", "ifrs-full_InterestRevenueExpense", "130", "130"),
            row("CIS", "ifrs-full_FeeAndCommissionIncomeExpense", "41", "41"),
            row("CIS", "dart_AdditionReversalOfCreditLossFinancialAssets", "20", "20"),
            row("CIS", "ifrs-full_InterestExpense", "160", "160"),
        ]
        statement = self.statement(kb_rows)
        statement["list"] = [r for r in statement["list"] if r["account_id"] not in ("ifrs-full_Revenue", "dart_OperatingIncomeLoss")]
        period = fm.map_period("105560", "2025-12-31", "CFS", statement, "f.json", shares(합계=("10", "1", "9")), "s.json", self.mapping)
        v = period.values
        for column in ("revenue", "current_assets", "current_liabilities", "inventories"):
            self.assertIsNone(v[column], column)  # 일반 기업 전용 항목은 값이 있어도 NULL
        self.assertEqual(v["operating_income"], Decimal("85"))
        self.assertEqual(v["interest_expense"], Decimal("160"))
        self.assertEqual(period.fin_type, "holding")  # fin_type_overrides
        self.assertEqual(period.fin_values, {
            "net_interest_income": Decimal("130"), "fee_income": Decimal("41"), "loan_loss_provision": Decimal("20"),
            "loans": None, "deposits": None, "insurance_revenue": None, "securities_operating_revenue": None,
        })
        self.assertEqual(period.fin_null_reasons, {"loans": "not_reported", "deposits": "not_reported",
                                                   "insurance_revenue": "not_reported", "securities_operating_revenue": "not_applicable"})
        self.assertEqual(period.null_reasons, {c: "not_applicable" for c in ("revenue", "current_assets", "current_liabilities", "inventories")})
        self.assertEqual({line.split(": ")[0] for line in period.review},
                         {f"105560 2025-12-31 financials_fin.{c}" for c in ("loans", "deposits", "insurance_revenue")})


def general_statement(extra=()):
    """일반 기업 응답 형태의 최소 재무제표 (SCE 자본총계·ProfitLoss·FinanceCosts 같은 함정 행 포함)."""
    rows = [
        row("IS", "ifrs-full_Revenue", "300", "900"),
        row("IS", "dart_OperatingIncomeLoss", "30", "90"),
        row("IS", "ifrs-full_ProfitLoss", "25", "75"),
        row("IS", "ifrs-full_ProfitLossAttributableToOwnersOfParent", "20", "60"),
        row("IS", "ifrs-full_BasicEarningsLossPerShare", "2", "6"),
        row("BS", "ifrs-full_Assets", "1000"),
        row("BS", "ifrs-full_Liabilities", "400"),
        row("BS", "ifrs-full_Equity", "600"),
        row("SCE", "ifrs-full_Equity", "550"),
        row("BS", "ifrs-full_EquityAttributableToOwnersOfParent", "500"),
        row("BS", "ifrs-full_CurrentAssets", "300"),
        row("BS", "ifrs-full_CurrentLiabilities", "200"),
        row("BS", "ifrs-full_RetainedEarnings", "450"),
        row("BS", "ifrs-full_IssuedCapital", "10"),
        row("BS", "dart_CapitalSurplus", "40"),
        row("BS", "ifrs-full_SharePremium", "44"),
        row("CIS", "ifrs-full_FinanceCosts", "9", "27"),
        *extra,
    ]
    return {"status": "000", "list": rows}


class UpdateProvenanceTest(unittest.TestCase):
    def test_replaces_by_key_and_keeps_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.jsonl"
            base = {"symbol": "s", "period_end": "2025-12-31", "table": "financials"}
            fp.update_provenance(path, [{**base, "column": "a", "value": Decimal("1")}, {**base, "column": "b", "value": None}])
            fp.update_provenance(path, [{**base, "column": "a", "value": Decimal("2")}])
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(r["column"], r["value"]) for r in rows], [("a", "2"), ("b", None)])


class LoadDryRunTest(unittest.TestCase):
    def test_dry_run_maps_saved_files_without_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"targets": {"periods": ["2025-12-31", "2026-03-31"]},
                      "paths": {"logs_dir": "logs", "financials_raw_dir": "fin", "shares_raw_dir": "shares", "financials_dir": "out"}}
            (root / "c.yaml").write_text(json.dumps(config), encoding="utf-8")
            (root / "fin").mkdir()
            (root / "fin" / "000660_2025_11011_CFS.json").write_text(json.dumps(general_statement()), encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                code = fp.main(["--config", str(root / "c.yaml"), "--root", str(root), "--symbols", "000660",
                                "--mapping", str(MAPPING_PATH), "--steps", "load", "--dry-run"], engine=None)
            record = json.loads(next((root / "logs").glob("financials_*.json")).read_text(encoding="utf-8"))
            self.assertEqual(code, 1)  # 2026-03-31 원본 없음 → 실패 목록
            self.assertEqual(record["mapping"]["000660 2025-12-31"]["revenue"], "300")
            self.assertIn("원본이 없습니다", record["failures"][0])
            self.assertFalse((root / "out").exists())  # dry-run은 provenance를 쓰지 않는다


class PreflightTest(unittest.TestCase):
    class FakeConn:
        def __init__(self, version, symbols):
            self.version, self.symbols = version, symbols

        def execute(self, statement, params=None):
            sql = str(statement)
            result = mock.Mock()
            if "alembic_version" in sql:
                result.scalars.return_value = [self.version]
            else:
                result.scalars.return_value = self.symbols
            return result

    def test_detects_version_columns_and_stocks(self):
        good = {t: dict(c) for t, c in fl.EXPECTED_COLUMNS.items()}
        with mock.patch.object(fl, "table_columns", side_effect=lambda conn, t: good[t]):
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            root = Path(__file__).resolve().parents[2]
            cfg = Config(str(root / "alembic.ini"))
            cfg.set_main_option("script_location", str(root / "alembic"))
            head = ScriptDirectory.from_config(cfg).get_current_head()
            fl.preflight(self.FakeConn(head, ["105560"]), ["105560"])
        bad = {t: dict(c) for t, c in fl.EXPECTED_COLUMNS.items()}
        bad["financials"]["eps"] = "numeric(20,0)"
        del bad["financials_fin"]["bis_ratio"]
        with mock.patch.object(fl, "table_columns", side_effect=lambda conn, t: bad[t]):
            with self.assertRaises(fl.FinancialsPreflightError) as ctx:
                fl.preflight(self.FakeConn("0004", []), ["105560"])
        message = str(ctx.exception)
        for part in ("0004", "eps", "bis_ratio", "105560"):
            self.assertIn(part, message)


def _engine_or_skip():
    try:
        from pipelines.common.db import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine
    except Exception as exc:  # DB 없음·설정 없음
        raise unittest.SkipTest(f"DB 연결 불가: {type(exc).__name__}")


class UpsertDbTest(unittest.TestCase):
    """실제 DB, 트랜잭션 롤백. 대상 기간 밖(1999년) 날짜만 쓴다."""

    def test_upsert_is_idempotent_and_keeps_bis_ratio(self):
        from sqlalchemy import text

        engine = _engine_or_skip()
        period = fm.MappedPeriod(
            symbol="105560", period_end="1999-12-31", period_type="annual", fs_div="consolidated", rcept_no=None,
            values={c: None for c in fl.FINANCIALS_VALUES} | {"total_assets": Decimal("100"), "eps": Decimal("1.50")},
            fin_values={"net_interest_income": Decimal("7"), "fee_income": None, "loan_loss_provision": Decimal("3")},
            provenance=[], review=[], shares=None,
        )
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                fl.preflight(conn, ["105560"])
                for _ in range(2):
                    fl.upsert_financials(conn, period)
                    fl.upsert_financials_fin(conn, period)
                conn.execute(text("UPDATE financials_fin SET bis_ratio = 15.5 WHERE symbol = '105560' AND period_end = '1999-12-31'"))
                period.values["total_assets"] = Decimal("200")
                fl.upsert_financials(conn, period)
                fl.upsert_financials_fin(conn, period)
                rows = conn.execute(text("SELECT total_assets, eps, fs_div FROM financials WHERE symbol = '105560' AND period_end = '1999-12-31'")).all()
                fin = conn.execute(text("SELECT net_interest_income, loan_loss_provision, bis_ratio FROM financials_fin WHERE symbol = '105560' AND period_end = '1999-12-31'")).all()
                self.assertEqual(rows, [(Decimal("200"), Decimal("1.50"), "consolidated")])
                self.assertEqual(fin, [(Decimal("7"), Decimal("3"), Decimal("15.50"))])  # load 재실행이 BIS 값을 지우지 않음
            finally:
                outer.rollback()


if __name__ == "__main__":
    unittest.main()
