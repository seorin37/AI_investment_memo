
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import call, patch

from backend.pipelines.economic import pipeline


class TestECOSPipeline(unittest.TestCase):

    def test_partial_failure_and_resume(self):
        """실패한 지표만 재수집하고 완료한 지표는 건너뛴다."""

        start = date(2026, 10, 1)
        end = date(2026, 10, 21)

        series = {
            "USD_KRW": "731Y003/0000003",
            "KR_GOV_3Y": "817Y002/010200000",
        }

        def fake_fetch(series_code, start_date, end_date):
            if series_code == series["KR_GOV_3Y"]:
                if fake_fetch.gov_failed is False:
                    fake_fetch.gov_failed = True
                    raise TimeoutError("가상 ECOS 타임아웃")

            return [{
                "TIME": "20261001",
                "DATA_VALUE": "100",
            }]

        fake_fetch.gov_failed = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    pipeline,
                    "ECOS_STATE_DIR",
                    Path(temp_dir),
                ),
                patch.object(pipeline, "ECOS_SERIES", series),
                patch.object(
                    pipeline,
                    "fetch_ecos_series",
                    side_effect=fake_fetch,
                ) as mock_fetch,
                patch.object(
                    pipeline,
                    "save_economic_observations",
                    return_value=1,
                ) as mock_save,
            ):
                first = pipeline.backfill_ecos(
                    start,
                    end,
                    request_interval=0,
                )

                self.assertEqual(first["success"], 1)
                self.assertEqual(len(first["failed"]), 1)
                self.assertEqual(first["remaining_failures"], 1)

                second = pipeline.backfill_ecos(
                    start,
                    end,
                    request_interval=0,
                )

                self.assertEqual(second["success"], 1)
                self.assertEqual(second["skipped_completed"], 1)
                self.assertEqual(second["remaining_failures"], 0)

                self.assertEqual(mock_fetch.call_count, 3)
                self.assertEqual(mock_save.call_count, 2)

                completed = pipeline.load_ecos_state("completed")
                failed = pipeline.load_ecos_state("failed")

                self.assertEqual(len(completed), 2)
                self.assertEqual(failed, {})


if __name__ == "__main__":
    unittest.main()
