"""
Comparison pipeline — orchestrates multi-pass analysis.

  Pass 1: Element inventory  (what exists in each screenshot)
  Pass 2: Detailed diff      (property-level comparison)
  Pass 3: Validation         (re-check low-confidence items — optional)

Improvements:
  - Parallel image preprocessing
  - Parallel Pass 3 validation across regions
  - Caching for repeated comparisons
  - Configurable thresholds
  - Structured output schemas for Gemini
  - Better error tracking
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from app.schemas import (
    CategoryDiffItem,
    CompareAPIResponse,
    ComparisonResponse,
    DiffItem,
    InventoryItem,
    InventoryResponse,
    ValidationResponse,
    get_inventory_schema,
    get_comparison_schema,
    get_validation_schema,
)
from app.gemini_client import call_gemini_vision
from app.image_utils import preprocess
from app.prompts.inventory import INVENTORY_SYSTEM, INVENTORY_USER
from app.prompts.compare import COMPARE_SYSTEM, build_compare_prompt
from app.prompts.validate import VALIDATE_SYSTEM, build_validate_prompt
from app.config import get_settings
from app.cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Track statistics and dropped items for transparency."""
    dropped_inventory_items: list[dict] = field(default_factory=list)
    dropped_diff_items: list[dict] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)
    cache_hit: bool = False


async def run_comparison(
    figma_raw: bytes,
    web_raw: bytes,
    *,
    skip_validation: bool = False,
    skip_cache: bool = False,
) -> CompareAPIResponse:
    """
    Full comparison pipeline. Returns the final API response.
    
    Features:
    - Parallel image preprocessing
    - Caching for identical image pairs
    - Parallel validation across regions
    - Configurable confidence thresholds
    """
    settings = get_settings()
    stats = PipelineStats()
    cache = get_cache()
    
    # ── Check cache ───────────────────────────────────────────────────────
    if settings.cache_enabled and not skip_cache:
        cached = cache.get(figma_raw, web_raw)
        if cached is not None:
            logger.info("Cache hit — returning cached result")
            stats.cache_hit = True
            return CompareAPIResponse.model_validate(cached)

    # ── Pre-process (parallel) ────────────────────────────────────────────
    logger.info("Preprocessing images (parallel)")
    figma_png, web_png = await asyncio.gather(
        asyncio.to_thread(preprocess, figma_raw),
        asyncio.to_thread(preprocess, web_raw),
    )

    # ── Pass 1: Inventory ─────────────────────────────────────────────────
    logger.info("Pass 1 — Element inventory")
    inv_raw = await call_gemini_vision(
        system_prompt=INVENTORY_SYSTEM,
        user_prompt=INVENTORY_USER,
        figma_png=figma_png,
        web_png=web_png,
        response_schema=get_inventory_schema(),
    )
    inventory, dropped = _parse_inventory(inv_raw)
    stats.dropped_inventory_items = dropped
    logger.info("  Found %d elements (%d dropped)", len(inventory), len(dropped))

    # ── Pass 2: Detailed comparison ───────────────────────────────────────
    logger.info("Pass 2 — Detailed comparison")
    compare_prompt = build_compare_prompt(inventory)
    cmp_raw = await call_gemini_vision(
        system_prompt=COMPARE_SYSTEM,
        user_prompt=compare_prompt,
        figma_png=figma_png,
        web_png=web_png,
        response_schema=get_comparison_schema(),
    )
    comparison, dropped = _parse_comparison(cmp_raw)
    stats.dropped_diff_items = dropped
    logger.info("  Found %d diffs (%d dropped)", len(comparison.diffs), len(dropped))

    # ── Pass 3: Validation (optional, parallel) ───────────────────────────
    diffs = comparison.diffs
    if not skip_validation:
        diffs, failures = await _run_validation_parallel(diffs, figma_png, web_png)
        stats.validation_failures = failures

    # ── Post-process ──────────────────────────────────────────────────────
    # Filter out "missing-in-figma" — Figma is the source of truth
    figma_only_items = [d for d in diffs if d.sub_type == "missing-in-figma"]
    if figma_only_items:
        logger.info("Filtering out %d 'missing-in-figma' items (Figma is source of truth)", 
                    len(figma_only_items))
    diffs = [d for d in diffs if d.sub_type != "missing-in-figma"]
    
    threshold_drop = settings.confidence_threshold_drop
    dropped_low_conf = [d for d in diffs if d.confidence < threshold_drop]
    if dropped_low_conf:
        logger.info("Dropping %d items below confidence threshold %.2f", 
                    len(dropped_low_conf), threshold_drop)
    
    diffs = [d for d in diffs if d.confidence >= threshold_drop]
    diffs = _enrich_deltas(diffs)
    diffs.sort(key=lambda d: (
        {"critical": 0, "major": 1, "minor": 2}[d.severity],
        -d.confidence,
    ))

    # ── Build response ────────────────────────────────────────────────────
    severity_counts = Counter(d.severity for d in diffs)
    type_counts = Counter(d.diff_type for d in diffs)
    
    # Group diffs by category (diff_type) for easier table mapping
    by_category: dict[str, list[CategoryDiffItem]] = {}
    for d in diffs:
        category = d.diff_type.value if hasattr(d.diff_type, 'value') else str(d.diff_type)
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(CategoryDiffItem(
            element=d.element,
            text=d.text,
            sub_type=d.sub_type,
            figma_value=d.figma_value,
            web_value=d.web_value,
            delta=d.delta,
            severity=d.severity,
        ))

    result = CompareAPIResponse(
        total_diffs=len(diffs),
        by_severity={k: severity_counts.get(k, 0) for k in ("critical", "major", "minor")},
        by_type=dict(type_counts),
        by_category=by_category,
        summary=comparison.summary,
    )
    
    # ── Cache result ──────────────────────────────────────────────────────
    if settings.cache_enabled and not skip_cache:
        cache.set(figma_raw, web_raw, result.model_dump())
        logger.info("Result cached")

    return result


