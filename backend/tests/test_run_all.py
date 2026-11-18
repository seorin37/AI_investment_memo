import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pipelines.disclosures import chunker
from pipelines.disclosures.dart import fiscal_period_label, select_window_candidates
from pipelines.disclosures.loader import KST
import csv

from pipelines.disclosures.dart import failure_item
from pipelines.disclosures.run_all import State, seconds_until_reset, window, write_failure_files
from pipelines.disclosures.universe import build_universe, fetch_kospi_rows


def item(rcept_no, title, rcept_dt):
    return {"rcept_no": rcept_no, "report_nm": title, "rcept_dt": rcept_dt}


DEC_ITEMS = [
    item("20240311000001", "사업보고서 (2023.12)", "20240311"),
    item("20240516000001", "분기보고서 (2024.03)", "20240516"),
    item("20240814000001", "반기보고서 (2024.06)", "20240814"),
    item("20241114000001", "분기보고서 (2024.09)", "20241114"),
    item("20250311000001", "사업보고서 (2024.12)", "20250311"),
    item("20250515000001", "분기보고서 (2025.03)", "20250515"),
    item("20250814000001", "반기보고서 (2025.06)", "20250814"),
    item("20251114000001", "분기보고서 (2025.09)", "20251114"),
    item("20260310000001", "사업보고서 (2025.12)", "20260310"),
    item("20260515000001", "분기보고서 (2026.03)", "20260515"),
    item("20260814000001", "반기보고서 (2026.06)", "20260814"),
    item("20260820000001", "[기재정정]반기보고서 (2026.06)", "20260820"),
]

MAR_ITEMS = [  # 3월 결산: 6월=1분기, 9월=반기, 12월=3분기, 3월=사업
    item("20240620000001", "사업보고서 (2024.03)", "20240620"),
    item("20240814000002", "분기보고서 (2024.06)", "20240814"),
    item("20241114000002", "반기보고서 (2024.09)", "20241114"),
    item("20250214000002", "분기보고서 (2024.12)", "20250214"),
    item("20250620000002", "사업보고서 (2025.03)", "20250620"),
    item("20250814000002", "분기보고서 (2025.06)", "20250814"),
    item("20251114000002", "반기보고서 (2025.09)", "20251114"),
    item("20260213000002", "분기보고서 (2025.12)", "20260213"),
    item("20260619000002", "사업보고서 (2026.03)", "20260619"),
    item("20260814000002", "분기보고서 (2026.06)", "20260814"),
]


class WindowSelectionTest(unittest.TestCase):
    def test_december_fiscal_year_matches_fixed_periods(self):
        grouped, missing = select_window_candidates("005930", "00126380", {"A001": DEC_ITEMS}, "2024-01-01", "2026-06-30", 10)
        self.assertEqual(missing, [])
        self.assertEqual(
            sorted(period for _, period in grouped),
            ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31",
             "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"],
        )
        latest = grouped[("half", "2026-06-30")]
        self.assertEqual([r.rcept_no for r in latest], ["20260820000001", "20260814000001"])
        for (_, period), refs in grouped.items():
            self.assertEqual(refs[0].period_label, chunker.period_label(period))

    def test_march_fiscal_year_labels_follow_fiscal_quarters(self):
        grouped, _ = select_window_candidates("000000", "00000000", {"A003": MAR_ITEMS}, "2024-01-01", "2026-06-30", 10)
        self.assertEqual(len(grouped), 10)
        labels = {period: refs[0].period_label for (_, period), refs in grouped.items()}
        self.assertEqual(labels["2024-06-30"], "1분기")
        self.assertEqual(labels["2024-09-30"], "반기")
        self.assertEqual(labels["2024-12-31"], "3분기")
        self.assertEqual(labels["2025-03-31"], "사업보고서")

    def test_keeps_latest_slots_and_dedupes_across_types(self):
        grouped, _ = select_window_candidates("005930", "x", {"A001": DEC_ITEMS, "A002": DEC_ITEMS}, "2024-01-01", "2026-06-30", 3)
        self.assertEqual(sorted(p for _, p in grouped), ["2025-12-31", "2026-03-31", "2026-06-30"])
        self.assertEqual(len(grouped[("half", "2026-06-30")]), 2)

    def test_six_month_fiscal_reit_keeps_all_reports(self):
        # 롯데리츠(2026-11-09 DART 목록): 6·12월 사업보고서, 3·9월 반기보고서
        reit = [item(f"2024{i:02d}000001", t, "20240101") for i, t in enumerate([
            "사업보고서 (2023.12)", "반기보고서 (2024.03)", "사업보고서 (2024.06)", "반기보고서 (2024.09)",
            "사업보고서 (2024.12)", "반기보고서 (2025.03)", "사업보고서 (2025.06)", "반기보고서 (2025.09)",
            "사업보고서 (2025.12)", "반기보고서 (2026.03)", "사업보고서 (2026.06)"], start=1)]
        grouped, _ = select_window_candidates("330590", "x", {"A001": reit, "A002": reit}, "2024-01-01", "2026-06-30", 10)
        self.assertEqual(len(grouped), 10)
        self.assertIn(("annual", "2025-12-31"), grouped)
        self.assertEqual(grouped[("half", "2025-09-30")][0].period_label, "반기")
        self.assertEqual(grouped[("annual", "2026-06-30")][0].period_label, "사업보고서")

    def test_three_month_fiscal_reit_keeps_every_annual(self):
        # SK리츠: 사업보고서만 3개월마다
        reit = [item(f"2025{i:02d}000001", f"사업보고서 ({y}.{m:02d})", "20250101")
                for i, (y, m) in enumerate([(2024, 3), (2024, 6), (2024, 9), (2024, 12), (2025, 3), (2025, 6)], start=1)]
        grouped, _ = select_window_candidates("395400", "x", {"A001": reit}, "2024-01-01", "2026-06-30", 10)
        self.assertEqual(len(grouped), 6)
        self.assertTrue(all(refs[0].period_label == "사업보고서" for refs in grouped.values()))

    def test_fiscal_cycle(self):
        from pipelines.disclosures.dart import fiscal_cycle
        self.assertEqual(fiscal_cycle(["2024-12-31", "2025-12-31"], ["2025-06-30"]), 12)
        self.assertEqual(fiscal_cycle(["2025-03-31"], ["2024-09-30", "2025-09-30"]), 12)  # 3월 결산
        self.assertEqual(fiscal_cycle(["2025-06-30", "2025-12-31"], []), 6)
        self.assertEqual(fiscal_cycle(["2025-06-30"], ["2025-09-30"]), 6)
        self.assertEqual(fiscal_cycle(["2025-01-31", "2025-04-30", "2025-07-31"], []), 3)
        self.assertIsNone(fiscal_period_label("quarterly", "2025-09-30", 6, cycle=6))

    def test_kind_inconsistent_with_fiscal_month_is_skipped(self):
        self.assertIsNone(fiscal_period_label("half", "2024-03-31", 12))
        self.assertEqual(fiscal_period_label("quarterly", "2024-09-30", 12), "3분기")


