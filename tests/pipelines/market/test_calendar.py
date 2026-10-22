
import unittest
from datetime import date
from unittest.mock import patch

from backend.pipelines.market import pipeline
from backend.pipelines.market.calendar import is_krx_trading_day


class TestKRXCalendar(unittest.TestCase):

    def test_trading_days_and_holidays(self):
        self.assertFalse(is_krx_trading_day(date(2020, 1, 1)))
        self.assertTrue(is_krx_trading_day(date(2020, 1, 2)))
        self.assertFalse(is_krx_trading_day(date(2026, 1, 1)))
        self.assertFalse(is_krx_trading_day(date(2026, 10, 17)))
        self.assertTrue(is_krx_trading_day(date(2026, 10, 19)))

    def test_out_of_calendar_range(self):
        with self.assertRaises(ValueError):
            is_krx_trading_day(date(2027, 1, 4))

    def test_holiday_does_not_call_krx_api(self):
        # 실패 기록은 임시 메모리 데이터로 대체
        with (
            patch.object(pipeline, "load_failures", return_value={}),
            patch.object(pipeline, "save_failures"),
            patch.object(pipeline, "collect_prices") as mock_collect,
        ):
            result = pipeline.backfill_prices(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
                symbols=pipeline.TEST_SYMBOLS,
                request_interval=0,
                scope="test",
            )

        mock_collect.assert_not_called()
        self.assertEqual(result["success_dates"], 0)
        self.assertEqual(result["remaining_failures"], 0)


if __name__ == "__main__":
    unittest.main()
