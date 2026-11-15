"""분기 단독 손익 계산 (financials_quarterly, 마이그레이션 0016)."""

import unittest
from datetime import date
from decimal import Decimal as D

from pipelines.disclosures import financials_quarterly as fq


def row(pe, pt, fs="consolidated", **values):
    base = {c: None for c in fq.GENERAL_FLOWS}
    base.update({k: (D(v) if v is not None else None) for k, v in values.items()})
    return fq.SourceRow(date.fromisoformat(pe), pt, fs, base)


def year(fs=("consolidated",) * 4, **overrides):
    """12월 결산 한 해: 누적 매출 10, 25, 45, 70 → 분기 10, 15, 20, 25."""
    rows = {
        "q1": row("2025-03-31", "q1", fs[0], revenue=10, operating_income=-2, net_income=1),
        "half": row("2025-06-30", "half", fs[1], revenue=25, operating_income=-5, net_income=3),
        "q3": row("2025-09-30", "q3", fs[2], revenue=45, operating_income=1, net_income=6),
        "annual": row("2025-12-31", "annual", fs[3], revenue=70, operating_income=4, net_income=10),
    }
    rows.update(overrides)
    return [r for r in rows.values() if r is not None]


class FiscalYearTest(unittest.TestCase):
    def test_december_year_end(self):
        self.assertEqual(fq.fiscal_year_end(date(2025, 3, 31), "q1"), date(2025, 12, 31))
        self.assertEqual(fq.fiscal_year_end(date(2025, 6, 30), "half"), date(2025, 12, 31))
        self.assertEqual(fq.fiscal_year_end(date(2025, 12, 31), "annual"), date(2025, 12, 31))

    def test_non_december_year_end(self):
        # 3월 결산: q1 = 6월 말, half = 9월 말, q3 = 12월 말, annual = 다음 해 3월 말
        self.assertEqual(fq.fiscal_year_end(date(2025, 6, 30), "q1"), date(2026, 3, 31))
        self.assertEqual(fq.fiscal_year_end(date(2025, 12, 31), "q3"), date(2026, 3, 31))
        # 2월 결산 (윤년 말일)
        self.assertEqual(fq.fiscal_year_end(date(2027, 11, 30), "q3"), date(2028, 2, 29))


class DeriveTest(unittest.TestCase):
    def test_normal_year(self):
        qs = fq.derive(year(), fq.GENERAL_FLOWS)
        self.assertEqual([q.quarter for q in qs], [1, 2, 3, 4])
        self.assertEqual([q.values["revenue"] for q in qs], [D(10), D(15), D(20), D(25)])
        self.assertEqual([q.values["operating_income"] for q in qs], [D(-2), D(-3), D(6), D(3)])  # 음수 이익은 그대로
        self.assertEqual([q.method for q in qs], ["reported", "derived", "derived", "derived"])
        self.assertTrue(all(q.null_reasons == {} for q in qs))
        self.assertTrue(all(q.fiscal_year_end == date(2025, 12, 31) for q in qs))
        self.assertEqual(sum(q.values["net_income"] for q in qs), D(10))  # 분기 합 = 연간 누적

    def test_missing_q1_blocks_only_q2(self):
        qs = {q.quarter: q for q in fq.derive(year(q1=None), fq.GENERAL_FLOWS)}
        self.assertNotIn(1, qs)
        self.assertIsNone(qs[2].values["revenue"])
        self.assertEqual(qs[2].null_reasons["revenue"], "missing_prev_period")
        self.assertEqual(qs[3].values["revenue"], D(20))

    def test_fs_div_mismatch(self):
        qs = {q.quarter: q for q in fq.derive(year(fs=("separate", "consolidated", "consolidated", "consolidated")), fq.GENERAL_FLOWS)}
        self.assertEqual(qs[1].values["revenue"], D(10))  # Q1은 보고값 그대로
        self.assertEqual(qs[2].null_reasons["revenue"], "fs_div_mismatch")
        self.assertEqual(qs[3].values["revenue"], D(20))

    def test_source_null(self):
        half = row("2025-06-30", "half", revenue=None, operating_income=-5, net_income=3)
        qs = {q.quarter: q for q in fq.derive(year(half=half), fq.GENERAL_FLOWS)}
        self.assertEqual(qs[2].null_reasons["revenue"], "source_null")
        self.assertEqual(qs[3].null_reasons["revenue"], "source_null")  # 앞 기간 값이 없음
        self.assertEqual(qs[2].values["net_income"], D(2))

    def test_negative_revenue_needs_review(self):
        annual = row("2025-12-31", "annual", revenue=40, operating_income=4, net_income=10)  # 누적 역전 45 → 40
        qs = {q.quarter: q for q in fq.derive(year(annual=annual), fq.GENERAL_FLOWS)}
        self.assertIsNone(qs[4].values["revenue"])
        self.assertEqual(qs[4].null_reasons["revenue"], "needs_review")
        self.assertEqual(qs[4].values["net_income"], D(4))

    def test_correction_changes_next_quarter(self):
        before = {q.quarter: q.values["revenue"] for q in fq.derive(year(), fq.GENERAL_FLOWS)}
        corrected = row("2025-03-31", "q1", revenue=12, operating_income=-2, net_income=1)
        after = {q.quarter: q.values["revenue"] for q in fq.derive(year(q1=corrected), fq.GENERAL_FLOWS)}
        self.assertEqual((before[1], before[2]), (D(10), D(15)))
        self.assertEqual((after[1], after[2]), (D(12), D(13)))

    def test_fin_flows_negative_provision_kept(self):
        rows = [
            fq.SourceRow(date(2025, 3, 31), "q1", "consolidated", {c: None for c in fq.FIN_FLOWS} | {"net_interest_income": D(5), "loan_loss_provision": D(-1)}),
            fq.SourceRow(date(2025, 6, 30), "half", "consolidated", {c: None for c in fq.FIN_FLOWS} | {"net_interest_income": D(11), "loan_loss_provision": D(-3)}),
        ]
        qs = {q.quarter: q for q in fq.derive(rows, fq.FIN_FLOWS)}
        self.assertEqual(qs[2].values["net_interest_income"], D(6))
        self.assertEqual(qs[2].values["loan_loss_provision"], D(-2))
        self.assertEqual(qs[2].null_reasons["fee_income"], "source_null")

    def test_empty(self):
        self.assertEqual(fq.derive([], fq.GENERAL_FLOWS), [])


