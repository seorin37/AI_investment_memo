
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from backend.pipelines.market import pipeline


class TestKRXResume(unittest.TestCase):

    def test_completed_date_is_skipped(self):
        """같은 날짜를 두 번 실행하면 두 번째는 수집하지 않는다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                collection_result = {
                    "status": "success",
                    "saved_rows": 4,
                    "market_rows": 940,
                }

                with patch.object(
                    pipeline,
                    "collect_prices",
                    return_value=collection_result,
                ) as mock_collect:

                    # 첫 번째 실행: 정상 수집
                    first = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                        resume=True,
                    )

                    # 두 번째 실행: 완료 날짜 건너뛰기
                    second = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                        resume=True,
                    )

                self.assertEqual(first["success_dates"], 1)
                self.assertEqual(second["skipped_completed"], 1)
                self.assertEqual(second["total_rows"], 0)

                # 두 번 실행했지만 실제 수집 함수는 한 번만 호출
                self.assertEqual(mock_collect.call_count, 1)

                completions = pipeline.load_completions("test")
                self.assertIn("2026-10-15", completions)

    def test_resume_false_forces_collection(self):
        """resume=False이면 완료 기록이 있어도 재수집한다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                pipeline.save_completions(
                    "test",
                    {
                        "2026-10-15": {
                            "status": "success",
                            "saved_rows": 4,
                        }
                    },
                )

                with patch.object(
                    pipeline,
                    "collect_prices",
                    return_value={
                        "status": "success",
                        "saved_rows": 4,
                        "market_rows": 940,
                    },
                ) as mock_collect:

                    result = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                        resume=False,
                    )

                mock_collect.assert_called_once()
                self.assertEqual(result["success_dates"], 1)
                self.assertEqual(result["skipped_completed"], 0)

    def test_failed_date_is_not_skipped(self):
        """완료 기록이 있더라도 실패 기록이 남아 있으면 재수집한다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                pipeline.save_completions(
                    "test",
                    {"2026-10-15": {"status": "success", "saved_rows": 4}},
                )

                pipeline.save_failures(
                    "test",
                    {"2026-10-15": {"error_type": "Timeout", "error": "timeout"}},
                )

                with patch.object(
                    pipeline,
                    "collect_prices",
                    return_value={
                        "status": "success",
                        "saved_rows": 4,
                        "market_rows": 940,
                    },
                ) as mock_collect:

                    result = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                        resume=True,
                    )

                mock_collect.assert_called_once()
                self.assertEqual(result["success_dates"], 1)
                self.assertEqual(pipeline.load_failures("test"), {})

    
    def test_retry_success_updates_completion(self):
        """실패 날짜 재수집에 성공하면 완료 기록도 생성한다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                pipeline.save_failures(
                    "test",
                    {
                        "2026-10-15": {
                            "error_type": "Timeout",
                            "error": "timeout",
                        }
                    },
                )

                with patch.object(
                    pipeline,
                    "collect_prices",
                    return_value={
                        "status": "success",
                        "saved_rows": 4,
                        "market_rows": 940,
                    },
                ) as mock_collect:

                    result = pipeline.retry_failed_prices(
                        scope="test",
                        request_interval=0,
                    )

                self.assertEqual(result["success_dates"], 1)
                self.assertEqual(result["remaining_failures"], 0)
                mock_collect.assert_called_once()

                self.assertEqual(
                    pipeline.load_failures("test"),
                    {},
                )

                completions = pipeline.load_completions("test")
                self.assertEqual(
                    completions["2026-10-15"]["status"],
                    "success",
                )
                self.assertEqual(
                    completions["2026-10-15"]["saved_rows"],
                    4,
                )



if __name__ == "__main__":
    unittest.main()
