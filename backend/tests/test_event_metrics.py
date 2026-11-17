"""사건 공시 표준 비율 (pipelines.disclosures.event_metrics, 0018)."""

import unittest
from datetime import date

from pipelines.disclosures.event_metrics import compute

CTX = {"prev_annual": {"period_end": date(2025, 12, 31), "operating_income": 3_089_320_181_000, "net_income": 1_404_962_303_000},
       "equity": {"period_end": date(2026, 6, 30), "total_equity": 20_000_000_000_000},
       "market": {"trade_date": date(2026, 11, 13), "market_cap": 50_000_000_000_000, "close": 1_000_000, "listed_shares": 50_000_000}}


class EventMetricsTest(unittest.TestCase):
    def test_rights_offering(self):
        f = {"new_shares_common": 4_267_200, "issue_price_common": 684_000, "new_shares_other": None, "issue_price_other": None,
             "shares_before_common": 51_000_000, "use_facility_krw": 1_000_000_000}
        m, inputs, reasons = compute("rights_offering", f, False, CTX)
        self.assertEqual(m["raise_krw"], 4_267_200 * 684_000)            # 신주 × 발행가 (자금 용도 합계보다 우선)
        self.assertEqual(inputs["raise_source"], "new_shares×issue_price")
        self.assertEqual(m["dilution_pct"], 8.37)
        self.assertEqual(m["raise_to_prev_op_income_x"], 0.94)
        self.assertEqual(m["raise_to_equity_pct"], 14.59)
        self.assertEqual(m["raise_to_market_cap_pct"], 5.84)
        self.assertEqual(inputs["prev_op_income"]["period_end"], "2025-12-31")
        self.assertEqual(reasons, {})

    def test_rights_offering_without_price_uses_fund_uses_and_loss_base(self):
        f = {"new_shares_common": 1000, "shares_before_common": 10000, "use_operating_krw": 5_000_000, "use_debt_krw": 1_000_000}
        ctx = {**CTX, "prev_annual": {**CTX["prev_annual"], "operating_income": -10}}
        m, inputs, reasons = compute("rights_offering", f, False, ctx)
        self.assertEqual((m["raise_krw"], inputs["raise_source"]), (6_000_000, "use_of_funds_sum"))
        self.assertEqual(reasons["raise_to_prev_op_income_x"], "non_positive_base")   # 적자 회사는 배수를 내지 않는다

    def test_treasury_and_cancel(self):
        m, _, _ = compute("treasury_buy", {"trust_amount": 5_000_000_000, "shares_common": 500_000}, False, CTX)
        self.assertEqual((m["amount_krw"], m["amount_to_market_cap_pct"], m["shares_pct"]), (5_000_000_000, 0.01, 1.0))
        m, _, _ = compute("share_cancel", {"shares_common": 1_000_000, "issued_common": 50_000_000, "amount_krw": 10**12}, False, CTX)
        self.assertEqual((m["cancel_pct"], m["amount_to_market_cap_pct"]), (2.0, 2.0))
        m, _, reasons = compute("treasury_sell", {"cancel_shares_common": 100_000}, False, {**CTX, "market": None})
        self.assertEqual(reasons, {"amount_krw": "source_null", "amount_to_market_cap_pct": "missing_market_cap",
                                   "shares_pct": "missing_listed_shares"})

    def test_dividend_year_end_only(self):
        m, inputs, reasons = compute("dividend", {"total_krw": 702_481_000_000, "record_date": "2025-12-31",
                                                  "dividend_kind": "결산배당"}, False, CTX)
        self.assertEqual(m["payout_ratio_pct"], 50.0)
        self.assertEqual(inputs["prev_net_income"]["source"], "financials.annual(지배주주)")
        m, _, reasons = compute("dividend", {"total_krw": 100, "record_date": "2026-09-30", "dividend_kind": "분기배당"},
                                False, CTX)
        self.assertEqual((m, reasons), ({"total_krw": 100}, {"payout_ratio_pct": "interim_dividend"}))

    def test_subsidiary_and_market_cap_fallback(self):
        self.assertEqual(compute("rights_offering", {"new_shares_common": 1}, True, CTX), ({}, {}, {"all": "subsidiary_event"}))
        ctx = {**CTX, "market": {"trade_date": date(2026, 11, 13), "market_cap": None, "close": 1000, "listed_shares": 100}}
        m, inputs, _ = compute("treasury_buy", {"amount_common": 1000, "shares_common": 1}, False, ctx)
        self.assertEqual((m["amount_to_market_cap_pct"], inputs["market_cap"]["source"]), (1.0, "close×listed_shares"))


if __name__ == "__main__":
    unittest.main()


class RefreshDbTest(unittest.TestCase):
    """실제 DB(테스트 DB), 트랜잭션 롤백. 1999년 가짜 공시만 쓴다. 0018 표가 없으면 건너뛴다."""

    def test_refresh_saves_and_failure_does_not_break_transaction(self):
        from unittest import mock

        from sqlalchemy import text

        from pipelines.disclosures import event_metrics as em
        try:
            from pipelines.common.db import get_engine
            engine = get_engine()
            with engine.connect() as c:
                if c.execute(text("SELECT to_regclass('public.disclosure_event_metrics')")).scalar() is None:
                    raise unittest.SkipTest("0018 표 없음")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise unittest.SkipTest(f"DB 연결 불가: {type(exc).__name__}")
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text("INSERT INTO disclosures (rcept_no, symbol, title, kind, rcept_dt)"
                                  " VALUES ('19990101900001', '005930', '주식소각결정', 'major', '1999-01-01')"))
                conn.execute(text("INSERT INTO disclosure_events (rcept_no, event_type, topic, base_title, fields, parse_status,"
                                  " parser_version) VALUES ('19990101900001', 'share_cancel', 'shareholder_return', '주식소각결정',"
                                  " CAST(:f AS jsonb), 'ok', 't')"), {"f": '{"shares_common": 10, "issued_common": 1000}'})
                self.assertEqual(em.refresh(conn, rcept_no="19990101900001"), 1)
                row = conn.execute(text("SELECT metrics, calc_version FROM disclosure_event_metrics"
                                        " WHERE rcept_no = '19990101900001'")).one()
                self.assertEqual((row.metrics["cancel_pct"], row.calc_version), (1.0, em.CALC_VERSION))
                with mock.patch.object(em, "compute_row", side_effect=RuntimeError("boom")):
                    self.assertEqual(em.refresh(conn, rcept_no="19990101900001"), 0)    # 실패는 0, 예외를 올리지 않는다
                self.assertEqual(conn.execute(text("SELECT 1")).scalar(), 1)            # 바깥 트랜잭션은 계속 쓸 수 있다
                with self.assertRaises(ValueError):
                    em.refresh(conn)
            finally:
                outer.rollback()
