"""Color naming, color families, and pattern detection for fabric masks."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


class ColorNaming:
    """Maps RGB values to human color names and stable sorting families."""

    PALETTE = {
        "white": (245, 245, 245),
        "cream": (238, 229, 205),
        "black": (25, 25, 25),
        "charcoal": (55, 58, 62),
        "gray": (132, 135, 140),
        "red": (200, 40, 40),
        "burgundy": (112, 32, 48),
        "orange": (230, 130, 40),
        "yellow": (230, 220, 60),
        "olive": (112, 126, 72),
        "green": (60, 160, 80),
        "teal": (30, 140, 145),
        "sky blue": (116, 174, 220),
        "blue": (50, 90, 200),
        "navy": (30, 40, 90),
        "purple": (130, 60, 170),
        "pink": (230, 140, 180),
        "brown": (120, 80, 50),
        "beige": (220, 200, 170),
        "denim": (70, 100, 140),
    }

    FAMILY_ALIASES = {
        "burgundy": "red",
        "maroon": "red",
        "red": "red",
        "cream": "cream",
        "beige": "cream",
        "white": "cream",
        "off white": "cream",
        "off-white": "cream",
        "denim": "navy",
        "navy": "navy",
        "blue": "navy",
        "dark blue": "navy",
        "black": "black",
        "charcoal": "black",
        "gray": "black",
        "grey": "black",
    }

    @staticmethod
    def _hsv(rgb) -> tuple[int, int, int]:
        r, g, b = [int(c) for c in rgb]
        hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0, 0]
        return int(hsv[0]), int(hsv[1]), int(hsv[2])

    @classmethod
    def closest_name(cls, rgb) -> str:
        """Return the palette name whose color is closest to ``rgb``."""
        r, g, b = rgb
        hue, sat, value = cls._hsv(rgb)
        if value < 95 and sat > 45 and 92 <= hue <= 132:
            return "navy"
        if value < 80 and sat < 55:
            return "black"

        best_name = "gray"
        best_dist = float("inf")
        for name, (pr, pg, pb) in cls.PALETTE.items():
            dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if dist < best_dist:
                best_dist = dist
                best_name = name
        return best_name

    @classmethod
    def family(cls, rgb=None, name=None, clusters=None) -> str:
        """Map noisy named colors into stable sorting families."""
        base = (name or "").lower().strip()
        if rgb is not None:
            hue, sat, value = cls._hsv(rgb)
            if value < 105 and sat > 38 and 90 <= hue <= 135:
                return "navy"
            if value < 85 and sat < 65:
                return "black"
            if sat < 42 and value > 145:
                return "cream"
            if (hue <= 10 or hue >= 170) and sat > 55 and value > 55:
                return "red"

        if base in cls.FAMILY_ALIASES:
            return cls.FAMILY_ALIASES[base]

        if clusters:
            families = [
                cls.family(rgb=cluster.get("rgb"), name=cluster.get("name"))
                for cluster in clusters
                if cluster.get("percent", 0) >= 0.08
            ]
            families = [f for f in families if f]
            if families:
                return max(set(families), key=families.count)

        return base or "mixed"

    @staticmethod
    def to_hex(rgb) -> str:
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
        return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class ColorProfile:
    """Everything the pipeline knows about one piece's color."""

    name: str
    hex: str
    rgb: tuple[int, int, int]
    family: str
    pattern: str
    clusters: list[dict] = field(default_factory=list)

    @property
    def secondary(self) -> list[dict]:
        return self.clusters[1:]


