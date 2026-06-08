#!/usr/bin/env bash
# Phase 1 smoke test — run against Docker API or native uvicorn.
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
TICKER="${SMOKE_TICKER:-AAPL}"
MAX_SECONDS="${SMOKE_MAX_SECONDS:-10}"
TMP=$(mktemp)

cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

echo "TradeSentinel smoke test"
echo "  API_URL=$API_URL"
echo "  TICKER=$TICKER"

curl -sf "$API_URL/health" | tee /dev/stderr
echo ""

start=$(date +%s.%N)
curl -sf "$API_URL/api/v1/context/$TICKER?summarize=true" -o "$TMP"
end=$(date +%s.%N)
elapsed=$(python3 -c "print(round(float('$end') - float('$start'), 2))")

python3 - "$TMP" "$TICKER" "$elapsed" "$MAX_SECONDS" <<'PY'
import json, sys
path, ticker, elapsed, max_seconds = sys.argv[1:5]
with open(path) as f:
    data = json.load(f)
assert data.get("ticker") == ticker.upper(), data
bullets = data.get("summary", {}).get("bullets", [])
assert len(bullets) == 3, f"expected 3 bullets, got {len(bullets)}"
print(f"Ticker: {data.get('ticker')}")
print(f"Price: {data.get('price')}")
print(f"RSI: {data.get('rsi')}")
print(f"Warnings: {len(data.get('warnings', []))}")
for b in bullets:
    print(f"  - {b[:100]}")
print(f"Elapsed: {elapsed}s")
if float(elapsed) > float(max_seconds):
    raise SystemExit(f"FAIL: exceeded {max_seconds}s budget")
print("PASS")
PY
