"""The scan pipeline: one table photo in, sorted bins out.

    decode photo
      → ScaleDetector        find ArUco marker / ruler → px per cm
      → ReplicateSamSegmenter SAM masks for everything in the photo
      → MaskFilter           keep fabric pieces, drop table/marker/duplicates
      → ColorAnalyzer + PieceGeometry   per-piece color, pattern, shape, area
      → MaterialClassifier   vision LLM: fabric type, composition, GSM
      → WeightEstimator      area × GSM × fold factor
      → SortGrouper          bins A, B, C… by color/material/pattern
      → AnnotationRenderer   annotated sorting-plan image for the worker
"""

from __future__ import annotations

import cv2

from ..core.config import Settings, get_settings
from ..core.openrouter import OpenRouterClient
from .annotation import AnnotationRenderer, PieceTable
from .colors import ColorAnalyzer
from .geometry import PieceGeometry, WeightEstimator
from .imaging import ImageCodec
from .mask_filter import MaskFilter
from .materials import MaterialClassifier
from .scale import ScaleDetector, ScaleReference
from .segmentation import ReplicateSamSegmenter, SegmentationError
from .sorting import SortGrouper


class ScanRejected(ValueError):
    """The photo could not be turned into pieces (bad image, nothing found, SAM down)."""


class ScanPipeline:
    def __init__(
        self,
        settings: Settings,
        segmenter: ReplicateSamSegmenter,
        material_classifier: MaterialClassifier,
        scale_detector: ScaleDetector | None = None,
        mask_filter: MaskFilter | None = None,
        color_analyzer: ColorAnalyzer | None = None,
        grouper: SortGrouper | None = None,
        renderer: AnnotationRenderer | None = None,
    ):
        self.settings = settings
        self.segmenter = segmenter
        self.material_classifier = material_classifier
        self.scale_detector = scale_detector or ScaleDetector(settings.aruco_marker_size_cm, settings.aruco_marker_id)
        self.mask_filter = mask_filter or MaskFilter(settings.max_pieces)
        self.color_analyzer = color_analyzer or ColorAnalyzer()
        self.grouper = grouper or SortGrouper()
        self.renderer = renderer or AnnotationRenderer()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "ScanPipeline":
        settings = settings or get_settings()
        return cls(
            settings=settings,
            segmenter=ReplicateSamSegmenter(
                settings.replicate_api_token, settings.replicate_sam_model, settings.replicate_deployment
            ),
            material_classifier=MaterialClassifier(
                OpenRouterClient(settings.openrouter_api_key, app_title="Reweave Vision Lab"),
                settings.openrouter_vision_models,
                settings.openrouter_timeout_s,
            ),
        )

    def run(self, image_bytes: bytes, use_deployment: bool = True) -> dict:
        image_bgr, original_bgr, original_to_work_scale = ImageCodec.decode_upload(
            image_bytes, self.settings.max_image_dimension
        )
        h, w = image_bgr.shape[:2]

        scale = self.scale_detector.detect(
            image_bgr, original_image_bgr=original_bgr, original_to_work_scale=original_to_work_scale
        )
        masks, discarded = self._segment(image_bgr, scale, use_deployment)
        pieces = self._measure_pieces(image_bgr, masks, scale)

        # Run the vision LLM, then group on its material result so the bins the
        # worker sees are correct from the first paint (no premature guesses).
        materials = self.material_classifier.classify(image_bgr, pieces)
        warnings = [materials.warning] if materials.warning else []
        for piece in pieces:
            self._apply_material(image_bgr, piece, materials.pieces.get(piece["id"], {}))
        warnings.extend(scale.warnings())

        groups = self.grouper.group(pieces)
        return {
            "image_width": w,
            "image_height": h,
            "pieces": [{k: v for k, v in piece.items() if k != "mask"} for piece in pieces],
            "groups": groups,
            "piece_table": PieceTable.rows(pieces),
            "annotated_image_data_url": self.renderer.render(image_bgr, pieces, groups),
            "scale_reference_found": bool(scale.found),
            "px_per_cm": round(scale.px_per_cm, 3) if scale.px_per_cm else None,
            "marker_corners": scale.marker_corners,
            "scale_method": scale.method,
            "scale_confidence": scale.confidence,
            "reference_objects": scale.public_reference_objects(),
            "discarded_objects": discarded,
            "segmentation_method": self.segmenter.describe(use_deployment),
            "llm_model": materials.model,
            "warnings": warnings,
        }

    # -- stages ----------------------------------------------------------------------

    def _segment(self, image_bgr, scale: ScaleReference, use_deployment: bool):
        try:
            raw_masks = self.segmenter.segment(
                image_bgr,
                max_masks=max(self.settings.max_pieces * 3, 50),
                use_deployment=use_deployment,
            )
        except SegmentationError as exc:
            raise ScanRejected(str(exc)) from exc
        masks, discarded = self.mask_filter.filter(raw_masks, image_bgr, scale.exclusion_mask)
        if not masks:
            raise ScanRejected("No fabric pieces remained after SAM mask cleanup")
        return masks, discarded

    def _measure_pieces(self, image_bgr, masks, scale: ScaleReference) -> list[dict]:
        h, w = image_bgr.shape[:2]
        total_area = h * w
        pieces = []
        for idx, mask in enumerate(masks, start=1):
            contour = PieceGeometry.contour(mask)
            if contour is None:
                continue
            x, y, bw, bh = cv2.boundingRect(contour)
            area_pixels = int(cv2.countNonZero(mask))
            size_percent = round(area_pixels / total_area * 100, 2)
            color = self.color_analyzer.profile(image_bgr, mask)
            area_cm2 = PieceGeometry.area_cm2(contour, scale.homography, scale.px_per_cm)
            pieces.append(
                {
                    "id": idx,
                    "bbox": [int(x), int(y), int(bw), int(bh)],
                    "contour": PieceGeometry.points(contour),
                    "mask": mask,
                    "area_pixels": area_pixels,
                    "area_cm2": round(area_cm2, 1) if area_cm2 is not None else None,
                    "color_name": color.name,
                    "color_hex": color.hex,
                    "dominant_rgb": [int(c) for c in color.rgb],
                    "color_family": color.family,
                    "secondary_colors": color.secondary,
                    "color_clusters": color.clusters,
                    "pattern_type": color.pattern,
                    "size_percent": size_percent,
                    "size_label": PieceGeometry.size_label(size_percent),
                    "shape_label": PieceGeometry.shape_label(mask, (x, y, bw, bh)),
                    "aspect_ratio": round(max(bw / max(1, bh), bh / max(1, bw)), 2),
                }
            )
        if not pieces:
            raise ScanRejected("No measurable fabric pieces found")
        return pieces

    @staticmethod
    def _apply_material(image_bgr, piece: dict, material: dict) -> None:
        piece.update(material)
        piece["estimated_weight_g"] = WeightEstimator.estimate_g(
            piece.get("area_cm2"),
            piece.get("fabric_type_guess", "unknown textile"),
            gsm=piece.get("gsm"),
            fold_factor=piece.get("fold_factor", 1.0),
        )
        piece["weight_label"] = WeightEstimator.label(piece.get("estimated_weight_g"))
        crop, _, _ = ImageCodec.padded_crop(image_bgr, piece["bbox"], pad_ratio=0.10)
        piece["crop_data_url"] = ImageCodec.thumbnail_data_url(crop, max_size=260, quality=86)
