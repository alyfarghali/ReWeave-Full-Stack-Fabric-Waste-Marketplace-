"""Cleaning up raw SAM masks: keep fabric pieces, drop everything else.

SAM segments *everything* — the table, the marker, the ruler, shadows, and
the same scrap several times over. ``MaskFilter`` keeps one mask per fabric
piece and records why every other mask was discarded (for the debug view).
"""

from __future__ import annotations

import cv2
import numpy as np

MIN_AREA_FRACTION = 0.0008
MAX_AREA_FRACTION = 0.45
MAX_DISCARD_RECORDS = 80


class _ImageContext:
    """Per-image facts every rejection rule needs."""

    def __init__(self, image_bgr, exclusion_mask):
        self.image_bgr = image_bgr
        self.h, self.w = image_bgr.shape[:2]
        self.total_area = self.h * self.w
        self.min_area = int(self.total_area * MIN_AREA_FRACTION)
        self.max_area = int(self.total_area * MAX_AREA_FRACTION)
        self.exclusion_mask = (
            exclusion_mask if exclusion_mask is not None else np.zeros((self.h, self.w), dtype=np.uint8)
        )
        self.background_bgr = self._estimate_background_bgr(image_bgr)

    @staticmethod
    def _estimate_background_bgr(image_bgr):
        """Median color of the four corners — almost always bare table."""
        h, w = image_bgr.shape[:2]
        patch = max(12, min(w, h) // 18)
        patches = [
            image_bgr[:patch, :patch],
            image_bgr[:patch, w - patch : w],
            image_bgr[h - patch : h, :patch],
            image_bgr[h - patch : h, w - patch : w],
        ]
        return np.median(np.concatenate([p.reshape(-1, 3) for p in patches], axis=0), axis=0)


class MaskFilter:
    DUPLICATE_IOU = 0.62
    DUPLICATE_CONTAINMENT = 0.78

    def __init__(self, max_pieces: int):
        self.max_pieces = max_pieces

    def filter(self, raw_masks, image_bgr, exclusion_mask) -> tuple[list[np.ndarray], list[dict]]:
        """Return ``(kept_masks, discarded_records)``, kept masks largest first."""
        ctx = _ImageContext(image_bgr, exclusion_mask)
        candidates, discarded = [], []
        for raw in raw_masks:
            for mask in self._split_components(raw):
                mask = self._smooth(mask)
                reason = self.rejection_reason(mask, ctx)
                if reason:
                    discarded.append(self._discard_record(mask, reason))
                else:
                    candidates.append(mask)

        kept = self._dedupe(candidates, discarded)
        kept.sort(key=cv2.countNonZero, reverse=True)
        return kept, discarded[:MAX_DISCARD_RECORDS]

    def rejection_reason(self, mask, ctx: _ImageContext) -> str | None:
        area = int(cv2.countNonZero(mask))
        h, w = mask.shape[:2]
        if area < ctx.min_area:
            return "too_small"
        if area > ctx.max_area:
            return "too_large_or_background"

        x, y, bw, bh = cv2.boundingRect(mask)
        if bw <= 1 or bh <= 1:
            return "empty_bbox"

        reference_overlap = cv2.countNonZero(cv2.bitwise_and(mask, ctx.exclusion_mask)) / max(1, area)
        if reference_overlap > 0.14:
            return "reference_marker_or_ruler"

        if bw > w * 0.94 and bh > h * 0.94:
            return "full_image_background"

        border = max(5, min(w, h) // 120)
        border_pixels = (
            cv2.countNonZero(mask[:border, :])
            + cv2.countNonZero(mask[h - border :, :])
            + cv2.countNonZero(mask[:, :border])
            + cv2.countNonZero(mask[:, w - border :])
        )
        border_fraction = border_pixels / max(1, area)
        spans_image = bw > w * 0.74 or bh > h * 0.74
        if border_fraction > 0.035 and spans_image:
            return "touches_image_border_like_background"

        if self._is_table_background(mask, ctx, area, border_fraction, spans_image):
            return "table_background"

        if self._is_ruler_like(mask, ctx.image_bgr, (x, y, bw, bh)):
            return "ruler_or_scale_card"

        return None

    # -- rules -------------------------------------------------------------------------

    def _dedupe(self, candidates, discarded) -> list[np.ndarray]:
        """Keep the largest of any set of overlapping masks, up to max_pieces."""
        candidates = sorted(candidates, key=cv2.countNonZero, reverse=True)
        kept = []
        for mask in candidates:
            if any(self._is_duplicate(mask, existing) for existing in kept):
                discarded.append(self._discard_record(mask, "duplicate_sam_mask"))
            else:
                kept.append(mask)
            if len(kept) >= self.max_pieces:
                break
        return kept

    def _is_duplicate(self, mask, existing) -> bool:
        inter = cv2.countNonZero(cv2.bitwise_and(mask, existing))
        area = cv2.countNonZero(mask)
        existing_area = cv2.countNonZero(existing)
        union = area + existing_area - inter
        iou = inter / union if union else 0
        containment = inter / max(1, min(area, existing_area))
        return iou > self.DUPLICATE_IOU or containment > self.DUPLICATE_CONTAINMENT

    @staticmethod
    def _is_table_background(mask, ctx: _ImageContext, area, border_fraction, spans_image) -> bool:
        if area < ctx.total_area * 0.03:
            return False
        if not spans_image and area < ctx.total_area * 0.14:
            return False
        pixels = ctx.image_bgr[mask > 0]
        if len(pixels) == 0:
            return False
        color_distance = float(np.linalg.norm(pixels.mean(axis=0) - ctx.background_bgr))
        return color_distance < 34 and (spans_image or border_fraction > 0.02 or area > ctx.total_area * 0.18)

    @staticmethod
    def _is_ruler_like(mask, image_bgr, bbox) -> bool:
        x, y, bw, bh = bbox
        h, w = mask.shape[:2]
        aspect = max(bw / max(1, bh), bh / max(1, bw))
        lower_left = x < w * 0.58 and y > h * 0.50
        if not lower_left or aspect < 3.0:
            return False

        crop = image_bgr[y : y + bh, x : x + bw]
        crop_mask = mask[y : y + bh, x : x + bw] > 0
        if crop.size == 0 or crop_mask.sum() < 60:
            return False
        selected = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[crop_mask]
        low_sat = selected[:, 1] < 45
        dark_or_light = (selected[:, 2] < 85) | (selected[:, 2] > 185)
        return float(np.mean(low_sat & dark_or_light)) > 0.58

    # -- helpers -----------------------------------------------------------------------

    @staticmethod
    def _split_components(mask) -> list[np.ndarray]:
        binary = (mask > 0).astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        components = []
        for label in range(1, num_labels):
            if int(stats[label, cv2.CC_STAT_AREA]) <= 0:
                continue
            component = np.zeros(binary.shape, dtype=np.uint8)
            component[labels == label] = 255
            components.append(component)
        return components

    @staticmethod
    def _smooth(mask):
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    @staticmethod
    def _discard_record(mask, reason: str) -> dict:
        x, y, w, h = cv2.boundingRect(mask)
        return {"reason": reason, "bbox": [int(x), int(y), int(w), int(h)], "area_pixels": int(cv2.countNonZero(mask))}
