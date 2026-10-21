"""Fabric material identification with a vision LLM (OpenRouter).

The model sees the full table photo plus a numbered contact sheet of every
piece and returns fabric type, family, structure, composition, GSM and fold
factor per piece. If no model answers, a color/pattern heuristic stands in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from ..core.openrouter import OpenRouterClient
from .fabrics import FabricCatalog
from .imaging import ImageCodec

CONFIDENCE_LEVELS = {"low", "medium", "high"}


@dataclass
class MaterialResult:
    model: str
    warning: str | None
    pieces: dict[int, dict] = field(default_factory=dict)  # piece id -> material fields


class ContactSheet:
    """A grid of numbered piece crops so the model can refer to pieces by id."""

    CARD_W = CARD_H = 220
    COLS = 5
    MAX_PIECES = 35

    @classmethod
    def render(cls, image_bgr, pieces) -> Image.Image:
        cards = [(piece["id"], cls._piece_crop(image_bgr, piece)) for piece in pieces[: cls.MAX_PIECES]]
        rows = max(1, (len(cards) + cls.COLS - 1) // cls.COLS)
        sheet = Image.new("RGB", (cls.COLS * cls.CARD_W, rows * cls.CARD_H), "white")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default()

        for idx, (piece_id, crop) in enumerate(cards):
            row, col = divmod(idx, cls.COLS)
            x, y = col * cls.CARD_W, row * cls.CARD_H
            crop.thumbnail((cls.CARD_W - 16, cls.CARD_H - 36), Image.Resampling.LANCZOS)
            ox = x + (cls.CARD_W - crop.width) // 2
            oy = y + 28 + (cls.CARD_H - 36 - crop.height) // 2
            sheet.paste(crop, (ox, oy))
            draw.rectangle([x + 6, y + 6, x + 58, y + 25], fill=(0, 0, 0))
            draw.text((x + 12, y + 10), f"ID {piece_id}", fill=(255, 255, 255), font=font)
            draw.rectangle([x, y, x + cls.CARD_W - 1, y + cls.CARD_H - 1], outline=(210, 210, 210))
        return sheet

    @staticmethod
    def _piece_crop(image_bgr, piece) -> Image.Image:
        """Padded crop with the piece's outline drawn on it."""
        crop, x1, y1 = ImageCodec.padded_crop(image_bgr, piece["bbox"], pad_ratio=0.12)
        pil = ImageCodec.bgr_to_pil(crop).convert("RGB")
        contour = piece.get("contour") or []
        if len(contour) >= 2:
            local = [(int(px - x1), int(py - y1)) for px, py in contour]
            ImageDraw.Draw(pil).line(local + [local[0]], fill=(37, 99, 235), width=4)
        return pil


