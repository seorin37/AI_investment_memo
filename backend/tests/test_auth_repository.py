from __future__ import annotations

import unittest

from app.auth.providers import ProviderProfile
from app.auth.repository import AuthRepository


class Result:
    def __init__(self, *, first=None, one=None, all_rows=None):
        self._first = first
        self._one = one
        self._all = all_rows or []

    def first(self):
        return self._first

    def one(self):
        return self._one

    def all(self):
        return self._all

    def mappings(self):
        return self


class ScriptedSession:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        if not self.results:
            raise AssertionError(f"unexpected SQL: {statement}")
        return self.results.pop(0)


class AuthRepositoryTest(unittest.TestCase):
    profile = ProviderProfile("google", "provider-1", "same@example.test", "새 사용자", None)

    def test_existing_provider_identity_reuses_user(self):
        db = ScriptedSession(
            [
                Result(),
                Result(first={"id": 3, "email": "old@example.test", "display_name": "기존", "bio": None, "avatar_url": None, "plan": "free", "deleted_at": None}),
                Result(all_rows=[{"provider": "google", "email": "old@example.test"}]),
            ]
        )
        user = AuthRepository(db).get_or_create_user(self.profile)
        self.assertEqual(user["id"], 3)
        self.assertEqual(len(db.calls), 3)
        self.assertIn("pg_advisory_xact_lock", db.calls[0][0])
        self.assertFalse(any("INSERT INTO users" in sql for sql, _ in db.calls))

    def test_same_email_from_another_provider_is_not_auto_merged(self):
        db = ScriptedSession(
            [
                Result(),
                Result(first=None),
                Result(),
                Result(first=(1,)),
                Result(one={"id": 9, "email": None, "display_name": "새 사용자", "bio": None, "avatar_url": None, "plan": "free", "deleted_at": None}),
                Result(),
                Result(),
            ]
        )
        user = AuthRepository(db).get_or_create_user(self.profile)
        insert_call = next((params for sql, params in db.calls if "INSERT INTO users" in sql), None)
        self.assertIsNotNone(insert_call)
        self.assertIsNone(insert_call["email"])
        self.assertEqual(user["id"], 9)
        self.assertEqual(user["providers"][0]["provider"], "google")

    def test_first_login_creates_settings_and_identity(self):
        db = ScriptedSession(
            [
                Result(),
                Result(first=None),
                Result(),
                Result(first=None),
                Result(one={"id": 11, "email": "same@example.test", "display_name": "새 사용자", "bio": None, "avatar_url": None, "plan": "free", "deleted_at": None}),
                Result(),
                Result(),
            ]
        )
        AuthRepository(db).get_or_create_user(self.profile)
        statements = "\n".join(sql for sql, _ in db.calls)
        self.assertIn("INSERT INTO users", statements)
        self.assertIn("INSERT INTO user_settings", statements)
        self.assertIn("INSERT INTO auth_identities", statements)


if __name__ == "__main__":
    unittest.main()
