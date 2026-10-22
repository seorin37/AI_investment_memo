
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, call

from backend.pipelines.market import pipeline


class TestKRXIndexPipeline(unittest.TestCase):

    def test_partial_failure_and_resume(self):
        """KOSDAQ만 실패하면 다음 실행에서 KOSDAQ만 재수집한다."""

        target_date = date(2026, 10, 19)

        # 첫 실행: KOSPI 성공, KOSDAQ 실패
        # 두 번째 실행: KOSDAQ 성공
        api_responses = [
            {"market": "KOSPI"},
            TimeoutError("가상 KOSDAQ API 타임아웃"),
            {"market": "KOSDAQ"},
        ]

        def fake_normalize(raw):
            return {
                "market": raw["market"],
                "trade_date": target_date,
                "close": 100,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)),
                patch.object(
                    pipeline,
                    "fetch_market_index_daily",
                    side_effect=api_responses,
                ) as mock_fetch,
                patch.object(
                    pipeline,
                    "normalize_market_index",
                    side_effect=fake_normalize,
                ),
                patch.object(
                    pipeline,
                    "save_market_index",
                    return_value=1,
                ) as mock_save,
            ):
                # 1. 첫 번째 수집
                first = pipeline.backfill_market_indices(
                    target_date,
                    target_date,
                    request_interval=0,
                    resume=True,
                )

                self.assertEqual(first["success"], 1)
                self.assertEqual(first["remaining_failures"], 1)
                self.assertEqual(
                    first["failed"],
                    ["2026-10-19:KOSDAQ"],
                )

                # 2. 다시 실행하여 실패 지수만 복구
                second = pipeline.backfill_market_indices(
                    target_date,
                    target_date,
                    request_interval=0,
                    resume=True,
                )

                self.assertEqual(second["success"], 1)
                self.assertEqual(second["skipped_completed"], 1)
                self.assertEqual(second["remaining_failures"], 0)

                # 3. API 호출 순서 확인
                self.assertEqual(
                    mock_fetch.call_args_list,
                    [
                        call(trade_date=target_date, market="KOSPI"),
                        call(trade_date=target_date, market="KOSDAQ"),
                        call(trade_date=target_date, market="KOSDAQ"),
                    ],
                )

                # 실제 저장 함수는 성공한 두 번만 호출
                self.assertEqual(mock_save.call_count, 2)

                # 4. 최종 완료·실패 기록 확인
                completed = pipeline.load_index_state("completed")
                failed = pipeline.load_index_state("failed")

                self.assertIn("2026-10-19:KOSPI", completed)
                self.assertIn("2026-10-19:KOSDAQ", completed)
                self.assertEqual(failed, {})


if __name__ == "__main__":
    unittest.main()
