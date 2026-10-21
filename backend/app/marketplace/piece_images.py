"""Normalizing the per-piece crop images stored on a lot.

Older clients sent bare data-URL strings or used ``url`` / ``crop_data_url`` /
``data_url`` keys; everything is normalized to ``{"src": ..., **extra}``.
"""

from __future__ import annotations

SOURCE_KEYS = ("src", "url", "crop_data_url", "data_url")


class PieceImages:
    @staticmethod
    def source_of(image) -> str | None:
        if isinstance(image, str):
            return image or None
        if isinstance(image, dict):
            for key in SOURCE_KEYS:
                if image.get(key):
                    return image[key]
        return None

    @classmethod
    def normalize(cls, value) -> list[dict]:
        if not isinstance(value, list):
            return []
        normalized = []
        for image in value:
            src = cls.source_of(image)
            if not src:
                continue
            normalized.append({**image, "src": src} if isinstance(image, dict) else {"src": src})
        return normalized

    @classmethod
    def thumbnail(cls, value) -> str | None:
        if not isinstance(value, list) or not value:
            return None
        return cls.source_of(value[0])
