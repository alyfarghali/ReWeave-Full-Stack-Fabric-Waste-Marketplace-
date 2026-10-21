from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..scanning.schemas import DetectResponse
from .models import Lot


class LotCreate(BaseModel):
    """A lot built from one sort bin of a scan (see scan_listing.py)."""

    name: str
    description: Optional[str] = ""
    fabric_type: str
    composition: str
    color_name: str
    color_hex: str
    lot_key: Optional[str] = None
    scan_run_id: Optional[int] = None
    piece_images: List[dict[str, Any]] = Field(default_factory=list)
    piece_count: int = 0
    weight_kg: float = 0.0
    price_usd: float = 0.0
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None


class LotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = ""
    fabric_type: str
    composition: str
    color_name: str
    color_hex: str
    lot_key: Optional[str] = None
    scan_run_id: Optional[int] = None
    piece_images: List[dict[str, Any]] = Field(default_factory=list)
    piece_count: int
    weight_kg: float
    price_usd: float  # base price at time of listing
    current_price_usd: float  # price after decay (computed, not stored)
    price_decay_pct: int  # % dropped from base (0–65)
    days_listed: int  # days since created
    carbon_saved_kg: float
    water_saved_l: float
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    status: str
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_lot(cls, lot: Lot) -> "LotOut":
        """Serialize a Lot, filling in the computed price/decay fields."""
        return cls(
            id=lot.id,
            name=lot.name,
            description=lot.description,
            fabric_type=lot.fabric_type,
            composition=lot.composition,
            color_name=lot.color_name,
            color_hex=lot.color_hex,
            lot_key=lot.effective_key,
            scan_run_id=lot.scan_run_id,
            piece_images=lot.images,
            piece_count=lot.piece_count,
            weight_kg=lot.weight_kg,
            price_usd=lot.price_usd,
            current_price_usd=lot.current_price_usd,
            price_decay_pct=lot.price_decay_pct,
            days_listed=lot.days_listed,
            carbon_saved_kg=lot.carbon_saved_kg,
            water_saved_l=lot.water_saved_l,
            origin_lat=lot.origin_lat,
            origin_lng=lot.origin_lng,
            status=lot.status,
            claimed_by=lot.claimed_by,
            claimed_at=lot.claimed_at,
            created_at=lot.created_at,
        )


class LotClaim(BaseModel):
    buyer_name: Optional[str] = None  # admins only; buyers always claim as themselves
    quantity_kg: Optional[float] = None


class LotSearch(BaseModel):
    """Query-string filters for listing lots."""

    status: Optional[str] = None
    fabric_type: Optional[str] = None
    color_name: Optional[str] = None
    claimed_by: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    q: Optional[str] = None




class ScanRunCreate(BaseModel):
    """Summary of one scan, stored alongside the lots it produced."""

    annotated_image_data_url: Optional[str] = None
    image_width: int = 0
    image_height: int = 0
    piece_count: int = 0
    group_count: int = 0
    total_weight_kg: float = 0.0
    total_carbon_saved_kg: float = 0.0
    total_water_saved_l: float = 0.0
    summary: dict[str, Any] = Field(default_factory=dict)



class ScanListingRequest(BaseModel):
    """A scan pipeline result to record and list, plus where it was scanned."""

    scan: DetectResponse
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None


class BinListing(BaseModel):
    sort_group_id: str
    lot_id: int
    name: str
    piece_count: int
    weight_kg: float
    price_usd: float
    sort_instruction: Optional[str] = None


class ScanListingOut(BaseModel):
    scan_run_id: int
    bins: List[BinListing]
    total_weight_kg: float
    total_carbon_saved_kg: float
    total_water_saved_l: float
    warnings: List[str] = Field(default_factory=list)
