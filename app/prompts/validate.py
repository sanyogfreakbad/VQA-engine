"""
Pass 3 — Validation / Refinement.

Re-examines items with low confidence or regions that produced many findings.
"""

from __future__ import annotations
import json
from app.schemas import DiffItem


VALIDATE_SYSTEM = """\
You are a senior UI/UX QA engineer performing a SECOND review of flagged \
differences. FIGMA IS THE SOURCE OF TRUTH. Be ruthless: reject false positives, \
sharpen estimates, and catch anything the first pass missed. \
Only report deviations of web FROM Figma — never report "missing-in-figma"."""


def build_validate_prompt(items: list[DiffItem], region: str) -> str:
    items_json = json.dumps(
        [item.model_dump() for item in items], indent=2
    )

    return f"""\
A previous analysis pass found these potential differences in the "{region}" region:

{items_json}

─────────────────────────────────────────────
TASK: Focus ONLY on the "{region}" region in both images.
─────────────────────────────────────────────

For EACH item above:
  1. CONFIRM  — the difference is real → update confidence to 0.85+
  2. REJECT   — it was a false positive → set confidence to 0.0
  3. REFINE   — your value estimates were imprecise → correct figma_value,
                web_value, and delta

Then CHECK: did the first pass MISS any differences in this region?
Look specifically for:
  □ Missing buttons or icons (especially action buttons like Create, Add, etc.)
  □ Missing icons INSIDE buttons (+ plus signs, arrows)
  □ Color differences in badges/status indicators
  □ Missing filter controls or dropdowns
  □ Table column differences
If found, add them as new items with confidence 0.90+.

BOUNDING BOX (must be accurate for annotation):
  For each diff, provide the bounding_box of the element in the WEB image.
  Use normalized coordinates (0-1000 scale):
    • x: left edge (0 = left of image, 1000 = right)
    • y: top edge (0 = top of image, 1000 = bottom)
    • width, height: element dimensions (0-1000)
  
  For MISSING elements, estimate where it SHOULD appear in the web image.

IMPORTANT:
  • FIGMA IS THE SOURCE OF TRUTH
  • Only report things that are in Figma but missing/different in web
  • Do NOT report "missing-in-figma" — we don't care about extra elements in web

Respond with ONLY the JSON (no markdown):

{{
  "diffs": [
    {{
      "element": "...",
      "text": "...",
      "diff_type": "...",
      "sub_type": "...",
      "figma_value": "...",
      "web_value": "...",
      "delta": "...",
      "severity": "critical|major|minor",
      "confidence": 0.0,
      "region": "{region}",
      "bounding_box": {{"x": 100, "y": 50, "width": 200, "height": 40}}
    }}
  ]
}}
"""
