"""Turning a scan pipeline result into inventory: one scan run plus one lot per sort bin.

Shared by the factory web page (which already holds the scan result) and the
fixed scanning station (which uploads a photo and wants lots in one call), so
the naming, weight, and image rules for a listing live in one place.
"""

from __future__ import annotations

from ..valuation import impact_calculator
from .schemas import LotCreate, ScanRunCreate

MAX_IMAGES_PER_LOT = 12
MAX_SUMMARY_WARNINGS = 4
UNSPECIFIED = "Unspecified"


def _capitalize(value: str) -> str:
    return value[:1].upper() + value[1:] if value else ""


def _format_weight(grams: float) -> str:
    if grams >= 1000:
        kg = grams / 1000
        return f"{kg:.1f} kg" if kg >= 10 else f"{kg:.2f} kg"
    return f"{round(grams)} g"


def _bin_id(group: dict, index: int) -> str:
    return group.get("sort_group_id") or chr(65 + index)


class ScanListing:
    """Builds the scan-run and lot payloads for one pipeline result."""

    def __init__(self, scan: dict):
        self.scan = scan
        self.groups: list[dict] = list(scan.get("groups") or [])
        self.pieces: list[dict] = list(scan.get("pieces") or [])

    # -- scan run --------------------------------------------------------------------

    def scan_run(self) -> ScanRunCreate:
        weight_kg = sum((group.get("estimated_weight_g") or 0) / 1000 for group in self.groups)
        return ScanRunCreate(
            annotated_image_data_url=self.scan.get("annotated_image_data_url"),
            image_width=self.scan.get("image_width") or 0,
            image_height=self.scan.get("image_height") or 0,
            piece_count=len(self.pieces),
            group_count=len(self.groups),
            total_weight_kg=round(weight_kg, 4),
            total_carbon_saved_kg=round(impact_calculator.raw_carbon_kg(weight_kg), 4),
            total_water_saved_l=round(impact_calculator.raw_water_l(weight_kg), 2),
            summary={
                "scale_method": self.scan.get("scale_method"),
                "scale_confidence": self.scan.get("scale_confidence"),
                "segmentation_method": self.scan.get("segmentation_method"),
                "llm_model": self.scan.get("llm_model"),
                "warnings": list(self.scan.get("warnings") or [])[:MAX_SUMMARY_WARNINGS],
                "groups": [self._group_summary(group, i) for i, group in enumerate(self.groups)],
            },
        )

    def _group_summary(self, group: dict, index: int) -> dict:
        return {
            "key": group.get("sort_group_id") or f"{group.get('color_name')}-{index}",
            "sort_group_id": _bin_id(group, index),
            "color_name": group.get("color_name"),
            "color_hex": group.get("color_hex"),
            "fabric_type": group.get("fabric_type_guess") or UNSPECIFIED,
            "composition": group.get("composition_guess") or UNSPECIFIED,
            "piece_count": group.get("piece_count") or 0,
            "weight_g": group.get("estimated_weight_g") or 0,
        }

    # -- lots --------------------------------------------------------------------------

    def lots(self, scan_run_id: int, origin_lat: float | None, origin_lng: float | None) -> list[tuple[str, LotCreate]]:
        """(bin id, lot payload) for every sort group, in pipeline order."""
        return [
            (_bin_id(group, i), self._lot(group, scan_run_id, origin_lat, origin_lng))
            for i, group in enumerate(self.groups)
        ]

    def _lot(self, group: dict, scan_run_id: int, origin_lat: float | None, origin_lng: float | None) -> LotCreate:
        weight_g = float(group.get("estimated_weight_g") or 0)
        weight_label = group.get("total_weight_label") or (_format_weight(weight_g) if weight_g else "weight pending")
        grouped = self._pieces_for(group)
        images = self._images(grouped) or self._images(self.pieces)
        count = group.get("piece_count") or len(grouped or self.pieces)
        color = group.get("color_name") or "unknown"
        fabric = group.get("fabric_type_guess") or UNSPECIFIED
        composition = group.get("composition_guess") or UNSPECIFIED

        description = ". ".join(
            part
            for part in (
                f"{count} {'piece' if count == 1 else 'pieces'} of {color} {fabric}",
                f"{weight_label} estimated total",
                composition if composition != UNSPECIFIED else "",
                group.get("sort_instruction") or "",
            )
            if part
        )
        return LotCreate(
            name=f"{_capitalize(color)} {fabric}".strip(),
            description=description,
            fabric_type=fabric,
            composition=composition,
            color_name=color,
            color_hex=group.get("color_hex") or "#777777",
            piece_images=images[:MAX_IMAGES_PER_LOT],
            piece_count=count,
            weight_kg=round(weight_g / 1000, 3),
            price_usd=0,  # auto-priced by InventoryService.list_group
            scan_run_id=scan_run_id,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
        )

    def _pieces_for(self, group: dict) -> list[dict]:
        """The group's pieces: by id, then bin id, then color + fabric, then color."""
        piece_ids = {int(pid) for pid in group.get("piece_ids") or []}
        by_ids = [p for p in self.pieces if p.get("id") in piece_ids]
        if by_ids:
            return by_ids

        bin_id = str(group.get("sort_group_id") or "")
        by_bin = [p for p in self.pieces if str(p.get("sort_group_id") or "") == bin_id]
        if by_bin:
            return by_bin

        color = str(group.get("color_name") or "").lower()
        fabric = str(group.get("fabric_type_guess") or "").lower()
        same_color = [p for p in self.pieces if str(p.get("color_name") or "").lower() == color]
        by_fabric = [p for p in same_color if not fabric or str(p.get("fabric_type_guess") or "").lower() == fabric]
        return by_fabric or same_color

    @staticmethod
    def _images(pieces: list[dict]) -> list[dict]:
        return [
            {
                "src": piece["crop_data_url"],
                "piece_id": piece.get("id"),
                "color_name": piece.get("color_name"),
                "weight_label": piece.get("weight_label"),
                "size_label": piece.get("size_label"),
            }
            for piece in pieces
            if piece.get("crop_data_url")
        ][:MAX_IMAGES_PER_LOT]
