"""Outputs a worker can read: the annotated sorting-plan image and the piece table."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .imaging import ImageCodec
from .sorting import describe_group

FONT_PATHS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
DEFAULT_OUTLINE = "#2563eb"


def _font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ellipsize(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "..."


def _hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


class AnnotationRenderer:
    """Draws each piece's outline and bin label on the photo, plus a bin legend."""

    LEGEND_WIDTH = 540

    def __init__(self):
        self.font = _font(16)
        self.font_bold = _font(18)
        self.font_small = _font(13)

    def render(self, image_bgr, pieces: list[dict], groups: list[dict]) -> str:
        """Return the annotated sorting plan as a PNG data URL."""
        composed = self._draw_pieces(ImageCodec.bgr_to_pil(image_bgr).convert("RGBA"), pieces)
        out = self._draw_legend(composed, pieces, groups)
        return ImageCodec.pil_to_data_url(out.convert("RGB"), fmt="PNG")

    def _draw_pieces(self, base: Image.Image, pieces) -> Image.Image:
        # Translucent fills first, composited under the outlines and labels.
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for piece in pieces:
            contour = piece.get("contour") or []
            if len(contour) >= 3:
                draw.polygon([tuple(p) for p in contour], fill=_hex_to_rgba(piece.get("outline_color") or DEFAULT_OUTLINE, 70))

        composed = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(composed)
        for piece in pieces:
            contour = piece.get("contour") or []
            if len(contour) >= 2:
                points = [tuple(p) for p in contour]
                draw.line(points + [points[0]], fill=piece.get("outline_color") or DEFAULT_OUTLINE, width=4)

            label = f"{piece['sort_group_id']}{piece['id']}"
            tx, ty = self._label_position(piece)
            text_box = draw.textbbox((0, 0), label, font=self.font)
            tw, th = text_box[2] - text_box[0], text_box[3] - text_box[1]
            draw.rounded_rectangle([tx, ty, tx + tw + 16, ty + th + 12], radius=6, fill=(0, 0, 0, 232))
            draw.text((tx + 8, ty + 5), label, fill="white", font=self.font_bold)
        return composed

    def _draw_legend(self, composed: Image.Image, pieces, groups) -> Image.Image:
        out = Image.new("RGBA", (composed.width + self.LEGEND_WIDTH, composed.height), (248, 250, 252, 255))
        out.paste(composed, (0, 0))
        legend = ImageDraw.Draw(out)

        lx, y = composed.width + 24, 24
        legend.text((lx, y), "Sorting Plan", fill=(15, 23, 42), font=self.font_bold)
        y += 34
        legend.text((lx, y), f"{len(pieces)} fabric pieces across {len(groups)} sort bins", fill=(71, 85, 105), font=self.font)
        y += 34

        for group in groups:
            if y > out.height - 96:
                legend.text((lx, y), "... more bins in table", fill=(100, 116, 139), font=self.font)
                break
            legend.rounded_rectangle([lx, y, lx + 62, y + 34], radius=7, fill=group["outline_color"])
            legend.text((lx + 21, y + 8), group["sort_group_id"], fill="white", font=self.font_bold)
            legend.text((lx + 78, y - 1), _ellipsize(describe_group(group), 42), fill=(15, 23, 42), font=self.font_bold)
            y += 20
            detail = (
                f"{group['piece_count']} pcs | {group.get('total_weight_label', str(group['estimated_weight_g']) + ' g')} | "
                f"{group.get('composition_guess', 'mixed textile')}"
            )
            legend.text((lx + 78, y), _ellipsize(detail, 56), fill=(71, 85, 105), font=self.font_small)
            y += 17
            ids = "Pieces " + ", ".join(f"{group['sort_group_id']}{pid}" for pid in group.get("piece_ids", []))
            legend.text((lx + 78, y), _ellipsize(ids, 56), fill=(100, 116, 139), font=self.font_small)
            y += 30
        return out

    @staticmethod
    def _label_position(piece) -> tuple[int, int]:
        """Centroid of the outline (offset so the badge is centered), else bbox corner."""
        x, y, _, _ = piece["bbox"]
        contour = piece.get("contour") or []
        if len(contour) >= 3:
            moments = cv2.moments(np.array(contour, dtype=np.int32))
            if moments["m00"]:
                cx = int(moments["m10"] / moments["m00"])
                cy = int(moments["m01"] / moments["m00"])
                return max(2, cx - 18), max(2, cy - 12)
        return x + 4, y + 4


class PieceTable:
    """Flat per-piece rows for the debug table / CSV export."""

    @staticmethod
    def rows(pieces: list[dict]) -> list[dict]:
        return [
            {
                "piece_id": piece["id"],
                "bin": piece.get("sort_group_id"),
                "color": piece["color_name"],
                "color_family": piece.get("color_family"),
                "pattern": piece.get("pattern_type"),
                "fabric_type": piece.get("fabric_type_guess"),
                "material_family": piece.get("material_family"),
                "weave_or_knit": piece.get("weave_or_knit"),
                "composition": piece.get("composition_guess"),
                "confidence": piece.get("fabric_confidence"),
                "shape": piece.get("shape_label"),
                "size": piece.get("size_label"),
                "area_cm2": piece.get("area_cm2"),
                "estimated_weight_g": piece.get("estimated_weight_g"),
                "weight_label": piece.get("weight_label"),
                "evidence": piece.get("material_evidence"),
            }
            for piece in pieces
        ]
