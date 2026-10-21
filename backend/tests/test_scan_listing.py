import unittest
from unittest.mock import patch

import cv2
from support import ApiHarness
from test_scanning import _FakeSegmenter, _pipeline, _synthetic_scrap_scene

from app.auth.models import Role
from app.marketplace.router import router as lots_router
from app.scanning.router import router as scanning_router


def _scan_result():
    image_bgr, raw_masks = _synthetic_scrap_scene()
    ok, encoded = cv2.imencode(".png", image_bgr)
    assert ok
    return encoded.tobytes(), _pipeline(_FakeSegmenter(raw_masks))


class ScanListingTests(unittest.TestCase):
    def setUp(self):
        self.api = ApiHarness(lots_router, scanning_router)
        self.client = self.api.client
        self.photo, self.pipeline = _scan_result()

    def tearDown(self):
        self.api.close()

    def test_from_scan_records_run_and_lists_one_lot_per_bin(self):
        scan = self.pipeline.run(self.photo)

        response = self.client.post(
            "/api/lots/from-scan",
            json={"scan": scan, "origin_lat": 33.75, "origin_lng": -84.39},
            headers=self.api.auth(Role.FACTORY),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([b["sort_group_id"] for b in body["bins"]], [g["sort_group_id"] for g in scan["groups"]])
        self.assertEqual(sum(b["piece_count"] for b in body["bins"]), 12)
        self.assertGreater(body["total_weight_kg"], 0)

        lots = self.client.get("/api/lots").json()
        self.assertEqual(len(lots), len(scan["groups"]))
        for lot in lots:
            self.assertEqual(lot["scan_run_id"], body["scan_run_id"])
            self.assertEqual((lot["origin_lat"], lot["origin_lng"]), (33.75, -84.39))
            self.assertGreater(lot["price_usd"], 0)
            self.assertTrue(lot["piece_images"])
            self.assertTrue(all(img["src"].startswith("data:image/") for img in lot["piece_images"]))

    def test_rescanning_creates_new_lots_instead_of_merging(self):
        scan = self.pipeline.run(self.photo)
        headers = self.api.auth(Role.FACTORY)

        first = self.client.post("/api/lots/from-scan", json={"scan": scan}, headers=headers).json()
        second = self.client.post("/api/lots/from-scan", json={"scan": scan}, headers=headers).json()

        self.assertNotEqual(first["scan_run_id"], second["scan_run_id"])
        self.assertEqual(len(self.client.get("/api/lots").json()), 2 * len(scan["groups"]))

    def test_vision_scan_uploads_photo_and_lists_lots(self):
        with patch("app.scanning.router.ScanPipeline.from_settings", return_value=self.pipeline):
            response = self.client.post(
                "/api/vision/scan",
                files={"image": ("table.png", self.photo, "image/png")},
                data={"origin_lat": "33.75", "origin_lng": "-84.39"},
                headers=self.api.auth(Role.FACTORY),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["bins"]), 4)
        self.assertEqual(len(self.client.get("/api/lots").json()), 4)

    def test_scan_endpoints_require_an_operator(self):
        scan = self.pipeline.run(self.photo)
        buyer = self.api.auth(Role.BUYER)
        self.assertEqual(self.client.post("/api/lots/from-scan", json={"scan": scan}, headers=buyer).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/vision/scan", files={"image": ("t.png", self.photo, "image/png")}, headers=buyer
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
