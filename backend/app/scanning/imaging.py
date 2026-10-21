"""Image decoding/encoding shared by every scanning stage."""

from __future__ import annotations

import base64
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps


class ImageCodec:
    @staticmethod
    def decode_upload(image_bytes: bytes, max_dimension: int) -> tuple[np.ndarray, np.ndarray, float]:
        """Decode an uploaded photo (honoring EXIF rotation).

        Returns ``(working_bgr, original_bgr, original_to_work_scale)``; the
        working image is downscaled so its longest side is ``max_dimension``.
        """
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        w, h = image.size
        scale = min(1.0, max_dimension / max(w, h))
        original_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        if scale < 1.0:
            image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR), original_bgr, scale

    @staticmethod
    def bgr_to_pil(image_bgr: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))

    @staticmethod
    def pil_to_data_url(image: Image.Image, fmt: str = "JPEG", quality: int = 88) -> str:
        buf = BytesIO()
        if fmt == "PNG":
            image.save(buf, format="PNG")
        else:
            image.save(buf, format=fmt, quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/{fmt.lower()};base64,{b64}"

    @classmethod
    def thumbnail_data_url(cls, image_bgr: np.ndarray, max_size: int, quality: int) -> str:
        pil = cls.bgr_to_pil(image_bgr)
        pil.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return cls.pil_to_data_url(pil, quality=quality)

    @staticmethod
    def padded_crop(image_bgr: np.ndarray, bbox, pad_ratio: float) -> tuple[np.ndarray, int, int]:
        """Crop ``bbox`` plus padding; returns the crop and its top-left corner."""
        x, y, w, h = bbox
        pad = max(8, int(max(w, h) * pad_ratio))
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2 = min(image_bgr.shape[1], x + w + pad)
        y2 = min(image_bgr.shape[0], y + h + pad)
        return image_bgr[y1:y2, x1:x2], x1, y1
