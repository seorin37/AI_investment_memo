from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import make_url

from app import db as app_db
from pipelines.common import db


class CommonDatabaseRoleTest(unittest.TestCase):
    def tearDown(self):
        db.get_engine.cache_clear()
        db.get_read_engine.cache_clear()

    def test_write_url_uses_database_url(self):
        env = {"DATABASE_URL": "write-dsn", "READONLY_DATABASE_URL": "read-dsn"}
        self.assertEqual(db.database_url(env), "write-dsn")

    def test_read_url_prefers_readonly_and_falls_back(self):
        both = {"DATABASE_URL": "write-dsn", "READONLY_DATABASE_URL": "read-dsn"}
        legacy = {"DATABASE_URL": "write-dsn"}
        self.assertEqual(db.read_database_url(both), "read-dsn")
        self.assertEqual(db.read_database_url(legacy), "write-dsn")

    def test_role_engines_are_created_from_separate_urls(self):
        write_engine = object()
        read_engine = object()
        with (
            mock.patch.object(db, "database_url", return_value="write-dsn"),
            mock.patch.object(db, "read_database_url", return_value="read-dsn"),
            mock.patch.object(db, "create_engine", side_effect=[write_engine, read_engine]) as create,
        ):
            self.assertIs(db.get_engine(), write_engine)
            self.assertIs(db.get_read_engine(), read_engine)

        self.assertEqual(create.call_args_list[0].args, ("write-dsn",))
        self.assertEqual(create.call_args_list[1].args, ("read-dsn",))

    def test_read_dsn_prefers_readonly_and_falls_back(self):
        both = {"DATABASE_URL": "write-dsn", "READONLY_DATABASE_URL": "read-dsn"}
        legacy = {"DATABASE_URL": "write-dsn"}
        self.assertEqual(db.get_read_dsn(both), "read-dsn")
        self.assertEqual(db.get_read_dsn(legacy), "write-dsn")

    def test_component_dsn_quotes_special_characters(self):
        password = "reserved @:# value"
        dsn = db.get_dsn(
            {
                "POSTGRES_HOST": "db.invalid",
                "POSTGRES_PORT": "5432",
                "POSTGRES_USER": "writer",
                "POSTGRES_PASSWORD": password,
                "POSTGRES_DB": "memos",
            }
        )
        self.assertEqual(conninfo_to_dict(dsn)["password"], password)

    def test_sqlalchemy_url_accepts_percent_encoded_password(self):
        parsed = make_url(
            "postgresql+psycopg://writer:reserved%40%3A%23value@db.invalid/memos"
        )
        self.assertEqual(parsed.password, "reserved@:#value")

    def test_dotenv_interpolates_role_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "DB_HOST=db.invalid\n"
                "DB_NAME=memos\n"
                "READONLY_DATABASE_URL=postgresql+psycopg://reader@${DB_HOST}/${DB_NAME}\n",
                encoding="utf-8",
            )
            values = dotenv_values(path)
        self.assertEqual(
            db.read_database_url(values),
            "postgresql+psycopg://reader@db.invalid/memos",
        )

    def test_missing_urls_raise_sanitized_errors(self):
        for resolver in (db.database_url, db.read_database_url):
            with self.subTest(resolver=resolver.__name__):
                with self.assertRaises(db.DatabaseConfigError) as caught:
                    resolver({})
                self.assertNotIn("://", str(caught.exception))


class FastApiSessionRoleTest(unittest.TestCase):
    def test_app_url_selection(self):
        env = {"DATABASE_URL": "write-dsn", "READONLY_DATABASE_URL": "read-dsn"}
        self.assertEqual(app_db.write_database_url(env), "write-dsn")
        self.assertEqual(app_db.read_database_url(env), "read-dsn")
        self.assertEqual(app_db.read_database_url({"DATABASE_URL": "write-dsn"}), "write-dsn")

    def test_write_session_commits(self):
        session = mock.MagicMock()
        with mock.patch.object(app_db, "SessionLocal", return_value=session):
            with app_db.get_session() as yielded:
                self.assertIs(yielded, session)
        session.commit.assert_called_once_with()
        session.close.assert_called_once_with()

    def test_read_session_does_not_commit(self):
        session = mock.MagicMock()
        with mock.patch.object(app_db, "ReadSessionLocal", return_value=session):
            with app_db.get_read_session() as yielded:
                self.assertIs(yielded, session)
        session.commit.assert_not_called()
        session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
