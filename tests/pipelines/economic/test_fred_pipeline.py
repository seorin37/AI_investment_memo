
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import call, patch

from backend.pipelines.economic import pipeline


class TestFREDPipeline(unittest.TestCase):

    def test_partial_failure_and_resume(self):
        """실패한 FRED 지표만 재수집하고 완료한 지표는 건너뛴다."""

        start = date(2026, 10, 19)
        end = date(2026, 10, 20)

        series = {
            "US_TREASURY_2Y": "DGS2",
            "US_TREASURY_10Y": "DGS10",
        }

        fetch_count = {"DGS10": 0}

        def fake_fetch(series_id, start_date, end_date):
            if series_id == "DGS10":
                fetch_count["DGS10"] += 1

                if fetch_count["DGS10"] == 1:
                    raise TimeoutError("가상 FRED API 타임아웃")

            return [
                {"date": "2026-10-19", "value": "5.10"}
            ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    pipeline, "FRED_STATE_DIR", Path(temp_dir)
                ),
                patch.object(
                    pipeline, "FRED_SERIES", series
                ),
                patch.object(
                    pipeline, "fetch_fred_series",
                    side_effect=fake_fetch,
                ) as mock_fetch,
                patch.object(
                    pipeline, "save_economic_observations",
                    return_value=1,
                ) as mock_save,
            ):
                first = pipeline.backfill_fred(
                    start,
                    end,
                    request_interval=0,
                )

                self.assertEqual(first["success"], 1)
                self.assertEqual(len(first["failed"]), 1)
                self.assertEqual(first["remaining_failures"], 1)

                second = pipeline.backfill_fred(
                    start,
                    end,
                    request_interval=0,
                )

                self.assertEqual(second["success"], 1)
                self.assertEqual(second["skipped_completed"], 1)
                self.assertEqual(second["remaining_failures"], 0)

                third = pipeline.backfill_fred(
                    start,
                    end,
                    request_interval=0,
                )

                self.assertEqual(third["success"], 0)
                self.assertEqual(third["skipped_completed"], 2)

                self.assertEqual(
                    mock_fetch.call_args_list,
                    [
                        call("DGS2", start, end),
                        call("DGS10", start, end),
                        call("DGS10", start, end),
                    ],
                )

                self.assertEqual(mock_save.call_count, 2)

                completed = pipeline.load_fred_state("completed")
                failed = pipeline.load_fred_state("failed")

                self.assertEqual(len(completed), 2)
                self.assertEqual(failed, {})


if __name__ == "__main__":
    unittest.main()
