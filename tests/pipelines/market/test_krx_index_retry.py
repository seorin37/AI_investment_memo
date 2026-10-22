
import unittest
from datetime import date
from unittest.mock import Mock, patch

import requests

from backend.pipelines.market.krx import fetch_market_index_daily


class TestKRXIndexRetry(unittest.TestCase):

    def setUp(self):
        self.trade_date = date(2026, 10, 19)
        self.sample_row = {
            "BAS_DD": "20261019",
            "IDX_CLSS": "KOSPI",
            "IDX_NM": "코스피",
            "CLSPRC_IDX": "5768.01",
        }

    @patch("backend.pipelines.market.krx.time.sleep")
    @patch("backend.pipelines.market.krx.requests.get")
    def test_retry_after_429(self, mock_get, mock_sleep):
        first = Mock()
        first.status_code = 429
        first.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests",
            response=first,
        )

        second = Mock()
        second.status_code = 200
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "OutBlock_1": [self.sample_row]
        }

        mock_get.side_effect = [first, second]

        with patch(
            "backend.pipelines.market.krx.os.getenv",
            return_value="test-api-key",
        ):
            result = fetch_market_index_daily(
                self.trade_date,
                "KOSPI",
            )

        self.assertEqual(result["CLSPRC_IDX"], "5768.01")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("backend.pipelines.market.krx.time.sleep")
    @patch("backend.pipelines.market.krx.requests.get")
    def test_no_retry_on_403(self, mock_get, mock_sleep):
        response = Mock()
        response.status_code = 403
        response.raise_for_status.side_effect = requests.HTTPError(
            "403 Forbidden",
            response=response,
        )

        mock_get.return_value = response

        with patch(
            "backend.pipelines.market.krx.os.getenv",
            return_value="test-api-key",
        ):
            with self.assertRaises(requests.HTTPError):
                fetch_market_index_daily(
                    self.trade_date,
                    "KOSPI",
                )

        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("backend.pipelines.market.krx.time.sleep")
    @patch("backend.pipelines.market.krx.requests.get")
    def test_timeout_max_attempts(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.Timeout(
            "Connection timed out"
        )

        with patch(
            "backend.pipelines.market.krx.os.getenv",
            return_value="test-api-key",
        ):
            with self.assertRaises(requests.Timeout):
                fetch_market_index_daily(
                    self.trade_date,
                    "KOSPI",
                    max_attempts=3,
                )

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
