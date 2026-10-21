from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Piece(BaseModel):
    id: int
    bbox: List[int]  # [x, y, width, height] in pixels
    color_name: str
    color_hex: str
    size_percent: float
    size_label: str  # small | medium | large
    contour: Optional[List[List[int]]] = None
    area_pixels: Optional[int] = None
    area_cm2: Optional[float] = None
    dominant_rgb: Optional[List[int]] = None
    secondary_colors: Optional[List[dict[str, Any]]] = None
    color_clusters: Optional[List[dict[str, Any]]] = None
    color_family: Optional[str] = None
    pattern_type: Optional[str] = None
    crop_data_url: Optional[str] = None
    is_fabric: Optional[bool] = None
    shape_label: Optional[str] = None
    aspect_ratio: Optional[float] = None
    fabric_type_guess: Optional[str] = None
    material_family: Optional[str] = None
    material_sort_family: Optional[str] = None
    weave_or_knit: Optional[str] = None
    composition_guess: Optional[str] = None
    fabric_confidence: Optional[str] = None
    material_evidence: Optional[str] = None
    gsm: Optional[float] = None
    fold_factor: Optional[float] = None
    estimated_weight_g: Optional[float] = None
    weight_label: Optional[str] = None
    sort_group_id: Optional[str] = None
    outline_color: Optional[str] = None


class SortGroup(BaseModel):
    color_name: str
    color_hex: str
    piece_count: int
    total_size_percent: float
    avg_size_label: str
    sort_group_id: Optional[str] = None
    outline_color: Optional[str] = None
    fabric_type_guess: Optional[str] = None
    material_family: Optional[str] = None
    material_sort_family: Optional[str] = None
    weave_or_knit: Optional[str] = None
    composition_guess: Optional[str] = None
    color_family: Optional[str] = None
    pattern_type: Optional[str] = None
    estimated_weight_g: Optional[float] = None
    total_weight_label: Optional[str] = None
    piece_ids: Optional[List[int]] = None
    sort_instruction: Optional[str] = None


class DetectResponse(BaseModel):
    image_width: int
    image_height: int
    pieces: List[Piece]
    groups: List[SortGroup]
    piece_table: Optional[List[dict[str, Any]]] = None
    annotated_image_data_url: Optional[str] = None
    scale_reference_found: Optional[bool] = None
    px_per_cm: Optional[float] = None
    marker_corners: Optional[List[List[int]]] = None
    scale_method: Optional[str] = None
    scale_confidence: Optional[str] = None
    reference_objects: List[dict[str, Any]] = Field(default_factory=list)
    discarded_objects: List[dict[str, Any]] = Field(default_factory=list)
    segmentation_method: Optional[str] = None
    llm_model: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
