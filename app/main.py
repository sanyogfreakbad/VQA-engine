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
from fastapi.responses import JSONResponse

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
    skip_validation: bool = Query(
        False,
        description="Skip Pass 3 (validation). Faster but may include more false positives.",
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
    - Automatic caching of results (use skip_cache=true to bypass)
    - Retry with exponential backoff on API failures
    - Parallel processing for faster results
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
