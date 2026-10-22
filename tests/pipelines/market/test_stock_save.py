
import unittest
from unittest.mock import MagicMock, patch

from backend.pipelines.market import pipeline


class TestStockSave(unittest.TestCase):

    def test_stocks_and_prices_same_transaction(self):
        """종목 등록과 주가 저장이 하나의 트랜잭션에서 실행되는지 확인."""

        raw_rows = [
            {
                "MKT_NM": "KOSPI",
                "ISU_CD": "005930",
                "ISU_NM": "삼성전자",
                "BAS_DD": "20261019",
                "TDD_OPNPRC": "100,000",
                "TDD_HGPRC": "102,000",
                "TDD_LWPRC": "99,000",
                "TDD_CLSPRC": "101,000",
                "ACC_TRDVOL": "1000000",
                "ACC_TRDVAL": "100000000000",
                "MKTCAP": "600000000000000",
                "LIST_SHRS": "5969782550",
            }
        ]

        mock_connection = MagicMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_connection

        with (
            patch.object(pipeline, "create_engine", return_value=mock_engine),
            patch.object(pipeline.os, "getenv", return_value="postgresql://test"),
        ):
            saved = pipeline.save_stocks_and_prices(raw_rows)

        self.assertEqual(saved, 1)

        # 하나의 트랜잭션에서 두 쿼리 실행
        mock_engine.begin.assert_called_once()
        self.assertEqual(mock_connection.execute.call_count, 2)

        # 첫 번째 쿼리: stocks INSERT
        stock_stmt = str(mock_connection.execute.call_args_list[0].args[0])
        self.assertIn("INSERT INTO stocks", stock_stmt)

        # 두 번째 쿼리: prices_daily UPSERT
        price_stmt = str(mock_connection.execute.call_args_list[1].args[0])
        self.assertIn("INSERT INTO prices_daily", price_stmt)
        self.assertIn("ON CONFLICT", price_stmt)

        mock_engine.dispose.assert_called_once()

    def test_empty_rows_do_not_access_database(self):
        """빈 입력이면 DB에 연결하지 않는다."""

        with patch.object(pipeline, "create_engine") as mock_create:
            saved = pipeline.save_stocks_and_prices([])

        self.assertEqual(saved, 0)
        mock_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