# ── Internal helpers ─────────────────────────────────────────────────────────


def _parse_inventory(raw: dict) -> tuple[list[InventoryItem], list[dict]]:
    """
    Validate pass-1 output and return typed inventory.
    
    Returns: (valid_items, dropped_items_with_errors)
    """
    dropped: list[dict] = []
    
    try:
        resp = InventoryResponse.model_validate(raw)
        return resp.elements, dropped
    except Exception as exc:
        logger.warning("Full inventory validation failed: %s", exc)
    
    # Fallback: parse items individually
    items: list[InventoryItem] = []
    raw_items = raw.get("elements", raw) if isinstance(raw, dict) else raw
    
    if not isinstance(raw_items, list):
        logger.warning("Could not parse inventory, returning empty list")
        return [], [{"raw": str(raw)[:200], "error": "Not a list"}]
    
    for item in raw_items:
        try:
            items.append(InventoryItem.model_validate(item))
        except Exception as exc:
            dropped.append({"item": item, "error": str(exc)})
            logger.debug("Dropped inventory item: %s", item)
    
    return items, dropped


def _parse_comparison(raw: dict) -> tuple[ComparisonResponse, list[dict]]:
    """
    Validate pass-2 output.
    
    Returns: (comparison_response, dropped_items_with_errors)
    """
    dropped: list[dict] = []
    
    try:
        return ComparisonResponse.model_validate(raw), dropped
    except Exception as exc:
        logger.warning("Comparison schema validation failed: %s", exc)
    
    # Partial recovery
    diffs: list[DiffItem] = []
    for item in raw.get("diffs", []):
        try:
            diffs.append(DiffItem.model_validate(item))
        except Exception as exc:
            dropped.append({"item": item, "error": str(exc)})
            logger.debug("Dropped diff item: %s", item)
    
    return ComparisonResponse(
        diffs=diffs,
        summary=raw.get("summary", "Comparison completed with partial results."),
    ), dropped


