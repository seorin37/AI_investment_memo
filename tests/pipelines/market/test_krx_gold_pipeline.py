
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import call, patch

from backend.pipelines.market import pipeline


class TestKRXGoldPipeline(unittest.TestCase):

    def test_partial_failure_and_resume(self):
        """첫 실행에서 실패하면 다음 실행에서 해당 날짜만 재수집한다."""

        test_date = date(2026, 10, 19)

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)),
                patch.object(
                    pipeline,
                    "is_krx_trading_day",
                    return_value=True,
                ),
                patch.object(
                    pipeline,
                    "fetch_gold_daily",
                    side_effect=[
                        TimeoutError("가상 금 API 타임아웃"),
                        {"ISU_CD": "04020000"},
                    ],
                ) as mock_fetch,
                patch.object(
                    pipeline,
                    "normalize_gold_row",
                    return_value={
                        "product_code": "04020000",
                        "trade_date": test_date,
                        "close": 178960,
                    },
                ),
                patch.object(
                    pipeline,
                    "save_gold_price",
                    return_value=1,
                ) as mock_save,
            ):
                # 첫 번째 실행: API 호출 실패
                first = pipeline.backfill_gold_prices(
                    test_date,
                    test_date,
                    request_interval=0,
                )

                self.assertEqual(first["success"], 0)
                self.assertEqual(first["failed"], ["2026-10-19"])
                self.assertEqual(first["remaining_failures"], 1)

                # 두 번째 실행: 실패했던 날짜 재수집
                second = pipeline.backfill_gold_prices(
                    test_date,
                    test_date,
                    request_interval=0,
                )

                self.assertEqual(second["success"], 1)
                self.assertEqual(second["remaining_failures"], 0)

                # 세 번째 실행: 성공한 날짜는 건너뛰기
                third = pipeline.backfill_gold_prices(
                    test_date,
                    test_date,
                    request_interval=0,
                )

                self.assertEqual(third["success"], 0)
                self.assertEqual(third["skipped_completed"], 1)

                # API는 첫 번째·두 번째 실행에서만 호출
                self.assertEqual(
                    mock_fetch.call_args_list,
                    [call(test_date), call(test_date)],
                )

                # DB 저장은 성공한 두 번째 실행에서만 수행
                self.assertEqual(mock_save.call_count, 1)

                completed = pipeline.load_gold_state("completed")
                failed = pipeline.load_gold_state("failed")

                self.assertIn("2026-10-19", completed)
                self.assertEqual(failed, {})


if __name__ == "__main__":
    unittest.main()
