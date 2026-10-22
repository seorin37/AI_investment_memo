
import unittest
from datetime import date
from unittest.mock import Mock, patch

import requests

from backend.pipelines.market.krx import fetch_kospi_daily


class TestKRXRetry(unittest.TestCase):

    @patch("backend.pipelines.market.krx.time.sleep")
    @patch("backend.pipelines.market.krx.requests.get")
    def test_retry_after_429(self, mock_get, mock_sleep):
        limited = Mock()
        limited.status_code = 429
        limited.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests",
            response=limited,
        )

        success = Mock()
        success.status_code = 200
        success.raise_for_status.return_value = None
        success.json.return_value = {"OutBlock_1": [{"ISU_CD": "005930"}]}

        mock_get.side_effect = [limited, success]

        result = fetch_kospi_daily(date(2026, 10, 19))

        self.assertEqual(len(result), 1)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("backend.pipelines.market.krx.time.sleep")
    @patch("backend.pipelines.market.krx.requests.get")
    def test_timeout_max_attempts(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.Timeout("timeout")

        with self.assertRaises(requests.Timeout):
            fetch_kospi_daily(date(2026, 10, 19), max_attempts=3)

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("backend.pipelines.market.krx.requests.get")
    def test_no_retry_on_403(self, mock_get):
        forbidden = Mock()
        forbidden.status_code = 403
        forbidden.raise_for_status.side_effect = requests.HTTPError(
            "403 Forbidden",
            response=forbidden,
        )

        mock_get.return_value = forbidden

        with self.assertRaises(requests.HTTPError):
            fetch_kospi_daily(date(2026, 10, 19))

        self.assertEqual(mock_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
