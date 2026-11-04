import unittest

from fastapi.testclient import TestClient

from app.main import app


class CookieCsrfTest(unittest.TestCase):
    def test_cookie_authenticated_mutation_requires_matching_header(self):
        with TestClient(app) as client:
            client.cookies.set("memos_access", "cookie-token")
            client.cookies.set("memos_csrf", "expected")
            response = client.post("/api/v1/auth/logout")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "CSRF 검증에 실패했습니다.")

            response = client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"}
            )
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
