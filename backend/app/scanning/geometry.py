"""Per-piece geometry: outlines, real-world area, shape/size labels, and weight."""

from __future__ import annotations

import cv2
import numpy as np

from .fabrics import FabricCatalog


class PieceGeometry:
    @staticmethod
    def contour(mask):
        """Simplified outer contour of the largest blob in ``mask``, or None."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        epsilon = max(1.5, 0.008 * cv2.arcLength(contour, True))
        return cv2.approxPolyDP(contour, epsilon, True)

    @staticmethod
    def points(contour) -> list[list[int]]:
        return [[int(x), int(y)] for [[x, y]] in contour.tolist()]

    @staticmethod
    def area_cm2(contour, homography, px_per_cm):
        """Area in cm², perspective-corrected when a homography is available."""
        if contour is None:
            return None
        if homography is not None:
            transformed = cv2.perspectiveTransform(contour.astype(np.float32), homography)
            area = abs(cv2.contourArea(transformed))
            if area > 0:
                return float(area)
        if px_per_cm:
            return float(cv2.contourArea(contour) / (px_per_cm**2))
        return None

    @staticmethod
    def shape_label(mask, bbox) -> str:
        area = float(cv2.countNonZero(mask))
        x, y, w, h = bbox
        if area <= 0 or w <= 0 or h <= 0:
            return "irregular"

        aspect = max(w / h, h / w)
        rectangularity = area / (w * h)

        if area < 2500:
            return "small offcut"
        if aspect >= 3.2:
            return "strip"
        if rectangularity > 0.68 and aspect < 1.8:
            return "panel"
        return "irregular"

    @staticmethod
    def size_label(size_percent: float) -> str:
        """small | medium | large, by share of the image."""
        if size_percent < 1.5:
            return "small"
        if size_percent < 5:
            return "medium"
        return "large"


class WeightEstimator:
    """weight = area × fabric GSM × fold factor."""

    @staticmethod
    def estimate_g(area_cm2, fabric_type, gsm=None, fold_factor=1.0):
        if area_cm2 is None:
            return None
        gsm_value = float(gsm or FabricCatalog.gsm(fabric_type))
        factor = max(0.5, min(4.0, float(fold_factor or 1.0)))
        return round((area_cm2 / 10000.0) * gsm_value * factor, 1)

    @staticmethod
    def label(weight_g, unknown: str = "estimate unavailable") -> str:
        if weight_g is None:
            return unknown
        if weight_g < 10:
            return f"{weight_g:.1f} g"
        if weight_g < 1000:
            return f"{weight_g:.0f} g"
        return f"{weight_g / 1000:.2f} kg"