async def _validate_region(
    region: str,
    region_items: list[DiffItem],
    figma_png: bytes,
    web_png: bytes,
) -> tuple[str, Optional[list[DiffItem]], Optional[str]]:
    """
    Validate a single region's items.
    
    Returns: (region_name, validated_items_or_none, error_or_none)
    """
    logger.info("Pass 3 — Validating %d items in '%s'", len(region_items), region)
    prompt = build_validate_prompt(region_items, region)
    
    try:
        val_raw = await call_gemini_vision(
            system_prompt=VALIDATE_SYSTEM,
            user_prompt=prompt,
            figma_png=figma_png,
            web_png=web_png,
            response_schema=get_validation_schema(),
        )
        val_resp = ValidationResponse.model_validate(val_raw)
        return region, val_resp.diffs, None
    except Exception as exc:
        error_msg = f"Validation failed for region '{region}': {exc}"
        logger.warning(error_msg)
        return region, None, error_msg


async def _run_validation_parallel(
    diffs: list[DiffItem],
    figma_png: bytes,
    web_png: bytes,
) -> tuple[list[DiffItem], list[str]]:
    """
    Pass 3 — re-check low-confidence items and dense regions (parallel).
    
    Returns: (final_diffs, list_of_validation_errors)
    """
    settings = get_settings()
    threshold_validate = settings.confidence_threshold_validate
    threshold_drop = settings.confidence_threshold_drop
    density_threshold = settings.region_density_threshold

    # Identify items that need validation
    low_conf = [d for d in diffs if d.confidence < threshold_validate]

    # Also validate regions with many findings (might have false positives)
    region_counts = Counter(d.region for d in diffs)
    dense_regions = {r for r, c in region_counts.items() if c > density_threshold}
    dense_items = [d for d in diffs if d.region in dense_regions and d not in low_conf]

    items_to_validate = low_conf + dense_items
    if not items_to_validate:
        logger.info("Pass 3 — Nothing to validate, skipping")
        return diffs, []

    # Group by region
    regions: dict[str, list[DiffItem]] = {}
    for item in items_to_validate:
        regions.setdefault(item.region, []).append(item)

    logger.info("Pass 3 — Validating %d regions in parallel", len(regions))

    # Validate all regions in parallel
    validation_tasks = [
        _validate_region(region, items, figma_png, web_png)
        for region, items in regions.items()
    ]
    results = await asyncio.gather(*validation_tasks)

    # Collect results and errors
    validated_map: dict[tuple[str, str], DiffItem] = {}
    failures: list[str] = []
    
    for region, validated_items, error in results:
        if error:
            failures.append(error)
            continue
        if validated_items:
            for item in validated_items:
                validated_map[(item.element, item.sub_type)] = item

    # Merge validated items back
    final: list[DiffItem] = []
    for d in diffs:
        key = (d.element, d.sub_type)
        if key in validated_map:
            final.append(validated_map.pop(key))
        else:
            final.append(d)

    # Add any NEW items discovered during validation
    for new_item in validated_map.values():
        if new_item.confidence >= threshold_drop:
            final.append(new_item)

    return final, failures


def _enrich_deltas(diffs: list[DiffItem]) -> list[DiffItem]:
    """Fill in missing or vague delta values."""
    for d in diffs:
        if d.delta and d.delta not in ("", "N/A", "n/a"):
            continue
        # Try numeric diff
        try:
            fig = float(d.figma_value.replace("px", "").strip())
            web = float(d.web_value.replace("px", "").strip())
            diff = web - fig
            sign = "+" if diff > 0 else ""
            d.delta = f"{sign}{diff:.0f}px"
        except (ValueError, AttributeError):
            d.delta = f"{d.figma_value} → {d.web_value}"
    return diffs
