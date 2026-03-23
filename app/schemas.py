"""
Pydantic models for the Design QA comparison pipeline.

These schemas serve double duty:
  1. Validate the structured JSON that Gemini returns
  2. Define the FastAPI response models

Also provides Gemini-compatible JSON schemas for structured output mode.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from google.genai import types


# ── Enums ────────────────────────────────────────────────────────────────────


class DiffType(str, Enum):
    TEXT = "text"
    SPACING = "spacing"
    PADDING = "padding"
    COLOR = "color"
    BUTTON = "button"
    COMPONENT = "component"
    SIZE = "size"
    MISSING = "missing"


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


# ── Pass 1 — Element Inventory ───────────────────────────────────────────────


class InventoryItem(BaseModel):
    element_id: str = Field(description="Short unique key, e.g. 'header_logo'")
    region: str = Field(description="UI region: header, filters, table_header, table_body, pagination, sidebar, actions")
    type: str = Field(description="Element kind: text, button, input, icon, badge, dropdown, table_cell, image, container, link")
    visible_text: str = Field(default="", description="Any text content visible on the element")
    present_in_figma: bool = True
    present_in_web: bool = True


class InventoryResponse(BaseModel):
    """Gemini Pass 1 output."""
    elements: list[InventoryItem]


# ── Pass 2 — Detailed Comparison ─────────────────────────────────────────────


class DiffItem(BaseModel):
    element: str = Field(description="Element name / identifier")
    text: str = Field(description="Visible text or short description")
    diff_type: DiffType
    sub_type: str = Field(description="Specific CSS-like property, e.g. font-weight, padding-top, width")
    figma_value: str = Field(description="Value observed in the Figma screenshot")
    web_value: str = Field(description="Value observed in the web screenshot")
    delta: str = Field(description="Human-readable difference, e.g. '+8px', '700 → 400'")
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0, description="LLM confidence 0-1")
    region: str = Field(description="UI region this element belongs to")


class ComparisonResponse(BaseModel):
    """Gemini Pass 2 output."""
    diffs: list[DiffItem]
    summary: str = Field(description="1-2 sentence overview of key findings")


# ── Final API Response ────────────────────────────────────────────────────────


class CompareAPIResponse(BaseModel):
    """What the /compare endpoint returns."""
    total_diffs: int
    by_severity: dict[str, int] = Field(description="Count per severity level")
    by_type: dict[str, int] = Field(description="Count per diff type")
    diffs: list[DiffItem]
    summary: str


# ── Validation pass ──────────────────────────────────────────────────────────


class ValidationResponse(BaseModel):
    """Gemini Pass 3 output — refined items."""
    diffs: list[DiffItem]


# ── Gemini Structured Output Schemas ─────────────────────────────────────────
#
# These schemas enforce valid JSON structure from Gemini, reducing parsing
# errors and improving accuracy.


def get_inventory_schema() -> types.Schema:
    """Build Gemini schema for Pass 1 (Inventory) response."""
    inventory_item = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "element_id": types.Schema(type=types.Type.STRING),
            "region": types.Schema(type=types.Type.STRING),
            "type": types.Schema(type=types.Type.STRING),
            "visible_text": types.Schema(type=types.Type.STRING),
            "present_in_figma": types.Schema(type=types.Type.BOOLEAN),
            "present_in_web": types.Schema(type=types.Type.BOOLEAN),
        },
        required=["element_id", "region", "type"],
    )
    
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "elements": types.Schema(
                type=types.Type.ARRAY,
                items=inventory_item,
            ),
        },
        required=["elements"],
    )


def get_comparison_schema() -> types.Schema:
    """Build Gemini schema for Pass 2 (Comparison) response."""
    diff_item = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "element": types.Schema(type=types.Type.STRING),
            "text": types.Schema(type=types.Type.STRING),
            "diff_type": types.Schema(
                type=types.Type.STRING,
                enum=["text", "spacing", "padding", "color", "button", "component", "size", "missing"],
            ),
            "sub_type": types.Schema(type=types.Type.STRING),
            "figma_value": types.Schema(type=types.Type.STRING),
            "web_value": types.Schema(type=types.Type.STRING),
            "delta": types.Schema(type=types.Type.STRING),
            "severity": types.Schema(
                type=types.Type.STRING,
                enum=["critical", "major", "minor"],
            ),
            "confidence": types.Schema(type=types.Type.NUMBER),
            "region": types.Schema(type=types.Type.STRING),
        },
        required=["element", "text", "diff_type", "sub_type", "figma_value", "web_value", "delta", "severity", "confidence", "region"],
    )
    
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "diffs": types.Schema(
                type=types.Type.ARRAY,
                items=diff_item,
            ),
            "summary": types.Schema(type=types.Type.STRING),
        },
        required=["diffs", "summary"],
    )


def get_validation_schema() -> types.Schema:
    """Build Gemini schema for Pass 3 (Validation) response."""
    diff_item = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "element": types.Schema(type=types.Type.STRING),
            "text": types.Schema(type=types.Type.STRING),
            "diff_type": types.Schema(
                type=types.Type.STRING,
                enum=["text", "spacing", "padding", "color", "button", "component", "size", "missing"],
            ),
            "sub_type": types.Schema(type=types.Type.STRING),
            "figma_value": types.Schema(type=types.Type.STRING),
            "web_value": types.Schema(type=types.Type.STRING),
            "delta": types.Schema(type=types.Type.STRING),
            "severity": types.Schema(
                type=types.Type.STRING,
                enum=["critical", "major", "minor"],
            ),
            "confidence": types.Schema(type=types.Type.NUMBER),
            "region": types.Schema(type=types.Type.STRING),
        },
        required=["element", "text", "diff_type", "sub_type", "figma_value", "web_value", "delta", "severity", "confidence", "region"],
    )
    
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "diffs": types.Schema(
                type=types.Type.ARRAY,
                items=diff_item,
            ),
        },
        required=["diffs"],
    )
