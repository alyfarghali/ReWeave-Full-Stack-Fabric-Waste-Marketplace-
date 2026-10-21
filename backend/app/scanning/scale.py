"""Finding a known-size reference in the photo so pixels can become centimeters.

Priority:
1. decoded ArUco marker (trusted)
2. strict marker-like dark square (used only when ArUco fails)
3. visible 0-5 cm ruler/calibration strip (medium confidence)
4. fallback table-view width estimate (low confidence)

A decoded ArUco marker is the only high-confidence reference. Marker-like
fallback is used only when ArUco fails, because dark fabric scraps can look
square enough to trigger looser heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

DEFAULT_VIEW_WIDTH_CM = 38.0
EXCLUSION_DILATE_PX = 7


def _square_world(size_cm: float) -> np.ndarray:
    return np.array([[0.0, 0.0], [size_cm, 0.0], [size_cm, size_cm], [0.0, size_cm]], dtype=np.float32)


@dataclass
class ScaleReference:
    """How this photo maps pixels to centimeters, and what to mask out."""

    found: bool
    px_per_cm: float
    method: str  # aruco | marker_like | ruler | fallback
    confidence: str  # high | medium | low
    exclusion_mask: np.ndarray
    homography: np.ndarray | None = None
    marker_corners: list | None = None
    reference_objects: list[dict] = field(default_factory=list)

    def warnings(self) -> list[str]:
        messages = []
        if self.method == "fallback":
            messages.append(
                "No trusted ArUco marker or 0-5 cm ruler was detected; area and weight use a fallback table-view estimate."
            )
        elif self.method == "ruler":
            messages.append("ArUco marker was not decoded, so the visible 0-5 cm ruler was used for scale.")
        elif self.method == "marker_like":
            messages.append("ArUco marker was not decoded; a strict marker-like square fallback was used for scale.")

        if any(obj.get("type") == "marker_like" for obj in self.reference_objects) and self.method != "aruco":
            messages.append(
                "A marker-like square was excluded from fabric masks but could not be decoded as a trusted ArUco marker."
            )
        return messages

    def public_reference_objects(self) -> list[dict]:
        """Reference objects as JSON-safe dicts (homographies stripped)."""
        return [
            {key: _json_safe(value) for key, value in obj.items() if key != "homography"}
            for obj in self.reference_objects
        ]


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


class ArucoFinder:
    DICTIONARIES = ["DICT_4X4_50", "DICT_4X4_100", "DICT_5X5_100", "DICT_APRILTAG_16h5", "DICT_APRILTAG_25h9"]

    def __init__(self, marker_size_cm: float, marker_id: int | None):
        self.marker_size_cm = marker_size_cm
        self.marker_id = marker_id

    def find(self, image_bgr) -> dict | None:
        if not hasattr(cv2, "aruco"):
            return None
        variants = self._image_variants(image_bgr)
        for dict_name in self.DICTIONARIES:
            if not hasattr(cv2.aruco, dict_name):
                continue
            dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dict_name))
            detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
            for variant, scale, offset in variants:
                corners, ids, _ = detector.detectMarkers(variant)
                if ids is None or len(corners) == 0:
                    continue
                flat_ids = ids.flatten().tolist()
                selected_idx = 0
                if self.marker_id is not None:
                    if self.marker_id not in flat_ids:
                        continue
                    selected_idx = flat_ids.index(self.marker_id)
                pts = corners[selected_idx].reshape(4, 2).astype(np.float32)
                pts = pts / scale + np.array(offset, dtype=np.float32)
                return self._result(pts, flat_ids[selected_idx], dict_name)
        return None

    def rescale(self, reference: dict | None, scale: float) -> dict | None:
        """Map a marker found on the full-resolution image onto the working image."""
        if not reference or abs(scale - 1.0) < 1e-6:
            return reference
        pts = np.array(reference["polygon"], dtype=np.float32) * scale
        scaled = dict(reference)
        scaled["polygon"] = pts.astype(int).tolist()
        scaled["px_per_cm"] = float(reference["px_per_cm"] * scale)
        scaled["homography"], _ = cv2.findHomography(pts, _square_world(self.marker_size_cm))
        return scaled

    def _result(self, pts, marker_id, dictionary_name) -> dict:
        side_lengths = [np.linalg.norm(pts[(i + 1) % 4] - pts[i]) for i in range(4)]
        homography, _ = cv2.findHomography(pts, _square_world(self.marker_size_cm))
        return {
            "type": "aruco",
            "id": int(marker_id),
            "dictionary": dictionary_name,
            "polygon": pts.astype(int).tolist(),
            "px_per_cm": float(np.mean(side_lengths) / self.marker_size_cm),
            "homography": homography,
            "confidence": "high",
        }

    @staticmethod
    def _image_variants(image_bgr):
        """Preprocessed copies that help decode small, blurry, or low-contrast markers."""
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        variants = [(gray, 1.0, (0, 0))]
        variants.append((cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray), 1.0, (0, 0)))
        variants.append((cv2.addWeighted(gray, 1.7, cv2.GaussianBlur(gray, (0, 0), 1.4), -0.7, 0), 1.0, (0, 0)))
        variants.append(
            (cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 5), 1.0, (0, 0))
        )
        variants.append((cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC), 2.0, (0, 0)))

        # The marker usually sits in the lower-left corner of the table shot.
        x2, y1 = int(w * 0.45), int(h * 0.55)
        roi = gray[y1:h, 0:x2]
        if roi.size:
            variants.append((cv2.resize(roi, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC), 2.5, (0, y1)))
        return variants


class MarkerLikeFinder:
    """Strict high-contrast square fallback for markers ArUco could not decode."""

    def __init__(self, marker_size_cm: float):
        self.marker_size_cm = marker_size_cm

    def find(self, image_bgr) -> dict | None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        roi_y1 = int(h * 0.45)
        roi = gray[roi_y1:h, 0 : int(w * 0.45)]

        _, dark = cv2.threshold(roi, 80, 255, cv2.THRESH_BINARY_INV)
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 800 or area > w * h * 0.025:
                continue
            _, _, bw, bh = cv2.boundingRect(contour)
            if not 0.78 <= bw / max(1, bh) <= 1.28:
                continue
            rect = cv2.minAreaRect(contour + np.array([[[0, roi_y1]]], dtype=np.int32))
            box = cv2.boxPoints(rect).astype(int)
            if not self._has_marker_like_interior(gray, box):
                continue
            side_px = float((rect[1][0] + rect[1][1]) / 2.0)
            score = area + side_px * 20
            if best is None or score > best[0]:
                best = (
                    score,
                    {
                        "type": "marker_like",
                        "polygon": box.tolist(),
                        "px_per_cm": side_px / self.marker_size_cm,
                        "confidence": "medium",
                        "note": "Strict high-contrast square fallback used because ArUco could not be decoded.",
                    },
                )
        return best[1] if best else None

    @staticmethod
    def _has_marker_like_interior(gray, polygon) -> bool:
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(polygon, dtype=np.int32)], 255)
        x, y, w, h = cv2.boundingRect(np.array(polygon, dtype=np.int32))
        if w < 20 or h < 20:
            return False
        crop = gray[y : y + h, x : x + w]
        crop_mask = mask[y : y + h, x : x + w] > 0
        if crop.size == 0 or crop_mask.sum() < 400:
            return False
        values = crop[crop_mask]
        dark = float(np.mean(values < 70))
        light = float(np.mean(values > 175))
        contrast = float(np.std(values))
        edge_fraction = float(np.mean(cv2.Canny(crop, 60, 160)[crop_mask] > 0))
        return dark > 0.30 and light > 0.08 and contrast > 55 and edge_fraction > 0.025


class RulerFinder:
    """A horizontal 0-5 cm ruler/calibration strip in the lower-left of the shot."""

    RULER_LENGTH_CM = 5.0

    def find(self, image_bgr) -> dict | None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        roi_y1 = int(h * 0.55)
        roi = gray[roi_y1:h, 0 : int(w * 0.55)]
        if roi.size == 0:
            return None

        _, dark = cv2.threshold(roi, 95, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            if bw < roi.shape[1] * 0.12 or bh > roi.shape[0] * 0.35:
                continue
            if bw / max(1, bh) < 3.0:
                continue
            score = bw * 2 + cv2.contourArea(contour) / 100
            if best is None or score > best[0]:
                best = (score, (x, y, bw, bh))
        if best is None:
            return None

        _, (x, y, bw, bh) = best
        gx, gy = x, y + roi_y1
        pad_x = max(8, int(bw * 0.18))
        pad_y = max(10, int(bh * 2.5))
        poly = np.array(
            [
                [max(0, gx - pad_x), max(0, gy - pad_y)],
                [min(w - 1, gx + bw + pad_x), max(0, gy - pad_y)],
                [min(w - 1, gx + bw + pad_x), min(h - 1, gy + bh + pad_y)],
                [max(0, gx - pad_x), min(h - 1, gy + bh + pad_y)],
            ],
            dtype=np.int32,
        )
        return {
            "type": "ruler",
            "polygon": poly.tolist(),
            "px_per_cm": float(bw / self.RULER_LENGTH_CM),
            "confidence": "medium",
            "note": "Detected horizontal 0-5 cm ruler/calibration strip.",
        }


class ScaleDetector:
    def __init__(
        self,
        marker_size_cm: float,
        marker_id: int | None = None,
        fallback_view_width_cm: float = DEFAULT_VIEW_WIDTH_CM,
    ):
        self.aruco = ArucoFinder(marker_size_cm, marker_id)
        self.marker_like = MarkerLikeFinder(marker_size_cm)
        self.ruler = RulerFinder()
        self.fallback_view_width_cm = fallback_view_width_cm

    def detect(self, image_bgr, original_image_bgr=None, original_to_work_scale: float = 1.0) -> ScaleReference:
        aruco = self.aruco.find(image_bgr)
        if aruco is None and original_image_bgr is not None and original_image_bgr is not image_bgr:
            # Small markers often only decode at full resolution.
            aruco = self.aruco.rescale(self.aruco.find(original_image_bgr), float(original_to_work_scale or 1.0))
        if aruco:
            return self._from_reference(image_bgr, aruco, method="aruco", confidence="high", keep_homography=True)

        marker_like = self.marker_like.find(image_bgr)
        if marker_like:
            return self._from_reference(image_bgr, marker_like, method="marker_like", confidence="medium")

        ruler = self.ruler.find(image_bgr)
        if ruler:
            return self._from_reference(
                image_bgr, ruler, method="ruler", confidence="medium", has_corners=False
            )

        h, w = image_bgr.shape[:2]
        return ScaleReference(
            found=False,
            px_per_cm=float(w / self.fallback_view_width_cm),
            method="fallback",
            confidence="low",
            exclusion_mask=self._dilate(np.zeros((h, w), dtype=np.uint8)),
        )

    def _from_reference(
        self,
        image_bgr,
        reference: dict,
        method: str,
        confidence: str,
        keep_homography: bool = False,
        has_corners: bool = True,
    ) -> ScaleReference:
        h, w = image_bgr.shape[:2]
        exclusion = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(exclusion, [np.array(reference["polygon"], dtype=np.int32)], 255)
        reference["used_for_scale"] = True
        reference["excluded_from_masks"] = True
        return ScaleReference(
            found=True,
            px_per_cm=reference["px_per_cm"],
            method=method,
            confidence=confidence,
            exclusion_mask=self._dilate(exclusion),
            homography=reference["homography"] if keep_homography else None,
            marker_corners=reference["polygon"] if has_corners else None,
            reference_objects=[reference],
        )

    @staticmethod
    def _dilate(mask):
        return cv2.dilate(mask, np.ones((EXCLUSION_DILATE_PX, EXCLUSION_DILATE_PX), np.uint8), iterations=1)


class ArucoMarker:
    """Printable reference marker the factory places on the scan table."""

    @staticmethod
    def png(marker_id: int, pixels: int) -> bytes | None:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, pixels)
        border = max(24, pixels // 12)
        marker = cv2.copyMakeBorder(marker, border, border, border, border, cv2.BORDER_CONSTANT, value=255)
        ok, encoded = cv2.imencode(".png", marker)
        return encoded.tobytes() if ok else None
