#!/usr/bin/env bash
# F1 smoke test — verifies OpenWebUI, Pipelines server, and backend are reachable.
# Usage: ./healthcheck.sh [backend_url]
# Default backend URL: http://localhost:8000

set -euo pipefail

BACKEND_URL="${1:-http://localhost:8000}"
OPENWEBUI_URL="http://localhost:3000"
PIPELINES_URL="http://localhost:9099"

PASS=0
FAIL=0

check() {
    local label="$1"
    local url="$2"
    local expected_status="${3:-200}"

    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    if [ "$status" = "$expected_status" ]; then
        echo "  PASS  $label ($status)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $label — expected $expected_status, got $status"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== ArchMind F1 Health Check ==="
echo ""

echo "--- OpenWebUI ---"
check "OpenWebUI root" "$OPENWEBUI_URL/" "200"
check "OpenWebUI API models" "$OPENWEBUI_URL/api/models" "401"

echo ""
echo "--- Pipelines Server ---"
check "Pipelines health" "$PIPELINES_URL/" "200"
check "Pipelines models" "$PIPELINES_URL/v1/models" "403"

echo ""
echo "--- ArchMind Backend ---"
check "Backend health" "$BACKEND_URL/api/v1/health" "200"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