class MaterialClassifier:
    def __init__(self, client: OpenRouterClient, models: list[str], timeout_s: int = 60):
        self.client = client
        self.models = models
        self.timeout_s = timeout_s

    def classify(self, image_bgr, pieces: list[dict]) -> MaterialResult:
        if not self.client.configured:
            return self._heuristic(pieces, "OPENROUTER_API_KEY is not configured")

        full_image = self._full_image_data_url(image_bgr)
        sheet_image = ImageCodec.pil_to_data_url(ContactSheet.render(image_bgr, pieces))
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self._prompt(pieces)},
                    {"type": "image_url", "image_url": {"url": full_image, "detail": "low"}},
                    {"type": "image_url", "image_url": {"url": sheet_image, "detail": "high"}},
                ],
            }
        ]

        errors = []
        for model in self.models:
            try:
                data = self.client.complete_json(
                    model,
                    messages,
                    timeout_s=self.timeout_s,
                    temperature=0.1,
                    max_tokens=4000,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "fabric_piece_classification", "strict": True, "schema": RESPONSE_SCHEMA},
                    },
                )
                return self._normalize(data, pieces, model, None)
            except Exception as exc:
                errors.append(f"{model}: {exc}")
        return self._heuristic(pieces, "OpenRouter classification failed: " + " | ".join(errors))

    # -- prompt -------------------------------------------------------------------------

    @staticmethod
    def _prompt(pieces) -> str:
        metadata = [
            {
                "id": p["id"],
                "color_name": p["color_name"],
                "color_family": p.get("color_family"),
                "color_hex": p.get("color_hex"),
                "secondary_colors": [
                    {"name": c.get("name"), "percent": c.get("percent")} for c in p.get("secondary_colors", [])[:4]
                ],
                "pattern_type": p.get("pattern_type"),
                "size_label": p["size_label"],
                "shape_label": p["shape_label"],
                "area_cm2": p.get("area_cm2"),
                "aspect_ratio": p.get("aspect_ratio"),
            }
            for p in pieces
        ]
        return (
            "You are classifying clean garment-factory fabric scraps from an iPhone photo. "
            "You get the original table image plus a numbered contact sheet. Each card is an original crop with the detected scrap outlined. "
            "Classify every provided piece id. Use broad, visually defensible textile categories, not tiny chemistry distinctions. "
            "If a piece is printed, striped, checkered, denim, fleece-like, shiny satin-like, jersey/knit, or plain woven, use that visual evidence. "
            "Use only these fabric_type values: "
            f"{', '.join(FabricCatalog.FABRICS)}. "
            "Use color_family as the broad sorting color; do not reinterpret navy denim as black because it is dark. "
            "Composition must be a short percent string like '95% cotton, 5% spandex'. "
            "Estimate gsm from the visible material class, thickness, drape, texture, and folds. "
            "fold_factor should be 1.0 for flat single-layer pieces, 1.5-2.5 for visibly folded/thick pieces. "
            "Be conservative with confidence when the crop is ambiguous. Return JSON only, no markdown. Piece metadata: "
            + json.dumps(metadata)
        )

    @staticmethod
    def _full_image_data_url(image_bgr) -> str:
        pil = ImageCodec.bgr_to_pil(image_bgr)
        pil.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        return ImageCodec.pil_to_data_url(pil)

    # -- response handling ----------------------------------------------------------------

    def _normalize(self, data, pieces, model, warning) -> MaterialResult:
        """Clamp/validate every field; anything missing falls back to catalog defaults."""
        by_id = {int(item.get("id")): item for item in data.get("pieces", []) if item.get("id") is not None}
        results = {}
        for piece in pieces:
            item = by_id.get(piece["id"], {})
            fabric = item.get("fabric_type") if item.get("fabric_type") in FabricCatalog.FABRICS else None
            fabric = fabric or FabricCatalog.guess_from_appearance(piece)
            material_family = item.get("material_family")
            if material_family not in FabricCatalog.FAMILIES:
                material_family = FabricCatalog.family(fabric)
            weave_or_knit = item.get("weave_or_knit")
            if weave_or_knit not in FabricCatalog.STRUCTURES:
                weave_or_knit = FabricCatalog.structure(fabric)
            confidence = item.get("confidence")
            results[piece["id"]] = {
                "is_fabric": bool(item.get("is_fabric", True)),
                "fabric_type_guess": fabric,
                "material_family": material_family,
                "weave_or_knit": weave_or_knit,
                "composition_guess": item.get("composition") or FabricCatalog.composition(fabric),
                "fabric_confidence": confidence if confidence in CONFIDENCE_LEVELS else "medium",
                "material_evidence": item.get("evidence") or "Estimated from visual texture, color, and piece crop.",
                "gsm": self._clamp(item.get("gsm"), FabricCatalog.GSM_BY_FABRIC.get(fabric, 170), 80, 500),
                "fold_factor": self._clamp(item.get("fold_factor"), 1.0, 0.5, 4.0),
            }
        return MaterialResult(model=model, warning=warning, pieces=results)

    def _heuristic(self, pieces, warning) -> MaterialResult:
        data = {"pieces": []}
        for piece in pieces:
            fabric = FabricCatalog.guess_from_appearance(piece)
            data["pieces"].append(
                {
                    "id": piece["id"],
                    "is_fabric": True,
                    "fabric_type": fabric,
                    "material_family": FabricCatalog.family(fabric),
                    "weave_or_knit": FabricCatalog.structure(fabric),
                    "composition": FabricCatalog.composition(fabric),
                    "confidence": "low",
                    "gsm": FabricCatalog.GSM_BY_FABRIC.get(fabric, 170),
                    "fold_factor": 1.0,
                    "evidence": "Fallback estimate because the vision LLM was unavailable.",
                }
            )
        return self._normalize(data, pieces, "heuristic-fallback", warning)

    @staticmethod
    def _clamp(value, default, low, high) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return float(default)
        return float(max(low, min(high, value)))


RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pieces": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "integer"},
                    "is_fabric": {"type": "boolean"},
                    "fabric_type": {"type": "string", "enum": FabricCatalog.FABRICS},
                    "material_family": {"type": "string", "enum": FabricCatalog.FAMILIES},
                    "weave_or_knit": {"type": "string", "enum": FabricCatalog.STRUCTURES},
                    "composition": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "gsm": {"type": "number"},
                    "fold_factor": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": [
                    "id",
                    "is_fabric",
                    "fabric_type",
                    "material_family",
                    "weave_or_knit",
                    "composition",
                    "confidence",
                    "gsm",
                    "fold_factor",
                    "evidence",
                ],
            },
        }
    },
    "required": ["pieces"],
}
