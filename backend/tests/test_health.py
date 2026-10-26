import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import main


class HealthApiTest(unittest.TestCase):
    def setUp(self):
        self.read_dsn = mock.patch.object(main, "get_read_dsn", return_value="readonly-dsn")
        self.read_dsn.start()
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.read_dsn.stop()

    @staticmethod
    def _connection_mock(fetchone_result):
        connection = mock.MagicMock()
        connection.execute.return_value.fetchone.return_value = fetchone_result
        connect = mock.MagicMock()
        connect.return_value.__enter__.return_value = connection
        return connect, connection

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_db_with_pgvector(self):
        connect, _ = self._connection_mock((1,))

        with mock.patch.object(main.psycopg, "connect", connect):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "pgvector": True})

    def test_health_db_without_pgvector(self):
        connect, _ = self._connection_mock(None)

        with mock.patch.object(main.psycopg, "connect", connect):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "pgvector": False})

    def test_health_db_connection_failure(self):
        sensitive_error = "could not connect to secret-host as secret-user"

        with mock.patch.object(
            main.psycopg,
            "connect",
            side_effect=main.psycopg.OperationalError(sensitive_error),
        ):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "error", "detail": "database health check failed"},
        )
        self.assertNotIn("secret-host", response.text)
        self.assertNotIn("secret-user", response.text)

    def test_health_db_uses_readonly_dsn(self):
        connect, _ = self._connection_mock((1,))

        with mock.patch.object(main.psycopg, "connect", connect):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        connect.assert_called_once_with("readonly-dsn", connect_timeout=3)

    def test_health_db_missing_configuration_is_sanitized(self):
        connect = mock.MagicMock()

        with (
            mock.patch.object(main, "get_read_dsn", return_value=None),
            mock.patch.object(main.psycopg, "connect", connect),
        ):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "database health check failed")
        connect.assert_not_called()

    def test_health_db_queries_pgvector_extension(self):
        connect, connection = self._connection_mock((1,))

        with mock.patch.object(main.psycopg, "connect", connect):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        connection.execute.assert_called_once()
        query = connection.execute.call_args.args[0]
        self.assertIn("pg_extension", query)
        self.assertIn("'vector'", query)


if __name__ == "__main__":
    unittest.main()