class ColorAnalyzer:
    """Extracts a ColorProfile from the pixels under a fabric mask."""

    def profile(self, image_bgr, mask) -> ColorProfile:
        clusters = self.clusters(image_bgr, mask)
        if clusters:
            rgb = tuple(clusters[0]["rgb"])
            name, hex_ = clusters[0]["name"], clusters[0]["hex"]
        else:
            rgb = self.dominant_rgb(image_bgr, mask)
            name, hex_ = ColorNaming.closest_name(rgb), ColorNaming.to_hex(rgb)
        return ColorProfile(
            name=name,
            hex=hex_,
            rgb=rgb,
            family=ColorNaming.family(rgb=rgb, name=name, clusters=clusters),
            pattern=self.pattern(image_bgr, mask, clusters),
            clusters=clusters,
        )

    @staticmethod
    def dominant_rgb(image_bgr, mask):
        """Return the dominant RGB color inside ``mask``.

        K-means is more stable than a mean for printed fabrics, shadows, and
        pieces with frayed light edges.
        """
        pixels_bgr = image_bgr[mask > 0]
        if len(pixels_bgr) == 0:
            return (128, 128, 128)

        pixels_rgb = pixels_bgr[:, ::-1].astype(np.float32)

        # Drop extreme shadow/highlight pixels when enough pixels remain.
        hsv = cv2.cvtColor(pixels_bgr.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        keep = (hsv[:, 2] > 25) & (hsv[:, 2] < 245)
        if keep.sum() > 80:
            pixels_rgb = pixels_rgb[keep]

        if len(pixels_rgb) > 5000:
            pixels_rgb = pixels_rgb[np.linspace(0, len(pixels_rgb) - 1, 5000).astype(int)]

        k = min(4, max(1, len(pixels_rgb) // 50))
        if k == 1:
            return tuple(int(c) for c in pixels_rgb.mean(axis=0))

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, 0.5)
        _, labels, centers = cv2.kmeans(pixels_rgb, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels.flatten(), minlength=k)
        color = centers[int(counts.argmax())]
        return tuple(int(max(0, min(255, c))) for c in color)

    @staticmethod
    def clusters(image_bgr, mask, max_clusters: int = 5) -> list[dict]:
        pixels_bgr = image_bgr[mask > 0]
        if len(pixels_bgr) == 0:
            return []

        hsv = cv2.cvtColor(pixels_bgr.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        keep = (hsv[:, 2] > 25) & (hsv[:, 2] < 248)
        if keep.sum() > 100:
            pixels_bgr = pixels_bgr[keep]

        pixels_rgb = pixels_bgr[:, ::-1].astype(np.float32)
        if len(pixels_rgb) > 6000:
            pixels_rgb = pixels_rgb[np.linspace(0, len(pixels_rgb) - 1, 6000).astype(int)]

        k = min(max_clusters, max(1, len(pixels_rgb) // 80))
        if k == 1:
            rgb = tuple(int(c) for c in pixels_rgb.mean(axis=0))
            return [{"name": ColorNaming.closest_name(rgb), "hex": ColorNaming.to_hex(rgb), "rgb": list(rgb), "percent": 1.0}]

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, 0.5)
        _, labels, centers = cv2.kmeans(pixels_rgb, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        counts = np.bincount(labels.flatten(), minlength=k).astype(float)

        clusters = []
        for idx in counts.argsort()[::-1]:
            percent = float(counts[idx] / counts.sum()) if counts.sum() else 0
            if percent < 0.04:
                continue
            rgb = tuple(int(max(0, min(255, c))) for c in centers[idx])
            clusters.append(
                {
                    "name": ColorNaming.closest_name(rgb),
                    "hex": ColorNaming.to_hex(rgb),
                    "rgb": list(rgb),
                    "percent": round(percent, 3),
                }
            )
        return clusters

    @classmethod
    def pattern(cls, image_bgr, mask, clusters) -> str:
        """solid | floral | checkered | striped | print | mixed"""
        if len(clusters) <= 1 or clusters[0]["percent"] > 0.82:
            return "solid"

        names = {cluster["name"] for cluster in clusters}
        families = {ColorNaming.family(rgb=c.get("rgb"), name=c.get("name")) for c in clusters}
        if len(families) <= 1 or len(names) <= 1:
            return "solid"

        if {"pink", "green"} & names and len(clusters) >= 4 and clusters[0]["percent"] < 0.72:
            return "floral"

        x, y, w, h = cv2.boundingRect(mask)
        crop_gray = cv2.cvtColor(image_bgr[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
        crop_mask = mask[y : y + h, x : x + w] > 0
        if crop_gray.size == 0 or crop_mask.sum() < 50:
            return "mixed"

        intensity_std = float(np.std(crop_gray[crop_mask]))
        if intensity_std < 18 and len(names) <= 2:
            return "solid"

        masked = np.where(crop_mask, crop_gray.astype(np.float32), np.nan)
        row_profile = cls._nan_profile(masked, axis=1)
        col_profile = cls._nan_profile(masked, axis=0)
        row_std = float(np.nanstd(row_profile)) if row_profile.size else 0.0
        col_std = float(np.nanstd(col_profile)) if col_profile.size else 0.0

        if min(row_std, col_std) > 19 and len(names) >= 2:
            return "checkered"
        if max(row_std, col_std) > 20 and max(row_std, col_std) > min(row_std, col_std) * 1.8:
            return "striped"
        if len(clusters) >= 4 and clusters[0]["percent"] < 0.70:
            return "print"
        return "mixed"

    @staticmethod
    def _nan_profile(masked_gray, axis):
        with np.errstate(invalid="ignore", divide="ignore"):
            profile = np.nanmean(masked_gray, axis=axis)
        return profile[~np.isnan(profile)]
