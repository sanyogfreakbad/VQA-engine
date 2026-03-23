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
    inventory_json = json.dumps(
        [item.model_dump() for item in inventory], indent=2
    )

    return f"""\
You are given TWO screenshots of the same page:
  • IMAGE 1 → FIGMA DESIGN  (source of truth)
  • IMAGE 2 → LIVE WEBPAGE   (implementation to verify)

Here is the element inventory from a previous analysis pass:
{inventory_json}

─────────────────────────────────────────────
TASK: Compare every element that exists in BOTH images.
Report ONLY the DIFFERENCES. Skip properties that match.
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
      "region": "header|filters|table_header|table_body|pagination|actions|sidebar"
    }}
  ],
  "summary": "1-2 sentence plain-English overview of key findings"
}}

IMPORTANT:
  • FIGMA IS THE SOURCE OF TRUTH. Report only deviations of web FROM Figma.
  • Do NOT report "missing-in-figma" — we only care about what's in Figma but missing/different in web.
  • Be precise. "Font looks different" is NOT acceptable.
    Say "font-weight: 700 vs 400" or "font-family: Montserrat vs system sans-serif".
  • Always give estimated px / hex / numeric values.
  • delta must show the math: "+8px", "700 → 600", "#1a1a1a → #333333".
  • Do NOT report anti-aliasing or sub-pixel rendering artefacts.
  • Do NOT hallucinate elements. If you cannot clearly see a property, set confidence < 0.6.
  • For MISSING elements (in web), set web_value to "N/A" and figma_value to the expected value.
"""
