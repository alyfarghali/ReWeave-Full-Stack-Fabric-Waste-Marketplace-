import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.valuation import price_decay, pricing_model


class PricingTests(unittest.TestCase):
    def test_positive_tiny_lot_has_minimum_price(self):
        price = pricing_model.base_price(
            fabric_type="unknown textile",
            composition="unknown",
            color_name="black",
            weight_kg=0.0005,
            piece_count=6,
        )

        self.assertEqual(price, 0.01)

    def test_decayed_positive_price_does_not_round_to_zero(self):
        price = price_decay.current_price(0.01, datetime.utcnow() - timedelta(days=365))

        self.assertEqual(price, 0.01)

    def test_no_decay_during_grace_period(self):
        now = datetime(2026, 1, 10)
        self.assertEqual(price_decay.current_price(100.0, now - timedelta(days=7), now=now), 100.0)
        self.assertEqual(price_decay.decay_pct(100.0, now - timedelta(days=7), now=now), 0)

    def test_decay_never_drops_below_floor(self):
        now = datetime(2026, 1, 10)
        self.assertEqual(price_decay.current_price(100.0, now - timedelta(days=1000), now=now), 35.0)
        self.assertEqual(price_decay.decay_pct(100.0, now - timedelta(days=1000), now=now), 65)

    def test_pure_white_small_lot_gets_premiums(self):
        # cotton $3.20 x purity 1.20 x white 1.15 x <=1kg 1.20 x <10 pieces 1.20
        price = pricing_model.base_price("cotton", "100% cotton", "white", weight_kg=1.0, piece_count=5)
        self.assertEqual(price, round(3.20 * 1.20 * 1.15 * 1.20 * 1.20, 2))


if __name__ == "__main__":
    unittest.main()
