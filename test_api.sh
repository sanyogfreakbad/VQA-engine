#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Quick test — call the /compare endpoint
# ─────────────────────────────────────────────
#
# Usage:
#   ./test_api.sh path/to/figma.png path/to/web.png
#
# Prerequisites:
#   - Server running: uvicorn app.main:app --reload
#   - curl and jq installed

set -euo pipefail

FIGMA="${1:?Usage: $0 <figma.png> <web.png>}"
WEB="${2:?Usage: $0 <figma.png> <web.png>}"
BASE_URL="${3:-http://localhost:8000}"

echo "▶ Comparing:"
echo "  Figma : $FIGMA"
echo "  Web   : $WEB"
echo "  Server: $BASE_URL"
echo ""

RESPONSE=$(curl -s -X POST "${BASE_URL}/compare" \
  -F "figma=@${FIGMA}" \
  -F "web=@${WEB}")

# Pretty-print if jq is available
if command -v jq &>/dev/null; then
  echo "$RESPONSE" | jq .
else
  echo "$RESPONSE"
fi

echo ""
echo "─────────────────────────────────────"

# Summary
if command -v jq &>/dev/null; then
  TOTAL=$(echo "$RESPONSE" | jq '.total_diffs')
  CRITICAL=$(echo "$RESPONSE" | jq '.by_severity.critical // 0')
  MAJOR=$(echo "$RESPONSE" | jq '.by_severity.major // 0')
  MINOR=$(echo "$RESPONSE" | jq '.by_severity.minor // 0')
  echo "Total: $TOTAL diffs  |  Critical: $CRITICAL  Major: $MAJOR  Minor: $MINOR"
fi