def _test_engine_or_skip():
    """로컬 테스트 DB(이름에 test)일 때만 실행한다."""
    try:
        from pipelines.common.db import get_engine

        engine = get_engine()
        if "test" not in (engine.url.database or ""):
            raise unittest.SkipTest("테스트 DB가 아님")
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1 FROM financials_quarterly LIMIT 1")
        return engine
    except unittest.SkipTest:
        raise
    except Exception as exc:
        raise unittest.SkipTest(f"DB 연결 불가 또는 0016 미적용: {type(exc).__name__}")


class RecomputeDbTest(unittest.TestCase):
    """테스트 DB, 트랜잭션 롤백. 대상 기간 밖(1999년)만 쓴다."""

    def test_loader_upsert_writes_quarters_and_recomputes_on_correction(self):
        from sqlalchemy import text

        from pipelines.disclosures import financials as fm
        from pipelines.disclosures import financials_loader as fl

        engine = _test_engine_or_skip()

        def period(pe, pt, rev):
            return fm.MappedPeriod(symbol="005930", period_end=pe, period_type=pt, fs_div="consolidated", rcept_no=None,
                                   values={c: None for c in fl.FINANCIALS_VALUES} | {"revenue": D(rev), "net_income": D(1)},
                                   fin_values=None, provenance=[], review=[], shares=None)

        with engine.connect() as conn:
            outer = conn.begin()
            try:
                for pe, pt, rev in (("1999-03-31", "q1", 10), ("1999-06-30", "half", 25), ("1999-09-30", "q3", 45), ("1999-12-31", "annual", 70)):
                    self.assertTrue(fl.upsert_financials(conn, period(pe, pt, rev)))
                sql = text("SELECT quarter, revenue FROM financials_quarterly WHERE symbol = '005930' AND fiscal_year_end = '1999-12-31' ORDER BY quarter")
                self.assertEqual(conn.execute(sql).all(), [(1, D(10)), (2, D(15)), (3, D(20)), (4, D(25))])
                fl.upsert_financials(conn, period("1999-03-31", "q1", 12))  # 정정: Q1이 바뀌면 Q2도 바뀐다
                self.assertEqual(conn.execute(sql).all(), [(1, D(12)), (2, D(13)), (3, D(20)), (4, D(25))])
                # 누적 원본은 그대로
                cum = conn.execute(text("SELECT revenue FROM financials WHERE symbol = '005930' AND period_end = '1999-06-30'")).scalar()
                self.assertEqual(cum, D(25))
            finally:
                outer.rollback()


if __name__ == "__main__":
    unittest.main()
