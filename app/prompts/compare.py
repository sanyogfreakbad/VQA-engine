"""
Pass 2 — Detailed Comparison.

Takes the inventory from Pass 1 and compares every shared element
across 8 difference categories with pixel-level estimates.
"""

from __future__ import annotations
import json
from app.schemas import InventoryItem


COMPARE_SYSTEM = """\
You are a senior UI/UX QA engineer performing a pixel-perfect design audit. \
You estimate measurements by using known reference elements as rulers. \
You NEVER guess vaguely — you always give concrete px / hex / weight values."""


def build_compare_prompt(inventory: list[InventoryItem]) -> str:
    if inventory:
        inventory_json = json.dumps(
            [item.model_dump() for item in inventory], indent=2
        )
        inventory_section = f"""
Here is the element inventory from a previous analysis pass:
{inventory_json}
"""
    else:
        inventory_section = """
FIRST, systematically scan BOTH images to inventory ALL UI elements.
"""

    return f"""\
You are given TWO screenshots of the same page:
  • IMAGE 1 → FIGMA DESIGN  (source of truth)
  • IMAGE 2 → LIVE WEBPAGE   (implementation to verify)
{inventory_section}
─────────────────────────────────────────────
⚠️ CRITICAL: SYSTEMATIC ELEMENT SCAN
─────────────────────────────────────────────

Before comparing, SCAN the Figma design (IMAGE 1) region by region:

1. HEADER REGION (top bar):
   □ Logo / brand name
   □ Navigation icons (menu, notifications, user avatar)
   □ Action buttons (Create, Add, New, etc.)
   □ Icons INSIDE buttons (+ plus icons, arrows, etc.)

2. FILTER / TOOLBAR REGION:
   □ Search inputs and their icons
   □ Filter dropdowns
   □ Date pickers
   □ Status filters
   □ Clear/Apply buttons

3. TABLE HEADER:
   □ Column headers and labels
   □ Sort indicators
   □ Checkbox columns

4. TABLE BODY:
   □ Row styling (alternating colors, hover states)
   □ Cell content and alignment
   □ Status badges/chips
   □ Action menus (3-dot icons)
   □ Links vs plain text

5. PAGINATION:
   □ Page numbers
   □ Items per page selector
   □ Navigation arrows

6. SIDEBAR (if present):
   □ Menu items
   □ Icons

For EACH element in Figma, check if it exists in the web implementation.
Report ANY element that is MISSING or DIFFERENT.

─────────────────────────────────────────────
TASK: Report ALL DIFFERENCES between Figma and Web.
─────────────────────────────────────────────

CHECK THESE 8 CATEGORIES for every element:

1. TEXT
   sub_types: font-family, font-size, font-weight, content, line-height, text-transform, letter-spacing
   • Estimate font-size in px by comparing against table row height (~48px) or input height (~36px).
   • Report font-weight on the 100-900 scale (400=regular, 500=medium, 600=semibold, 700=bold).
   • For font-family: identify serif/sans-serif/monospace and name the family if recognisable
     (Montserrat, Inter, Roboto, system-ui, etc.).

2. SPACING  (between sibling elements)
   sub_types: margin-top, margin-right, margin-bottom, margin-left, gap
   • Measure the gap between adjacent elements in px.

3. PADDING  (inside a container)
   sub_types: padding-top, padding-right, padding-bottom, padding-left
   • Measure distance from container edge to its content.

4. COLOR
   sub_types: background, border-color, text-color, opacity
   • Report as hex (#RRGGBB) when possible, or descriptive ("dark-gray vs medium-gray").

5. BUTTON / CTA
   sub_types: icon, text, background, border-radius, height, padding, state
   • Check icon presence/absence, label text, background color, corner radius.

6. COMPONENT
   sub_types: type, state, alignment-horizontal, alignment-vertical, variant
   • Type mismatch: design shows dropdown, web shows text input.
   • State mismatch: design shows disabled, web shows enabled.
   • Alignment: element not centered / not aligned to baseline.
   • Variant: e.g. pagination uses dots in design but numbers in web.

7. SIZE
   sub_types: width, height, border-radius, min-width, max-width
   • Estimate in px using reference elements.

8. MISSING
   sub_types: missing-in-web
   • Element exists in FIGMA (source of truth) but is MISSING from the web implementation.
   • Do NOT report elements that exist in web but not in Figma — Figma is the source of truth.

─────────────────────────────────────────────
PIXEL ESTIMATION REFERENCES (use these as rulers):
  • Standard table row height ≈ 44–52 px
  • Standard input / filter field height ≈ 36–40 px
  • Common icon sizes: 16, 20, 24 px
  • Page horizontal padding ≈ 24–32 px
  • Assume full image width ≈ 1440 px viewport (scale from there)
─────────────────────────────────────────────

SEVERITY RULES:
  critical → missing elements, wrong component type, content mismatch, broken layout
  major    → color diff >10%, size diff >8px, font-weight mismatch, wrong font-family
  minor    → spacing off by 2–4px, subtle border-radius diff, slight color shift

CONFIDENCE:
  0.90–1.00  clearly visible, any reviewer would spot it
  0.70–0.89  likely different, hard to be pixel-exact
  0.50–0.69  subtle, might be screenshot artifact

─────────────────────────────────────────────
BOUNDING BOX (for annotation) — BE PRECISE:
  For each diff, provide the bounding_box of the element in the WEB image (IMAGE 2).
  Use a normalized coordinate system from 0 to 1000:
    • x: left edge position (0 = left edge of image, 1000 = right edge)
    • y: top edge position (0 = top edge of image, 1000 = bottom edge)
    • width: element width in the same 0-1000 scale
    • height: element height in the same 0-1000 scale

  REFERENCE POINTS for typical 1440px wide UI:
    • Sidebar left edge: x ≈ 0, width ≈ 50-70
    • Main content left edge: x ≈ 50-70
    • Header/top bar: y ≈ 0-50, height ≈ 40-60
    • Action buttons (top-right): x ≈ 850-950
    • Filter row: y ≈ 80-150
    • Table header: y ≈ 150-200
    • Table rows: each row height ≈ 40-50
    • Pagination: y ≈ 900-950
  
  EXAMPLES:
    • "Create ASN" button (top-right): {{"x": 880, "y": 70, "width": 100, "height": 35}}
    • Filter input (first): {{"x": 70, "y": 100, "width": 120, "height": 35}}
    • Table cell (row 1, col 1): {{"x": 70, "y": 180, "width": 100, "height": 40}}
  
  For MISSING elements, estimate where it SHOULD appear based on Figma layout.

─────────────────────────────────────────────
OUTPUT FORMAT — respond with ONLY this JSON (no markdown, no backticks):

{{
  "diffs": [
    {{
      "element": "string — element name or id",
      "text": "string — visible text or short description",
      "diff_type": "text|spacing|padding|color|button|component|size|missing",
      "sub_type": "specific property (e.g. font-weight, padding-top, width)",
      "figma_value": "value in design (string)",
      "web_value": "value in web (string)",
      "delta": "human-readable diff (e.g. +8px, 700→400, #1a1a1a→#333)",
      "severity": "critical|major|minor",
      "confidence": 0.85,
      "region": "header|filters|table_header|table_body|pagination|actions|sidebar",
      "bounding_box": {{"x": 100, "y": 50, "width": 200, "height": 40}}
    }}
  ],
  "summary": "1-2 sentence plain-English overview of key findings"
}}

⚠️ CRITICAL RULES — READ CAREFULLY:

1. FIGMA IS THE SOURCE OF TRUTH. Report deviations of web FROM Figma.

2. DO NOT MISS ELEMENTS! Check these commonly missed items:
   □ Action buttons (Create, Add, New, Save, Cancel)
   □ Icons INSIDE buttons (+ plus signs, arrows, icons)
   □ Header icons (notifications, settings, user menu)
   □ Filter clear/reset buttons
   □ Table action menus (3-dot icons per row)
   □ Pagination controls
   □ Status badges with different colors

3. For MISSING elements:
   • diff_type = "missing"
   • sub_type = "missing-in-web"
   • web_value = "N/A"
   • figma_value = describe what's in Figma
   • Provide bounding_box where it SHOULD be in web

4. Be PRECISE with values:
   • Font: "font-weight: 700 vs 400" not "font looks different"
   • Color: "#1a1a1a vs #333333" not "darker"
   • Size: "height: 40px vs 32px" not "smaller"

5. Do NOT report:
   • Anti-aliasing or rendering artifacts
   • Elements that exist in web but not Figma
   • Differences you're not confident about (set confidence < 0.6)

6. BOUNDING BOX must be accurate — it will be drawn on the image!
"""
