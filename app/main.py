"""
FastAPI application — Design QA comparison API.

Endpoints:
  POST /compare         Upload two screenshots, get a diff table
  GET  /health          Health check
  GET  /cache/stats     Cache statistics
  DELETE /cache         Clear cache
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.schemas import CompareAPIResponse
from app.pipeline import run_comparison
from app.cache import get_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Design QA — Figma vs Web Comparator",
    description=(
        "Upload a Figma design screenshot and a live webpage screenshot. "
        "Returns a structured diff table covering typography, spacing, "
        "padding, color, sizing, component type, and missing elements. "
        "Features retry logic, caching, and parallel processing for robustness."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cache/stats")
async def cache_stats():
    """Return cache statistics."""
    return get_cache().stats()


@app.delete("/cache")
async def clear_cache():
    """Clear the comparison cache."""
    get_cache().clear()
    return {"status": "cleared"}


@app.post("/compare", response_model=CompareAPIResponse)
async def compare(
    figma: UploadFile = File(..., description="Figma design screenshot (PNG/JPG)"),
    web: UploadFile = File(..., description="Web page screenshot (PNG/JPG)"),
    fast_mode: bool = Query(
        False,
        description="Skip inventory pass. Set true for faster but potentially less thorough results.",
    ),
    skip_validation: bool = Query(
        False,
        description="Skip validation pass. Set true for faster but less accurate results.",
    ),
    skip_cache: bool = Query(
        False,
        description="Bypass cache and force fresh comparison.",
    ),
):
    """
    Compare a Figma screenshot against a web screenshot.

    Returns a table of differences grouped by type with severity,
    confidence scores, and calculated deltas.
    
    Features:
    - Full 3-pass analysis: Inventory → Comparison → Validation (default)
    - Automatic caching of results (use skip_cache=true to bypass)
    - Annotated web image with diff markers (retrievable via /compare/{comparison_id}/image)
    
    Pipeline:
    - Pass 1: Element inventory (identifies all UI elements in both images)
    - Pass 2: Detailed comparison (finds differences with bounding boxes)
    - Pass 3: Validation (filters false positives, catches missed items)
    
    Speed options:
    - Default (full mode): ~2-3min (most accurate)
    - fast_mode=true: ~60-90s (skips inventory)
    - fast_mode=true, skip_validation=true: ~30-60s (fastest, least accurate)
    """
    # ── Validate uploads ─────────────────────────────────────────────────
    for label, f in [("figma", figma), ("web", web)]:
        if f.content_type and f.content_type not in ALLOWED_MIME:
            raise HTTPException(
                status_code=400,
                detail=f"{label}: unsupported format '{f.content_type}'. Use PNG or JPG.",
            )

    figma_bytes = await figma.read()
    web_bytes = await web.read()

    for label, data in [("figma", figma_bytes), ("web", web_bytes)]:
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"{label}: file exceeds 20 MB limit.",
            )
        if len(data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"{label}: empty file.",
            )

    # ── Run pipeline ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        result = await run_comparison(
            figma_bytes,
            web_bytes,
            skip_inventory=fast_mode,
            skip_validation=skip_validation,
            skip_cache=skip_cache,
        )
    except ValueError as exc:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal comparison error.")

    elapsed = time.perf_counter() - t0
    logger.info(
        "Comparison complete: %d diffs in %.1fs",
        result.total_diffs,
        elapsed,
    )

    return result


@app.get("/compare/{comparison_id}/image")
async def get_annotated_image(comparison_id: str):
    """
    Retrieve the annotated web image for a comparison.
    
    The annotated image shows red bounding boxes around each detected
    difference, with numbered markers matching the diff_ids in the
    comparison response.
    
    Args:
        comparison_id: The comparison_id returned from /compare endpoint
        
    Returns:
        PNG image with annotations
    """
    cache = get_cache()
    image_bytes = cache.get_annotated_image(comparison_id)
    
    if image_bytes is None:
        raise HTTPException(
            status_code=404,
            detail=f"Annotated image not found for comparison_id: {comparison_id[:16]}... "
                   f"The comparison may have been evicted from cache or no annotations were generated.",
        )
    
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="annotated_{comparison_id[:16]}.png"',
            "Cache-Control": "public, max-age=3600",
        },
    )
