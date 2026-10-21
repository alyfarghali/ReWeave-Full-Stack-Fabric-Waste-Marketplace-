"""Marketplace inventory: the sellable lots a scan produces, and the scans themselves.

``Lot`` owns its own lifecycle rules (split, claim, delist, relist) so routers
and services never poke at status strings directly.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from ..core.database import Base
from ..valuation import impact_calculator, price_decay, pricing_model
from .piece_images import PieceImages


class LotStatus:
    AVAILABLE = "available"
    CLAIMED = "claimed"
    UNLISTED = "unlisted"


class LotStateError(Exception):
    """A lifecycle transition that is not allowed from the lot's current status."""


class Lot(Base):
    """A sellable group of scraps, created from a camera scan (a vision color /
    fabric group). Every descriptive field comes from the vision pipeline; the
    price and environmental impact are computed when the lot is created.
    """

    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    # From the camera (vision pipeline)
    fabric_type = Column(String, nullable=False)
    composition = Column(String, nullable=False)
    color_name = Column(String, nullable=False)
    color_hex = Column(String, nullable=False)
    lot_key = Column(String, nullable=True, index=True)
    scan_run_id = Column(Integer, ForeignKey("scan_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    piece_images = Column(JSON, default=list)
    piece_count = Column(Integer, default=0)
    weight_kg = Column(Float, default=0.0)
    # Computed at listing time
    price_usd = Column(Float, default=0.0)
    carbon_saved_kg = Column(Float, default=0.0)
    water_saved_l = Column(Float, default=0.0)
    # Origin — where the factory worker shared their location during the scan
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    # Marketplace lifecycle
    status = Column(String, default=LotStatus.AVAILABLE)  # available | claimed | unlisted
    claimed_by = Column(String, nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # -- identity ----------------------------------------------------------------

    @staticmethod
    def make_key(fabric_type: str, composition: str, color_name: str) -> str:
        """Stable merge key: lots with the same fabric/composition/color combine."""
        cleaned = []
        for part in (fabric_type, composition, color_name):
            value = re.sub(r"[^a-z0-9]+", "-", (part or "unspecified").strip().lower())
            cleaned.append(value.strip("-") or "unspecified")
        return "::".join(cleaned)

    @property
    def effective_key(self) -> str:
        return self.lot_key or self.make_key(self.fabric_type, self.composition, self.color_name)

    # -- computed pricing ----------------------------------------------------------

    @property
    def current_price_usd(self) -> float:
        return price_decay.current_price(self.price_usd or 0, self.created_at)

    @property
    def price_decay_pct(self) -> int:
        return price_decay.decay_pct(self.price_usd or 0, self.created_at)

    @property
    def days_listed(self) -> int:
        return price_decay.days_listed(self.created_at)

    @property
    def images(self) -> list[dict]:
        return PieceImages.normalize(self.piece_images)

    def reprice(self) -> None:
        self.price_usd = pricing_model.base_price(
            fabric_type=self.fabric_type,
            composition=self.composition,
            color_name=self.color_name,
            weight_kg=self.weight_kg,
            piece_count=self.piece_count,
        )

    def recompute_impact(self) -> None:
        self.carbon_saved_kg = impact_calculator.carbon_saved_kg(self.weight_kg)
        self.water_saved_l = impact_calculator.water_saved_l(self.weight_kg)

    # -- lifecycle -----------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self.status == LotStatus.AVAILABLE

    def claim(self, buyer_name: str, quantity_kg: float | None = None) -> "Lot":
        """Claim all of this lot, or split off ``quantity_kg`` and claim that part.

        Returns the claimed lot: ``self`` for a full claim, or a new (unsaved)
        Lot for a partial one; the caller must add a new lot to the session.
        """
        if self.status == LotStatus.CLAIMED:
            raise LotStateError("Lot already claimed")
        if not self.is_available:
            raise LotStateError("Lot is not available")

        if quantity_kg is not None:
            quantity_kg = round(float(quantity_kg), 3)
            if quantity_kg <= 0:
                raise LotStateError("Quantity must be greater than zero")

        if quantity_kg is None or quantity_kg >= (self.weight_kg or 0) - 0.001:
            self._mark_claimed(buyer_name)
            return self
        if quantity_kg > (self.weight_kg or 0):
            raise LotStateError("Quantity exceeds available weight")
        claimed = self._split_off(quantity_kg)
        claimed._mark_claimed(buyer_name)
        return claimed

    def delist(self) -> None:
        if self.status == LotStatus.CLAIMED:
            raise LotStateError("Cannot delist a claimed lot")
        self.status = LotStatus.UNLISTED

    def relist(self) -> None:
        if self.status != LotStatus.UNLISTED:
            raise LotStateError("Lot is not unlisted")
        self.status = LotStatus.AVAILABLE

    def _mark_claimed(self, buyer_name: str) -> None:
        self.status = LotStatus.CLAIMED
        self.claimed_by = buyer_name
        self.claimed_at = datetime.utcnow()

    def _split_off(self, quantity_kg: float) -> "Lot":
        """Move ``quantity_kg`` (and a proportional share of pieces, price and
        impact) out of this lot into a new one."""
        ratio = quantity_kg / self.weight_kg if self.weight_kg else 0
        claimed_pieces = max(1, round((self.piece_count or 0) * ratio))
        images = self.images
        part = Lot(
            name=self.name,
            description=self.description,
            fabric_type=self.fabric_type,
            composition=self.composition,
            color_name=self.color_name,
            color_hex=self.color_hex,
            lot_key=self.lot_key,
            piece_images=images[:claimed_pieces],
            piece_count=claimed_pieces,
            weight_kg=quantity_kg,
            price_usd=round((self.price_usd or 0) * ratio, 2),
            carbon_saved_kg=round((self.carbon_saved_kg or 0) * ratio, 2),
            water_saved_l=round((self.water_saved_l or 0) * ratio, 2),
            status=self.status,
            created_at=self.created_at,
        )
        self.weight_kg = round(self.weight_kg - quantity_kg, 3)
        self.piece_count = max(0, (self.piece_count or 0) - claimed_pieces)
        self.price_usd = round((self.price_usd or 0) - part.price_usd, 2)
        self.carbon_saved_kg = round((self.carbon_saved_kg or 0) - part.carbon_saved_kg, 2)
        self.water_saved_l = round((self.water_saved_l or 0) - part.water_saved_l, 2)
        self.piece_images = images[claimed_pieces:] or images
        return part


class ScanRun(Base):
    """One camera/table scan that produced one or more marketplace lots."""

    __tablename__ = "scan_runs"

    id = Column(Integer, primary_key=True, index=True)
    annotated_image_data_url = Column(Text, nullable=True)
    image_width = Column(Integer, default=0)
    image_height = Column(Integer, default=0)
    piece_count = Column(Integer, default=0)
    group_count = Column(Integer, default=0)
    total_weight_kg = Column(Float, default=0.0)
    total_carbon_saved_kg = Column(Float, default=0.0)
    total_water_saved_l = Column(Float, default=0.0)
    summary = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
