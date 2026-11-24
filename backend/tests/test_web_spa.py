"""웹 정적 빌드 서빙 (같은 주소에서 웹 + API) 테스트."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import mount_web, web_dist_dir


class WebSpaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.dist = root / "dist"
        (self.dist / "_expo" / "static" / "js" / "web").mkdir(parents=True)
        (self.dist / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
        (self.dist / "favicon.ico").write_bytes(b"ico")
        (self.dist / "_expo" / "static" / "js" / "web" / "entry-abc.js").write_text("bundle", encoding="utf-8")
        (root / "secret.txt").write_text("outside", encoding="utf-8")

        app = FastAPI()

        @app.get("/api/v1/ping")
        def ping():
            return {"ok": True}

        @app.get("/health")
        def health():
            return {"status": "ok"}

        self.mounted = mount_web(app, self.dist)
        self.client = TestClient(app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_mounted(self):
        self.assertTrue(self.mounted)

    def test_api_and_health_routes_still_win(self):
        self.assertEqual(self.client.get("/api/v1/ping").json(), {"ok": True})
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_unknown_api_path_is_json_404_not_index(self):
        res = self.client.get("/api/v1/nope")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {"detail": "Not Found"})

    def test_spa_routes_fall_back_to_index(self):
        for path in ("/", "/auth/callback", "/auth/callback?status=success", "/stocks/005930"):
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.text, "<html>INDEX</html>")
                self.assertEqual(res.headers["cache-control"], "no-cache")

    def test_static_files_served_and_bundles_cached(self):
        self.assertEqual(self.client.get("/favicon.ico").content, b"ico")
        res = self.client.get("/_expo/static/js/web/entry-abc.js")
        self.assertEqual(res.text, "bundle")
        self.assertIn("immutable", res.headers["cache-control"])

    def test_path_traversal_does_not_escape_dist(self):
        res = self.client.get("/..%2Fsecret.txt")
        self.assertNotEqual(res.text, "outside")

    def test_not_mounted_without_build(self):
        app = FastAPI()
        self.assertFalse(mount_web(app, Path(self._tmp.name) / "missing"))
        self.assertEqual(TestClient(app).get("/auth/callback").status_code, 404)

    def test_web_dist_dir_env(self):
        self.assertEqual(web_dist_dir({"WEB_DIST_DIR": "/srv/web"}), Path("/srv/web"))
        self.assertTrue(str(web_dist_dir({})).endswith("frontend/dist"))


if __name__ == "__main__":
    unittest.main()
