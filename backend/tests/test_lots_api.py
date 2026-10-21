import unittest

from support import ApiHarness

from app.auth.models import Role
from app.marketplace.models import Lot
from app.marketplace.router import router as lots_router


class LotsApiTests(unittest.TestCase):
    def setUp(self):
        self.api = ApiHarness(lots_router)
        self.client = self.api.client

    def tearDown(self):
        self.api.close()

    def add_lot(self, **overrides) -> int:
        fields = {
            "name": "Blue cotton",
            "fabric_type": "cotton",
            "composition": "100% cotton",
            "color_name": "blue",
            "color_hex": "#2244aa",
            "piece_images": [{"crop_data_url": "data:image/gif;base64,legacy", "piece_id": 1}],
            "piece_count": 10,
            "weight_kg": 2.0,
            "price_usd": 20.0,
            "status": "available",
            **overrides,
        }
        with self.api.Session() as db:
            lot = Lot(**fields)
            db.add(lot)
            db.commit()
            return lot.id

    # -- browsing ----------------------------------------------------------------------

    def test_listing_normalizes_images_and_fills_key_for_legacy_rows(self):
        self.add_lot(lot_key=None)

        body = self.client.get("/api/lots", params={"status": "available"}).json()

        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["lot_key"], "cotton::100-cotton::blue")
        self.assertEqual(body[0]["piece_images"][0]["src"], "data:image/gif;base64,legacy")
        self.assertEqual(body[0]["current_price_usd"], 20.0)

    def test_search_filters_by_status_and_text(self):
        self.add_lot()
        self.add_lot(name="Red fleece", fabric_type="fleece", color_name="red", status="unlisted")

        self.assertEqual([l["name"] for l in self.client.get("/api/lots", params={"q": "fleece"}).json()], ["Red fleece"])
        self.assertEqual(len(self.client.get("/api/lots", params={"status": "available"}).json()), 1)

    # -- inventory management ----------------------------------------------------------

    def test_inventory_management_is_admin_only(self):
        lot_id = self.add_lot()

        for role in (Role.FACTORY, Role.BUYER):
            headers = self.api.auth(role)
            self.assertEqual(self.client.patch(f"/api/lots/{lot_id}/delist", headers=headers).status_code, 403)
            self.assertEqual(self.client.delete(f"/api/lots/{lot_id}", headers=headers).status_code, 403)

        admin = self.api.auth(Role.ADMIN)
        self.assertEqual(self.client.patch(f"/api/lots/{lot_id}/delist", headers=admin).json()["status"], "unlisted")
        self.assertEqual(self.client.patch(f"/api/lots/{lot_id}/relist", headers=admin).json()["status"], "available")
        self.assertEqual(self.client.delete(f"/api/lots/{lot_id}", headers=admin).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/lots/{lot_id}", headers=admin).status_code, 404)

    # -- claims ------------------------------------------------------------------------

    def test_buyer_claims_as_themselves_regardless_of_body(self):
        lot_id = self.add_lot()

        claimed = self.client.post(
            f"/api/lots/{lot_id}/claim", json={"buyer_name": "Someone Else"}, headers=self.api.auth(Role.BUYER)
        )

        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(claimed.json()["claimed_by"], "Looptex Recyclers")

    def test_admin_can_assign_a_lot_to_a_named_buyer(self):
        lot_id = self.add_lot()

        claimed = self.client.post(
            f"/api/lots/{lot_id}/claim", json={"buyer_name": "Thread & Tide Studio"}, headers=self.api.auth(Role.ADMIN)
        )

        self.assertEqual(claimed.json()["claimed_by"], "Thread & Tide Studio")

    def test_claims_require_a_purchaser(self):
        lot_id = self.add_lot()
        self.assertEqual(self.client.post(f"/api/lots/{lot_id}/claim", json={}).status_code, 401)
        self.assertEqual(
            self.client.post(f"/api/lots/{lot_id}/claim", json={}, headers=self.api.auth(Role.FACTORY)).status_code,
            403,
        )

    def test_partial_claim_splits_lot_and_second_full_claim_fails(self):
        lot_id = self.add_lot()
        buyer = self.api.auth(Role.BUYER)

        part = self.client.post(f"/api/lots/{lot_id}/claim", json={"quantity_kg": 0.5}, headers=buyer).json()
        remainder = self.client.get("/api/lots", params={"status": "available"}).json()[0]

        self.assertNotEqual(part["id"], lot_id)
        self.assertEqual(part["weight_kg"], 0.5)
        self.assertEqual(part["price_usd"], 5.0)
        self.assertEqual(part["status"], "claimed")
        self.assertEqual((remainder["id"], remainder["weight_kg"]), (lot_id, 1.5))

        self.client.post(f"/api/lots/{lot_id}/claim", json={}, headers=buyer)
        again = self.client.post(f"/api/lots/{lot_id}/claim", json={}, headers=buyer)
        self.assertEqual(again.status_code, 400)
        self.assertIn("already claimed", again.json()["detail"])


if __name__ == "__main__":
    unittest.main()
