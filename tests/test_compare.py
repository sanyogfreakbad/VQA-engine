"""
Test client — run a comparison from Python.

Usage:
    python tests/test_compare.py figma.png web.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests


def main():
    if len(sys.argv) < 3:
        print("Usage: python tests/test_compare.py <figma.png> <web.png> [base_url]")
        sys.exit(1)

    figma_path = Path(sys.argv[1])
    web_path = Path(sys.argv[2])
    base_url = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000"

    print(f"Figma : {figma_path}")
    print(f"Web   : {web_path}")
    print(f"Server: {base_url}")
    print()

    with open(figma_path, "rb") as f_figma, open(web_path, "rb") as f_web:
        resp = requests.post(
            f"{base_url}/compare",
            files={
                "figma": (figma_path.name, f_figma, "image/png"),
                "web": (web_path.name, f_web, "image/png"),
            },
            params={"skip_validation": False},
        )

    resp.raise_for_status()
    data = resp.json()

    # Print summary
    print(f"Total diffs: {data['total_diffs']}")
    print(f"By severity: {data['by_severity']}")
    print(f"By type:     {data['by_type']}")
    print(f"Summary:     {data['summary']}")
    print()

    # Print table
    print(f"{'Element':<25} {'Type':<10} {'Sub-type':<18} {'Figma':<18} {'Web':<18} {'Delta':<15} {'Sev':<9} {'Conf':.4}")
    print("─" * 140)
    for d in data["diffs"]:
        print(
            f"{d['element']:<25} "
            f"{d['diff_type']:<10} "
            f"{d['sub_type']:<18} "
            f"{str(d['figma_value']):<18} "
            f"{str(d['web_value']):<18} "
            f"{d['delta']:<15} "
            f"{d['severity']:<9} "
            f"{d['confidence']:.2f}"
        )

    # Save full JSON
    out_path = Path("comparison_result.json")
    out_path.write_text(json.dumps(data, indent=2))
    print(f"\nFull JSON saved to {out_path}")


if __name__ == "__main__":
    main()
