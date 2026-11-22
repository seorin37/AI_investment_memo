"""약관 동의 API (GET/POST /me/terms, 0022 user_terms_consents) — 중앙 DB 없이 메모리 저장소.

account 쪽에는 실제 DB 통합 테스트 패턴(*_TEST_DATABASE_URL)이 없어 여기서도 쓰지 않는다.
SQL 은 RecordingSession 으로 문장만 확인한다 (ON CONFLICT · withdrawn_at 조건).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.account.defaults import REQUIRED_TERMS, TERMS_VERSION
from app.account.repository import AccountRepository
from app.account.routes import get_account_command_service, get_account_query_service, router
from app.account.schemas import TermsAgree
from app.account.service import AccountService, TermsError
from app.auth.routes import get_current_user

T0 = datetime(2026, 11, 22, 3, 0, tzinfo=timezone.utc)


class FakeTermsRepo:
    """user_terms_consents 흉내: (user_id, kind, version) UNIQUE, ON CONFLICT DO NOTHING."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.inserts = 0

    def list_terms_consents(self, user_id):
        return [
            {"kind": r["kind"], "version": r["version"], "agreed_at": r["agreed_at"]}
            for r in self.rows
            if r["user_id"] == user_id and r["withdrawn_at"] is None
        ]

    def insert_terms_consents(self, user_id, items):
        self.inserts += 1
        for kind, version in items:
            if any(r["user_id"] == user_id and r["kind"] == kind and r["version"] == version for r in self.rows):
                continue
            self.rows.append({"user_id": user_id, "kind": kind, "version": version,
                              "agreed_at": T0 + timedelta(seconds=len(self.rows)), "withdrawn_at": None})

    def count(self, user_id):
        return sum(1 for r in self.rows if r["user_id"] == user_id)


def current_body():
    return {"items": [{"kind": k, "version": TERMS_VERSION} for k in REQUIRED_TERMS]}


class TermsApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeTermsRepo()
        service = AccountService(self.repo, auth_repo=None)
        self.user = {"id": "7"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_account_query_service] = lambda: service
        app.dependency_overrides[get_account_command_service] = lambda: service
        self.client = TestClient(app)

    def test_before_agreeing_get_is_incomplete_with_current_required(self):
        res = self.client.get("/api/v1/me/terms")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            {
                "required": [{"kind": k, "version": TERMS_VERSION} for k in ("age", "service", "invest")],
                "agreed": [],
                "complete": False,
            },
        )

    def test_first_agree_completes_and_get_matches(self):
        res = self.client.post("/api/v1/me/terms", json=current_body())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["complete"])
        self.assertEqual([(a["kind"], a["version"]) for a in body["agreed"]],
                         [(k, TERMS_VERSION) for k in REQUIRED_TERMS])
        self.assertTrue(all(a["agreed_at"].startswith("2026-11-22T") for a in body["agreed"]))
        self.assertEqual(self.client.get("/api/v1/me/terms").json(), body)

    def test_same_request_twice_keeps_one_row_per_kind(self):
        self.client.post("/api/v1/me/terms", json=current_body())
        res = self.client.post("/api/v1/me/terms", json=current_body())
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["complete"])
        self.assertEqual(self.repo.count(7), len(REQUIRED_TERMS))

    def test_missing_required_is_422_and_saves_nothing(self):
        body = {"items": [{"kind": "age", "version": TERMS_VERSION}, {"kind": "service", "version": TERMS_VERSION}]}
        res = self.client.post("/api/v1/me/terms", json=body)
        self.assertEqual(res.status_code, 422)
        self.assertIn("invest", res.json()["detail"])
        self.assertEqual(self.repo.rows, [])

    def test_old_version_is_422(self):
        body = current_body()
        body["items"][1]["version"] = "2026-01-01"
        res = self.client.post("/api/v1/me/terms", json=body)
        self.assertEqual(res.status_code, 422)
        self.assertIn("버전", res.json()["detail"])
        self.assertEqual(self.repo.rows, [])

    def test_unknown_kind_is_422(self):
        body = current_body()
        body["items"].append({"kind": "marketing", "version": TERMS_VERSION})
        res = self.client.post("/api/v1/me/terms", json=body)
        self.assertEqual(res.status_code, 422)
        self.assertIn("marketing", res.json()["detail"])

    def test_bad_body_shape_is_422(self):
        for body in ({}, {"items": []}, {"items": [{"kind": "age"}]}, {"items": current_body()["items"], "x": 1}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/me/terms", json=body).status_code, 422)

    def test_users_do_not_mix(self):
        self.client.post("/api/v1/me/terms", json=current_body())
        self.user = {"id": "8"}
        other = self.client.get("/api/v1/me/terms").json()
        self.assertFalse(other["complete"])
        self.assertEqual(other["agreed"], [])
        self.user = {"id": "7"}
        self.assertTrue(self.client.get("/api/v1/me/terms").json()["complete"])

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_account_query_service] = lambda: None
        app.dependency_overrides[get_account_command_service] = lambda: None
        from app.auth.routes import get_auth_service

        app.dependency_overrides[get_auth_service] = lambda: None
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/me/terms").status_code, 401)
        self.assertEqual(client.post("/api/v1/me/terms", json=current_body()).status_code, 401)


class TermsServiceTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeTermsRepo()
        self.service = AccountService(self.repo, auth_repo=None)

    def test_old_version_rows_are_listed_but_do_not_complete(self):
        for kind in REQUIRED_TERMS:
            self.repo.rows.append({"user_id": 7, "kind": kind, "version": "2026-01-01", "agreed_at": T0, "withdrawn_at": None})
        got = self.service.get_terms(7)
        self.assertEqual(len(got["agreed"]), 3)
        self.assertFalse(got["complete"])

    def test_withdrawn_rows_are_hidden_and_do_not_complete(self):
        for kind in REQUIRED_TERMS:
            self.repo.rows.append({"user_id": 7, "kind": kind, "version": TERMS_VERSION, "agreed_at": T0,
                                   "withdrawn_at": T0 if kind == "invest" else None})
        got = self.service.get_terms(7)
        self.assertEqual([a["kind"] for a in got["agreed"]], ["age", "service"])
        self.assertFalse(got["complete"])

    def test_errors_do_not_write(self):
        with self.assertRaises(TermsError):
            self.service.agree_terms(7, TermsAgree.model_validate({"items": [{"kind": "age", "version": TERMS_VERSION}]}))
        self.assertEqual(self.repo.inserts, 0)

    def test_duplicate_items_in_one_request_insert_once(self):
        body = current_body()
        body["items"].append({"kind": "age", "version": TERMS_VERSION})
        self.service.agree_terms(7, TermsAgree.model_validate(body))
        self.assertEqual(self.repo.count(7), 3)


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return self

    def mappings(self):
        return self

    def all(self):
        return []


class TermsRepositorySqlTest(unittest.TestCase):
    def test_insert_uses_on_conflict_do_nothing_and_is_required(self):
        session = RecordingSession()
        AccountRepository(session).insert_terms_consents(7, [("age", TERMS_VERSION), ("service", TERMS_VERSION)])
        sql, params = session.calls[0]
        self.assertIn("INSERT INTO user_terms_consents (user_id, kind, version, is_required)", sql)
        self.assertIn("ON CONFLICT (user_id, kind, version) DO NOTHING", sql)
        self.assertIn("true", sql)
        self.assertEqual(params, [{"user_id": 7, "kind": "age", "version": TERMS_VERSION},
                                  {"user_id": 7, "kind": "service", "version": TERMS_VERSION}])

    def test_list_filters_user_and_withdrawn(self):
        session = RecordingSession()
        AccountRepository(session).list_terms_consents(7)
        sql, params = session.calls[0]
        self.assertIn("WHERE user_id = :user_id AND withdrawn_at IS NULL", sql)
        self.assertEqual(params, {"user_id": 7})

    def test_empty_insert_does_not_touch_db(self):
        session = RecordingSession()
        AccountRepository(session).insert_terms_consents(7, [])
        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()
