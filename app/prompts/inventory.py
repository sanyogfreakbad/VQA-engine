"""
Pass 1 — Element Inventory.

Goal: Build a shared vocabulary of every visible UI element across
both screenshots so Pass 2 has a checklist to compare against.
"""

INVENTORY_SYSTEM = """\
You are a senior UI/UX QA engineer with 10+ years of experience \
performing pixel-perfect design audits. You are meticulous, precise, \
and never skip elements."""

INVENTORY_USER = """\
You are given TWO screenshots of the same page:
  • IMAGE 1 → FIGMA DESIGN (the source of truth)
  • IMAGE 2 → LIVE WEBPAGE  (the implementation to verify)

─────────────────────────────────────────────
TASK: Create a complete inventory of EVERY visible UI element in BOTH images.
─────────────────────────────────────────────

For each element output:
  element_id  — short unique snake_case key (e.g. "header_logo", "filter_asn_no")
  region      — one of: header, sidebar, filters, table_header, table_body,
                pagination, actions, footer, toast, modal
  type        — one of: text, button, input, icon, badge, dropdown,
                table_cell, image, container, link, checkbox, toggle,
                search_field, date_picker, tab, scroll, divider
  visible_text — any text content (empty string if none)
  present_in_figma — true / false
  present_in_web   — true / false

RULES:
  • FIGMA IS THE SOURCE OF TRUTH. Focus on cataloging elements from Figma.
  • Scan LEFT-TO-RIGHT, TOP-TO-BOTTOM so you don't skip anything.
  • Include EVERY filter field, column header, button, icon, badge,
    pagination control, and action menu that appears in FIGMA.
  • If an element exists in Figma but NOT in web, still list it
    and set present_in_web to false.
  • Elements that exist ONLY in web (not in Figma) can be noted but are less important.
  • Do NOT group multiple distinct elements into one entry. Each filter
    input, each column header, each action icon is its OWN entry.

Respond with ONLY a JSON object matching this exact structure (no markdown,
no backticks, no explanation):

{
  "elements": [
    {
      "element_id": "header_logo",
      "region": "header",
      "type": "image",
      "visible_text": "CARGOES",
      "present_in_figma": true,
      "present_in_web": true
    }
  ]
}
"""
