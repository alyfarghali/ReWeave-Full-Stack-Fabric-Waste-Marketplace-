"""Vision endpoints: run the scan pipeline, warm up SAM, and the Vision Lab test page."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import require_operator
from ..core.config import get_settings
from ..core.database import get_db
from ..marketplace.schemas import ScanListingOut
from ..marketplace.service import LotService
from .pipeline import ScanPipeline, ScanRejected
from .scale import ArucoMarker
from .schemas import DetectResponse

logger = logging.getLogger("reweave.vision")

router = APIRouter(prefix="/api/vision", tags=["vision"])

LAB_HTML_PATH = Path(__file__).with_name("lab.html")


@router.post("/detect", response_model=DetectResponse, dependencies=[Depends(require_operator)])
async def detect(image: UploadFile = File(...), use_deployment: bool = Form(default=True)):
    """Accept a photo of mixed scraps and return detected pieces plus
    color-based groups (the "before -> after" sorting result)."""
    return await _run_pipeline(image, use_deployment)


@router.post("/scan", response_model=ScanListingOut, dependencies=[Depends(require_operator)])
async def scan_and_list(
    image: UploadFile = File(...),
    use_deployment: bool = Form(default=True),
    origin_lat: Optional[float] = Form(default=None),
    origin_lng: Optional[float] = Form(default=None),
    db: Session = Depends(get_db),
):
    """Scan a photo and list every sort bin as a marketplace lot in one call.
    Used by the fixed scanning station, which has no UI to review results first."""
    result = await _run_pipeline(image, use_deployment)
    return await run_in_threadpool(LotService(db).list_scan, result, origin_lat, origin_lng)


async def _run_pipeline(image: UploadFile, use_deployment: bool) -> dict:
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        # The pipeline blocks for 30-90 s on SAM and the vision LLM; keep it off
        # the event loop so other requests are served meanwhile.
        return await run_in_threadpool(ScanPipeline.from_settings().run, contents, use_deployment=use_deployment)
    except ScanRejected as exc:
        # Surface the real reason in the server log -- otherwise a phone just sees
        # a generic "try again" and we have no idea which stage rejected the photo.
        logger.warning(
            "vision rejected photo (%d bytes, content-type=%s, use_deployment=%s): %s",
            len(contents),
            image.content_type,
            use_deployment,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 -- log then re-raise as a clean 500
        logger.exception(
            "vision pipeline crashed (%d bytes, content-type=%s, use_deployment=%s)",
            len(contents),
            image.content_type,
            use_deployment,
        )
        raise HTTPException(status_code=500, detail=f"Vision pipeline error: {exc}") from exc


@router.post("/warmup", dependencies=[Depends(require_operator)])
async def warmup(background_tasks: BackgroundTasks):
    """Boot the Replicate SAM container in the background so the next real scan
    skips the cold-start delay. Fire-and-forget: returns immediately."""

    pipeline = ScanPipeline.from_settings()
    if not pipeline.settings.replicate_api_token:
        return {"status": "skipped"}
    background_tasks.add_task(pipeline.segmenter.warmup)
    return {"status": "warming"}


@router.get("/lab", response_class=HTMLResponse)
def vision_lab():
    """Small backend-only testing UI for the vision pipeline."""
    return HTMLResponse(_lab_html())


@router.get("/aruco-marker")
def aruco_marker(
    marker_id: Optional[int] = Query(default=None),
    pixels: int = Query(default=700, ge=100, le=2000),
):
    marker_id = get_settings().aruco_marker_id if marker_id is None else marker_id
    png = ArucoMarker.png(marker_id, pixels)
    if png is None:
        raise HTTPException(status_code=500, detail="Could not generate marker")
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="reweave-aruco-{marker_id}.png"'},
    )


@lru_cache
def _lab_html() -> str:
    return LAB_HTML_PATH.read_text(encoding="utf-8")
