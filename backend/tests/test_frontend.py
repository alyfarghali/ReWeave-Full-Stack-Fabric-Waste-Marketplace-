import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import support  # noqa: F401  (puts the app on sys.path)

from app.core.frontend import mount_frontend


class FrontendMountTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        (root / "index.html").write_text("<div id=root></div>")
        (root / "favicon.png").write_bytes(b"png")

        app = FastAPI()

        @app.get("/api/health")
        def health():
            return {"status": "ok"}

        mount_frontend(app, self.dir.name)
        self.client = TestClient(app)

    def tearDown(self):
        self.dir.cleanup()

    def test_client_routes_fall_back_to_index(self):
        for path in ("/", "/marketplace", "/admin/impact"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("id=root", response.text)

    def test_static_files_are_served(self):
        self.assertEqual(self.client.get("/favicon.png").content, b"png")

    def test_api_routes_win_and_unknown_api_paths_404(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/nope").status_code, 404)

    def test_paths_cannot_escape_dist(self):
        response = self.client.get("/..%2F..%2Fetc%2Fpasswd")
        self.assertIn("id=root", response.text)

    def test_missing_build_fails_fast(self):
        with tempfile.TemporaryDirectory() as empty, self.assertRaises(RuntimeError):
            mount_frontend(FastAPI(), empty)


if __name__ == "__main__":
    unittest.main()
