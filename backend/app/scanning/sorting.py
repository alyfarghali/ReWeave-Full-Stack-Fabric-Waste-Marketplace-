"""Assigning pieces to sort bins (A, B, C, ...) a factory worker can act on.

Pieces are binned by (color family, material sort family, pattern). When most
pieces of one color agree on a material, that consensus overrides individual
LLM outliers so a single misread scrap doesn't spawn its own bin.
"""

from __future__ import annotations

import string
from collections import Counter, defaultdict

from .colors import ColorNaming
from .fabrics import FabricCatalog
from .geometry import WeightEstimator

BIN_COLORS = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#f59e0b",
    "#7c3aed",
    "#0891b2",
    "#db2777",
    "#4b5563",
    "#84cc16",
    "#ea580c",
]

PRINTED_PATTERNS = {"floral", "checkered", "striped"}


def _most_common(values, default):
    cleaned = [value for value in values if value]
    if not cleaned:
        return default
    return Counter(cleaned).most_common(1)[0][0]


def describe_group(group: dict) -> str:
    """Human label such as "navy denim" or "red striped cotton jersey"."""
    color = group.get("color_family") or group.get("color_name") or "mixed"
    fabric = group.get("fabric_type_guess") or "unknown textile"
    pattern = group.get("pattern_type") or "solid"
    if pattern != "solid" and pattern not in color:
        return f"{color} {pattern} {fabric}"
    return f"{color} {fabric}"


class SortBin:
    """Accumulates pieces for one bin, then summarizes them as a group dict."""

    def __init__(self, index: int, first_piece: dict, color_family: str, material_sort_family: str, pattern: str):
        self.bin_id = self._bin_id(index)
        self.outline_color = BIN_COLORS[index % len(BIN_COLORS)]
        self.color_family = color_family
        self.material_sort_family = material_sort_family
        self.pattern = pattern
        self.first = first_piece
        self.pieces: list[dict] = []

    @staticmethod
    def _bin_id(index: int) -> str:
        letters = string.ascii_uppercase
        return letters[index] if index < len(letters) else f"Z{index - len(letters) + 1}"

    def add(self, piece: dict) -> None:
        piece["sort_group_id"] = self.bin_id
        piece["outline_color"] = self.outline_color
        piece["color_family"] = self.color_family
        piece["material_sort_family"] = self.material_sort_family
        self.pieces.append(piece)

    def summary(self) -> dict:
        first = self.first
        first_fabric = first.get("fabric_type_guess", "unknown textile")
        fabrics = [p.get("fabric_type_guess", "unknown textile") for p in self.pieces]
        families = [
            p.get("material_family") or FabricCatalog.family_from_name(p.get("fabric_type_guess", "unknown textile"))
            for p in self.pieces
        ]
        structures = [p.get("weave_or_knit") or "unknown" for p in self.pieces]
        compositions = [p.get("composition_guess", "mixed textile") for p in self.pieces]
        size_labels = [p["size_label"] for p in self.pieces]
        piece_ids = [p["id"] for p in self.pieces]
        weight_g = round(sum(p.get("estimated_weight_g") or 0.0 for p in self.pieces), 1)

        group = {
            "sort_group_id": self.bin_id,
            "fabric_type_guess": _most_common(fabrics, first_fabric),
            "material_family": _most_common(families, families[0]),
            "material_sort_family": self.material_sort_family,
            "weave_or_knit": _most_common(structures, structures[0]),
            "composition_guess": _most_common(compositions, compositions[0]),
            "color_name": first["color_name"],
            "color_family": self.color_family,
            "pattern_type": self.pattern,
            "color_hex": first["color_hex"],
            "outline_color": self.outline_color,
            "piece_count": len(self.pieces),
            "total_size_percent": round(sum(p["size_percent"] for p in self.pieces), 2),
            "estimated_weight_g": weight_g,
            "avg_size_label": max(set(size_labels), key=size_labels.count) if size_labels else "medium",
            "total_weight_label": WeightEstimator.label(weight_g, unknown="unknown"),
            "piece_ids": piece_ids,
        }
        group["sort_instruction"] = (
            f"Bin {self.bin_id}: place outlined pieces {', '.join(str(i) for i in piece_ids)} "
            f"into the {describe_group(group)} lot."
        )
        return group


class SortGrouper:
    CONSENSUS_MIN_PIECES = 3
    CONSENSUS_MIN_VOTES = 2

    def group(self, pieces: list[dict]) -> list[dict]:
        """Assign every piece a bin (mutating it) and return bins heaviest first."""
        consensus = self._material_consensus_by_color(pieces)
        bins: dict[tuple, SortBin] = {}
        for piece in pieces:
            color_family = self.color_family(piece)
            material_sort_family = consensus.get(color_family) or self.material_sort_family(piece)
            pattern = self.pattern(piece)
            key = (color_family, material_sort_family, pattern)
            if key not in bins:
                bins[key] = SortBin(len(bins), piece, color_family, material_sort_family, pattern)
            bins[key].add(piece)

        groups = [sort_bin.summary() for sort_bin in bins.values()]
        groups.sort(key=lambda g: g["estimated_weight_g"], reverse=True)
        return groups

    # -- per-piece sort keys --------------------------------------------------------------

    @staticmethod
    def color_family(piece: dict) -> str:
        explicit = piece.get("color_family")
        if explicit:
            return explicit
        pattern = piece.get("pattern_type") or "solid"
        if pattern in PRINTED_PATTERNS:
            names = [piece.get("color_name")]
            names.extend(c.get("name") for c in piece.get("secondary_colors", [])[:2] if c.get("name"))
            names = [name for name in names if name]
            if names:
                return f"{pattern} " + "/".join(dict.fromkeys(names))
            return pattern
        return ColorNaming.family(
            rgb=piece.get("dominant_rgb"),
            name=piece.get("color_name", "mixed"),
            clusters=piece.get("color_clusters"),
        )

    @staticmethod
    def pattern(piece: dict) -> str:
        pattern = piece.get("pattern_type") or "solid"
        return "solid" if pattern in {"print", "mixed"} else pattern

    @staticmethod
    def material_sort_family(piece: dict) -> str:
        """Coarse physical category a worker can tell apart by hand."""
        fabric = (piece.get("fabric_type_guess") or "").lower()
        material = (piece.get("material_family") or "").lower()
        structure = (piece.get("weave_or_knit") or "").lower()
        color = piece.get("color_family") or ColorNaming.family(
            rgb=piece.get("dominant_rgb"),
            name=piece.get("color_name", ""),
            clusters=piece.get("color_clusters"),
        )

        if "denim" in fabric or "denim" in material or "denim" in structure:
            return "denim"
        if "fleece" in fabric or "fleece" in structure:
            return "fleece"
        if "knit" in fabric or "jersey" in fabric or "rib" in fabric or "knit" in structure:
            if color in {"red", "black"}:
                return "fleece"
            return "knit"
        if "woven" in fabric or "woven" in structure or "cotton" in material:
            return "woven"
        if "poly" in material:
            return "synthetic"
        return "textile"

    def _material_consensus_by_color(self, pieces) -> dict[str, str]:
        by_color = defaultdict(list)
        for piece in pieces:
            by_color[self.color_family(piece)].append(self.material_sort_family(piece))

        consensus = {}
        for family, materials in by_color.items():
            if len(materials) < self.CONSENSUS_MIN_PIECES:
                continue
            material, count = Counter(materials).most_common(1)[0]
            if count >= self.CONSENSUS_MIN_VOTES:
                consensus[family] = material
        return consensus