class UniverseTest(unittest.TestCase):
    def test_preferred_shares_merge_into_common_by_corp_code(self):
        rows = [
            {"ISU_CD": "005930", "ISU_NM": "삼성전자", "MKT_NM": "KOSPI", "MKTCAP": "1,000"},
            {"ISU_CD": "005935", "ISU_NM": "삼성전자우", "MKT_NM": "KOSPI", "MKTCAP": "100"},
            {"ISU_CD": "000660", "ISU_NM": "SK하이닉스", "MKT_NM": "KOSPI", "MKTCAP": "2000"},
        ]
        companies, unmatched = build_universe(rows, {"005930": "00126380", "000660": "00164779"})
        self.assertEqual([c.symbol for c in companies], ["000660", "005930"])  # 시가총액 큰 순
        self.assertEqual([u["symbol"] for u in unmatched], ["005935"])

    def test_fetch_walks_back_to_last_trading_day(self):
        calls = []

        def fetcher(day):
            calls.append(day)
            return [{"MKT_NM": "KOSPI", "ISU_CD": "005930"}] if day == date(2026, 10, 23) else []

        day, rows = fetch_kospi_rows(date(2026, 10, 25), fetcher)
        self.assertEqual(day, date(2026, 10, 23))
        self.assertEqual(len(calls), 3)


class StateTest(unittest.TestCase):
    def test_pending_skips_done_and_errors_unless_retry(self):
        with TemporaryDirectory() as tmp:
            state = State(Path(tmp) / "state.json")
            state.companies.update({"A": {"status": "done"}, "B": {"status": "error"}})
            state.save()
            reloaded = State(Path(tmp) / "state.json")
            self.assertEqual(reloaded.pending(["A", "B", "C"], retry_failed=False), ["C"])
            self.assertEqual(reloaded.pending(["A", "B", "C"], retry_failed=True), ["B", "C"])

    def test_partial_counts_as_failed_for_retry(self):
        with TemporaryDirectory() as tmp:
            state = State(Path(tmp) / "state.json")
            state.companies.update({"A": {"status": "partial"}})
            self.assertEqual(state.pending(["A"], retry_failed=False), [])
            self.assertEqual(state.pending(["A"], retry_failed=True), ["A"])

    def test_failure_files(self):
        with TemporaryDirectory() as tmp:
            state = State(Path(tmp) / "state.json")
            item = failure_item("105560", "download", "014: 파일이 존재하지 않습니다.", period_end="2025-12-31", kind="annual", rcept_no="20260619000667")
            state.companies.update({
                "105560": {"status": "partial", "docs": 9, "failed_items": [item], "batch": 1, "updated_at": "t"},
                "999990": {"status": "done", "docs": 4, "failed_items": [], "batch": 1, "updated_at": "t"},
                "005930": {"status": "done", "docs": 10, "failed_items": [], "batch": 1, "updated_at": "t"},
            })
            count = write_failure_files(state, {"105560": "KB금융", "999990": "신규상장"}, Path(tmp), 10)
            self.assertEqual(count, 1)
            with (Path(tmp) / "failed_reports.csv").open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["기업명"], "KB금융")
            self.assertEqual(rows[0]["실패 단계"], "원문 다운로드")
            self.assertEqual(rows[0]["보고서 유형"], "사업보고서")
            with (Path(tmp) / "under_slots.csv").open(encoding="utf-8-sig") as handle:
                under = list(csv.DictReader(handle))
            self.assertEqual([(r["종목코드"], r["부족 수"]) for r in under], [("999990", "6")])

    def test_window_and_reset(self):
        start, end, slots = window({"targets": {"periods": ["2026-06-30", "2024-03-31"]}})
        self.assertEqual((start, end, slots), ("2024-01-01", "2026-06-30", 2))
        wait = seconds_until_reset(datetime(2026, 10, 29, 23, 0, tzinfo=KST))
        self.assertEqual(wait, 65 * 60)


if __name__ == "__main__":
    unittest.main()
