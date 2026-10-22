
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.pipelines.market import pipeline


class TestKRXRecovery(unittest.TestCase):

    def test_failure_then_recovery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            failure_dir = Path(temp_dir)

            with patch.object(pipeline, "FAILURE_DIR", failure_dir):
                # 1. 가상의 실패 기록 생성
                initial_failures = {
                    "2026-10-15": {
                        "error_type": "Timeout",
                        "error": "Connection timed out",
                    }
                }

                pipeline.save_failures("test", initial_failures)

                # 2. 기존 실패 기록 확인
                self.assertEqual(
                    pipeline.load_failures("test"),
                    initial_failures,
                )

                # 3. API 호출과 DB 저장을 가짜로 대체
                with patch.object(
                    pipeline, "collect_prices", return_value={
                                                                "status": "success",
                                                                "saved_rows": 4,
                                                                "market_rows": 940,
                                                            }
                ) as mock_collect:

                    result = pipeline.retry_failed_prices(
                        scope="test",
                        request_interval=0,
                    )

                # 4. 실패 날짜만 수집했는지 확인
                mock_collect.assert_called_once()
                self.assertEqual(
                    mock_collect.call_args.kwargs["trade_date"].isoformat(),
                    "2026-10-15",
                )
                self.assertEqual(
                    mock_collect.call_args.kwargs["symbols"],
                    pipeline.TEST_SYMBOLS,
                )

                # 5. 재수집 결과 확인
                self.assertEqual(result["attempted_dates"], 1)
                self.assertEqual(result["success_dates"], 1)
                self.assertEqual(result["total_rows"], 4)

                # 6. 성공한 날짜의 실패 기록 삭제 확인
                self.assertEqual(pipeline.load_failures("test"), {})

    def test_empty_response_keeps_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                pipeline.save_failures(
                    "test",
                    {
                        "2026-10-15": {
                            "error_type": "Timeout",
                            "error": "Previous failure",
                        }
                    },
                )

                with patch.object(
                    pipeline, "collect_prices", return_value={
                                                                "status": "empty_market",
                                                                "saved_rows": 0,
                                                                "market_rows": 0,
                                                            }
                ):
                    result = pipeline.retry_failed_prices(
                        scope="test",
                        request_interval=0,
                    )

                self.assertEqual(result["empty_dates"], ["2026-10-15"])
                self.assertEqual(result["remaining_failures"], 1)
                self.assertIn(
                    "2026-10-15",
                    pipeline.load_failures("test"),
                )

    
    def test_backfill_failure_is_recorded(self):
        from datetime import date

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                with patch.object(
                    pipeline,
                    "collect_prices",
                    side_effect=TimeoutError("가상 API 타임아웃"),
                ):
                    result = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                    )

                failures = pipeline.load_failures("test")

                self.assertEqual(result["success_dates"], 0)
                self.assertEqual(
                    result["failed_dates"],
                    ["2026-10-15"],
                )
                self.assertEqual(result["remaining_failures"], 1)
                self.assertEqual(
                    failures["2026-10-15"]["error_type"],
                    "TimeoutError",
                )
    
    def test_no_matching_symbols_is_not_failure(self):
        from datetime import date

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(pipeline, "FAILURE_DIR", Path(temp_dir)):
                collection_result = {
                    "status": "no_matching_symbols",
                    "saved_rows": 0,
                    "market_rows": 900,
                }

                with patch.object(
                    pipeline,
                    "collect_prices",
                    return_value=collection_result,
                ):
                    result = pipeline.backfill_prices(
                        start_date=date(2026, 10, 15),
                        end_date=date(2026, 10, 15),
                        symbols=pipeline.TEST_SYMBOLS,
                        request_interval=0,
                        scope="test",
                    )

                self.assertEqual(result["no_matching_dates"], 1)
                self.assertEqual(result["success_dates"], 0)
                self.assertEqual(result["remaining_failures"], 0)
                self.assertEqual(pipeline.load_failures("test"), {})



if __name__ == "__main__":
    unittest.main()
