"""Textile scrap pricing model.

Base price per kg is derived from fabric type and composition, then adjusted
by purity, color, weight tier, and piece-count multipliers. Price decays
exponentially after a grace period to incentivize quick marketplace turnover.

Decay formula: current = base * max(FLOOR, e^(-DECAY_RATE * max(0, days - GRACE)))
Half-life after grace period: ~46 days.
"""

from __future__ import annotations

import math
import re
from datetime import datetime

MINIMUM_PRICE = 0.01


class PricingModel:
    """Computes a lot's base listing price from what the camera saw."""

    # Base price per kg (USD) by dominant fabric keyword; first match wins.
    FABRIC_BASE_PER_KG: dict[str, float] = {
        "silk": 14.00,
        "wool": 6.50,
        "linen": 4.50,
        "denim": 3.80,
        "twill": 3.50,
        "cotton": 3.20,
        "jersey": 2.80,
        "spandex": 2.20,
        "nylon": 1.80,
        "polyester": 1.20,
    }
    DEFAULT_BASE_PER_KG = 2.00

    # Neutrals/whites command a re-dyeing premium.
    COLOR_MULTIPLIERS: dict[str, float] = {
        "white": 1.15,
        "natural": 1.15,
        "cream": 1.12,
        "ivory": 1.12,
        "beige": 1.10,
        "grey": 1.05,
        "gray": 1.05,
        "black": 1.05,
        "navy": 1.00,
        "blue": 1.00,
        "red": 0.97,
        "green": 0.97,
        "yellow": 0.95,
        "mixed": 0.85,
    }

    def base_price(
        self,
        fabric_type: str,
        composition: str,
        color_name: str,
        weight_kg: float,
        piece_count: int,
    ) -> float:
        """Return the base listing price (USD) for a lot."""
        per_kg = (
            self.base_per_kg(fabric_type)
            * self.purity_multiplier(composition)
            * self.color_multiplier(color_name)
            * self.weight_multiplier(weight_kg)
            * self.piece_multiplier(piece_count)
        )
        price = round(per_kg * weight_kg, 2)
        if weight_kg > 0 and piece_count > 0 and price == 0:
            return MINIMUM_PRICE
        return price

    def base_per_kg(self, fabric_type: str) -> float:
        fabric_lower = fabric_type.lower()
        for keyword, price in self.FABRIC_BASE_PER_KG.items():
            if keyword in fabric_lower:
                return price
        return self.DEFAULT_BASE_PER_KG

    @staticmethod
    def purity_multiplier(composition: str) -> float:
        """Single-fiber lots are more recyclable."""
        match = re.search(r"(\d+)\s*%", composition)
        if not match:
            return 1.0
        dominant_pct = int(match.group(1))
        if dominant_pct >= 95:
            return 1.20
        if dominant_pct >= 85:
            return 1.10
        if dominant_pct >= 70:
            return 1.00
        return 0.85

    def color_multiplier(self, color_name: str) -> float:
        return self.COLOR_MULTIPLIERS.get(color_name.lower(), 1.00)

    @staticmethod
    def weight_multiplier(weight_kg: float) -> float:
        """Bulk discount, small-lot premium."""
        if weight_kg >= 15:
            return 0.88
        if weight_kg >= 8:
            return 0.95
        if weight_kg <= 1:
            return 1.20
        if weight_kg <= 3:
            return 1.10
        return 1.00

    @staticmethod
    def piece_multiplier(piece_count: int) -> float:
        """Fewer large pieces = more maker-friendly."""
        if piece_count < 10:
            return 1.20
        if piece_count <= 30:
            return 1.05
        if piece_count <= 50:
            return 1.00
        return 0.90


class PriceDecay:
    """Time-based markdown applied when a listing is read (never stored)."""

    DECAY_RATE = 0.015  # 1.5 % per day — half-life ~46 days after grace
    GRACE_DAYS = 7  # no decay for first 7 days
    FLOOR_PCT = 0.35  # never drop below 35 % of base price

    def current_price(self, base_price: float, created_at: datetime, now: datetime | None = None) -> float:
        days = self._days_since(created_at, now)
        decay_days = max(0.0, days - self.GRACE_DAYS)
        factor = max(self.FLOOR_PCT, math.exp(-self.DECAY_RATE * decay_days))
        price = round(base_price * factor, 2)
        if base_price > 0 and price == 0:
            return MINIMUM_PRICE
        return price

    def decay_pct(self, base_price: float, created_at: datetime, now: datetime | None = None) -> int:
        """Percentage the price has dropped from base (0–65)."""
        if base_price == 0:
            return 0
        current = self.current_price(base_price, created_at, now)
        return max(0, round((1 - current / base_price) * 100))

    def days_listed(self, created_at: datetime, now: datetime | None = None) -> int:
        return max(0, int(self._days_since(created_at, now)))

    @staticmethod
    def _days_since(created_at: datetime, now: datetime | None) -> float:
        return ((now or datetime.utcnow()) - created_at).total_seconds() / 86_400


pricing_model = PricingModel()
price_decay = PriceDecay()
