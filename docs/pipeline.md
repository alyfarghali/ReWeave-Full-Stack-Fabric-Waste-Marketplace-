# How a scan works

One photo of a cutting table goes in. Sorted bins come out, and each bin becomes a priced marketplace lot. This page follows a photo through [`ScanPipeline.run`](../backend/app/scanning/pipeline.py).

```
photo ─▶ decode ─▶ scale ─▶ segment (SAM) ─▶ filter masks ─▶ measure ─▶ classify (vision LLM) ─▶ weigh ─▶ sort ─▶ annotate
                                                                                                              │
                                                                         POST /api/lots/from-scan ◀───────────┘
                                                                         one scan run + one lot per bin
```

## 1. Decode

[`ImageCodec.decode_upload`](../backend/app/scanning/imaging.py) reads the upload and makes a working copy capped at `VISION_MAX_IMAGE_DIMENSION` (1600 px by default). The full-resolution original is kept for scale detection, where small markers need every pixel.

## 2. Find the scale

Weight comes from area, and area needs centimeters, so the pipeline first finds something of known size. [`ScaleDetector`](../backend/app/scanning/scale.py) tries, in order:

| Method | Confidence | Notes |
|---|---|---|
| ArUco marker | high | A printed 5 cm marker (`GET /api/vision/aruco-marker`). Its corners also give a homography, so areas are perspective-corrected |
| Marker-like dark square | medium | Used only when the ArUco code can't be decoded |
| Ruler or calibration strip | medium | A visible 0–5 cm ruler |
| Table-width estimate | low | Last resort. The scan still completes, with a warning |

Every response reports `scale_method` and `scale_confidence`, so a low-confidence weight is visible, not hidden. The detector also returns an exclusion mask covering the marker or ruler, which the next stages use.

## 3. Segment

[`ReplicateSamSegmenter`](../backend/app/scanning/segmentation.py) sends the photo to Segment Anything on Replicate and asks for up to three times as many masks as the piece limit. SAM finds everything: pieces, the table, the marker, weave texture inside a piece. Setting `REPLICATE_DEPLOYMENT` routes calls to an always-warm deployment, and `POST /api/vision/warmup` boots the container while the worker is still framing the photo.

## 4. Filter the masks

[`MaskFilter`](../backend/app/scanning/mask_filter.py) turns SAM's output into one mask per piece:

1. Split each mask into connected components and smooth the edges.
2. Reject a mask, with a recorded reason, when it is too small, covers most of the image, overlaps the scale reference by more than 14%, hugs the image border like background, looks like the table surface, or looks like a ruler.
3. Remove duplicates: a mask that overlaps a kept one by IoU above 0.62, or is 78% contained in it, is dropped.

Rejected masks come back in `discarded_objects`, which makes tuning possible. The [vision lab page](../backend/app/scanning/lab.html) (`GET /api/vision/lab`) draws them.

## 5. Measure each piece

For every kept mask, [`PieceGeometry`](../backend/app/scanning/geometry.py) computes the contour, a shape label, and the area in cm² (through the homography when there is one). [`ColorAnalyzer`](../backend/app/scanning/colors.py) reads the dominant and secondary colors from the mask's pixels only, plus a pattern type such as striped or checked.

## 6. Classify the material

[`MaterialClassifier`](../backend/app/scanning/materials.py) sends the vision LLM two images: the whole photo at low detail and a contact sheet of numbered piece crops at high detail. It also sends each piece's measured color, pattern, size, and shape. The model returns fabric type, composition, fabric density (grams per square meter), and a fold factor for folded or layered pieces.

Models are tried in the order of `OPENROUTER_VISION_MODELS`. If none answers, or no key is configured, a heuristic based on color and pattern classifies the pieces, and the response carries a warning. A scan never fails just because the LLM did.

## 7. Estimate weight

[`WeightEstimator`](../backend/app/scanning/geometry.py) computes `area × density × fold factor`. If the model didn't return a density, it falls back to a per-fabric catalog value. The fold factor is clamped to 0.5–4.

Weight accuracy against a real scale has not been measured yet. The [accuracy section of the README](../README.md#accuracy) describes the evaluation.

## 8. Sort into bins

[`SortGrouper`](../backend/app/scanning/sorting.py) bins pieces by color family, material family, and pattern, then labels them A, B, C… When most pieces of one color agree on a material, that consensus overrides individual LLM outliers, so one misread scrap doesn't get its own bin.

## 9. Annotate and list

[`AnnotationRenderer`](../backend/app/scanning/annotation.py) draws each piece outlined in its bin's color with the bin letter, which is the sorting plan the worker follows at the table.

The factory portal shows the plan for review and then posts it to `POST /api/lots/from-scan`. The [scanning station](../station/README.md), which has no screen, uses `POST /api/vision/scan` to scan and list in one call. Both go through [`ScanListing`](../backend/app/marketplace/scan_listing.py): one scan run is recorded, and each bin becomes a lot, priced by [`PricingModel`](../backend/app/valuation/pricing.py) and credited with impact by [`ImpactCalculator`](../backend/app/valuation/impact.py).

## Testing

[`tests/test_scanning.py`](../backend/tests/test_scanning.py) builds a synthetic 12-piece table scene with OpenCV, stubs SAM and the LLM, and runs the whole pipeline. Because every stage is injected through `ScanPipeline`'s constructor, the stubs replace only the paid network calls; scale detection, mask filtering, measurement, and sorting run for real.
