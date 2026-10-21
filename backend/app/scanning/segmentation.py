"""Replicate SAM/SAM2 segmentation: photo in, one binary mask per candidate object out.

The preferred model returns a list of mask images. ``SamOutputDecoder`` also
accepts single composite mask images and recursively scans nested output
shapes so a minor Replicate wrapper change does not break scanning.
"""

from __future__ import annotations

import base64
import os
import tempfile
import urllib.request

import cv2
import numpy as np


class SegmentationError(RuntimeError):
    pass


class SamOutputDecoder:
    """Turns whatever Replicate returned into a list of uint8 masks (0/255)."""

    OUTPUT_KEYS = ("masks", "mask", "output", "image", "combined_mask", "segmentation")

    def __init__(self, target_shape: tuple[int, int]):
        self.target_shape = target_shape

    def decode(self, output) -> list[np.ndarray]:
        if output is None:
            return []
        if isinstance(output, dict):
            masks = []
            for key in self.OUTPUT_KEYS:
                if key in output:
                    masks.extend(self.decode(output[key]))
            return masks
        if isinstance(output, (list, tuple)):
            masks = []
            for item in output:
                masks.extend(self.decode(item))
            return masks

        image_bytes = self._to_bytes(output)
        if image_bytes is None:
            return []
        decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if decoded is None:
            return []
        return self._image_to_masks(decoded)

    @staticmethod
    def _to_bytes(output) -> bytes | None:
        if hasattr(output, "read"):
            return output.read()
        if hasattr(output, "url"):
            return SamOutputDecoder._read_url(output.url)
        if isinstance(output, bytes):
            return output
        if isinstance(output, str):
            if output.startswith(("http://", "https://")):
                return SamOutputDecoder._read_url(output)
            if output.startswith("data:image/"):
                return base64.b64decode(output.split(",", 1)[1])
        return None

    @staticmethod
    def _read_url(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()

    def _image_to_masks(self, decoded) -> list[np.ndarray]:
        target_h, target_w = self.target_shape
        if decoded.shape[:2] != (target_h, target_w):
            decoded = cv2.resize(decoded, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

        if decoded.ndim == 2:
            return self.components(decoded > 127)

        if decoded.shape[2] == 4:
            alpha = decoded[:, :, 3]
            if int(alpha.max()) > 0:
                return self.components(alpha > 20)
            decoded = decoded[:, :, :3]

        bgr = decoded[:, :, :3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Binary mask image, usually white foreground on black background.
        if len(np.unique(gray)) <= 8:
            return self.components(gray > max(5, int(gray.mean())))

        return self._label_image_to_masks(bgr, target_h, target_w)

    def _label_image_to_masks(self, bgr, target_h, target_w) -> list[np.ndarray]:
        """Colored label/composite mask image: quantize colors and split
        connected components per visible label color."""
        flat = bgr.reshape(-1, 3).astype(np.float32)
        sample = flat
        if len(sample) > 12000:
            sample = sample[np.linspace(0, len(sample) - 1, 12000).astype(int)]

        k = min(16, max(4, len(np.unique(sample.astype(np.uint8), axis=0)) // 8))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, _, centers = cv2.kmeans(sample, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)

        # Assign every pixel to the nearest sampled center.
        centers = centers.astype(np.float32)
        dists = ((flat[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        label_img = dists.argmin(axis=1).reshape(target_h, target_w)

        masks = []
        for idx, center in enumerate(centers):
            # Skip near-black/near-white background-like regions.
            if center.mean() < 15 or center.mean() > 242:
                continue
            masks.extend(self.components(label_img == idx))
        return masks

    @staticmethod
    def components(binary) -> list[np.ndarray]:
        """One 0/255 mask per 8-connected blob in ``binary``."""
        binary = binary.astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        masks = []
        for label in range(1, num_labels):
            if int(stats[label, cv2.CC_STAT_AREA]) <= 0:
                continue
            mask = np.zeros(binary.shape, dtype=np.uint8)
            mask[labels == label] = 255
            masks.append(mask)
        return masks


class ReplicateSamSegmenter:
    """Runs SAM on Replicate, preferring an always-warm deployment when one is
    configured and falling back to the public model if it fails."""

    def __init__(self, token: str, model: str, deployment: str = ""):
        self.token = token
        self.model = model
        self.deployment = deployment

    def describe(self, use_deployment: bool = True) -> str:
        if use_deployment and self.deployment:
            return f"replicate-deployment:{self.deployment}"
        return f"replicate:{self.model}"

    def segment(self, image_bgr, max_masks: int = 80, use_deployment: bool = True) -> list[np.ndarray]:
        replicate = self._client()

        # JPEG (visually lossless at q92) instead of PNG keeps the upload ~5-10x
        # smaller, which trims a real chunk off the SAM round trip. Segmentation
        # quality is unaffected at this quality level.
        ok, encoded = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise SegmentationError("Could not encode image for Replicate")

        deployment = self.deployment if use_deployment else ""
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            tmp.write(encoded.tobytes())
            tmp.close()
            with open(tmp.name, "rb") as image_file:
                masks, error = self._segment_with_fallback(replicate, image_file, image_bgr.shape[:2], max_masks, deployment)
        finally:
            os.unlink(tmp.name)

        if not masks:
            if error is not None:
                raise SegmentationError(f"Replicate returned no usable masks after fallback: {error}") from error
            raise SegmentationError("Replicate returned no usable masks")
        return masks

    def warmup(self, max_masks: int = 8) -> bool:
        """Fire a tiny throwaway SAM call to boot the Replicate container ahead of a
        real scan, so the worker does not pay the cold-start delay. Best effort: any
        failure is swallowed since this only ever runs in the background."""
        try:
            replicate = self._client()
        except SegmentationError:
            return False

        primer = np.full((96, 96, 3), 200, dtype=np.uint8)
        primer[24:72, 24:72] = (60, 90, 160)  # one shape so the model has something to segment
        ok, encoded = cv2.imencode(".jpg", primer, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return False
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
                tmp.write(encoded.tobytes())
                tmp.flush()
                with open(tmp.name, "rb") as image_file:
                    try:
                        self._segment_once(replicate, image_file, primer.shape[:2], max_masks, self.deployment)
                    except Exception:
                        if not self.deployment:
                            raise
                        self._segment_once(replicate, image_file, primer.shape[:2], max_masks, "")
            return True
        except Exception:
            # A warm container is the only goal here; the result is discarded.
            return False

    # -- internals ---------------------------------------------------------------

    def _client(self):
        if not self.token:
            raise SegmentationError("REPLICATE_API_TOKEN is not configured")
        try:
            import replicate
        except ImportError as exc:
            raise SegmentationError("Install the replicate package first") from exc
        os.environ["REPLICATE_API_TOKEN"] = self.token
        return replicate

    def _segment_with_fallback(self, replicate, image_file, image_shape, max_masks, deployment):
        deployment_error = None
        if deployment:
            try:
                masks = self._segment_once(replicate, image_file, image_shape, max_masks, deployment)
                if masks:
                    return masks, None
                deployment_error = SegmentationError("deployment returned no usable masks")
            except Exception as exc:
                deployment_error = exc

        try:
            return self._segment_once(replicate, image_file, image_shape, max_masks, ""), deployment_error
        except Exception as exc:
            if deployment_error is not None:
                raise SegmentationError(
                    f"deployment path failed ({deployment_error}); public model fallback failed ({exc})"
                ) from exc
            raise SegmentationError(f"Replicate SAM call failed: {exc}") from exc

    def _segment_once(self, replicate, image_file, image_shape, max_masks, deployment):
        image_file.seek(0)
        output = self._run(replicate, deployment, self._input_payload(image_file, max_masks))
        return SamOutputDecoder(image_shape).decode(output)

    def _run(self, replicate, deployment: str, input_payload: dict):
        """Run SAM either against a dedicated always-warm deployment (no cold start)
        or the public model. The deployment path returns the same output shape that
        replicate.run() produces, so mask extraction downstream is unchanged."""
        if deployment:
            prediction = replicate.deployments.predictions.create(deployment, input=input_payload)
            prediction.wait()
            if prediction.status != "succeeded":
                raise SegmentationError(
                    f"Replicate deployment prediction ended with status {prediction.status}: {prediction.error}"
                )
            return prediction.output
        return replicate.run(self._resolved_ref(replicate), input=input_payload)

    def _resolved_ref(self, replicate) -> str:
        if ":" in self.model:
            return self.model
        resolved = replicate.models.get(self.model)
        version = getattr(getattr(resolved, "latest_version", None), "id", None)
        return f"{self.model}:{version}" if version else self.model

    def _input_payload(self, image_file, max_masks: int) -> dict:
        payload = {"image": image_file}
        if "lucataco/segment-anything-2" in self.model:
            payload.update(
                {
                    "mask_limit": max_masks,
                    "points_per_side": 32,
                    "pred_iou_thresh": 0.72,
                    "stability_score_thresh": 0.88,
                    "min_mask_region_area": 80,
                    "crop_n_layers": 0,
                }
            )
        elif "yyjim/segment-anything-everything" in self.model:
            payload.update(
                {
                    "mask_only": True,
                    "mask_limit": max_masks,
                    "points_per_side": 32,
                    "pred_iou_thresh": 0.78,
                    "stability_score_thresh": 0.88,
                    "min_mask_region_area": 80,
                }
            )
        elif "meta/sam-2" in self.model:
            payload.update({"points_per_side": 32, "pred_iou_thresh": 0.82, "stability_score_thresh": 0.9})
        return payload
