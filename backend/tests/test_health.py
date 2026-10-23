import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import main


class HealthApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

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
        error_message = "database unavailable"

        with mock.patch.object(
            main.psycopg,
            "connect",
            side_effect=main.psycopg.OperationalError(error_message),
        ):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn(error_message, response.json()["detail"])

    def test_health_db_connection_arguments_from_environment(self):
        connect, _ = self._connection_mock((1,))
        environment = {
            "POSTGRES_HOST": "db.example.test",
            "POSTGRES_PORT": "6543",
            "POSTGRES_USER": "test-user",
            "POSTGRES_PASSWORD": "test-password",
            "POSTGRES_DB": "test-db",
        }

        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(main.psycopg, "connect", connect),
        ):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        connect.assert_called_once_with(
            host="db.example.test",
            port="6543",
            user="test-user",
            password="test-password",
            dbname="test-db",
            connect_timeout=3,
        )

    def test_health_db_connection_argument_defaults(self):
        connect, _ = self._connection_mock((1,))

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(main.psycopg, "connect", connect),
        ):
            response = self.client.get("/health/db")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(connect.call_args.kwargs["host"], "localhost")
        self.assertEqual(connect.call_args.kwargs["port"], "5432")

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
