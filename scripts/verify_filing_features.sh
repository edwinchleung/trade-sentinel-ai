#!/usr/bin/env bash
# Verify SEC filing features against a running API (default http://localhost:8000).
set -euo pipefail

API="${API_BASE:-http://localhost:8000}"

echo "=== Filing feature verification ($API) ==="

check() {
  local name="$1"
  local url="$2"
  local py_expr="$3"
  echo ""
  echo "--- $name ---"
  if ! curl -sf -m 120 "$url" | python3 -c "import sys,json; d=json.load(sys.stdin); $py_expr"; then
    echo "FAIL: $name"
    return 1
  fi
}

check "Health" "$API/health" \
  'print({k:d.get(k) for k in ("ready","warming","background_jobs_enabled")})'
check "Form 4 feed" "$API/api/v1/smart-money/feed?days=7" \
  'print({"ok":d.get("data_available"),"items":len(d.get("items",[])),"buys":d.get("stats",{}).get("buy_count"),"sells":d.get("stats",{}).get("sell_count"),"enriched":d.get("enriched_count"),"message":d.get("message")})'
check "AAPL 13F" "$API/api/v1/smart-money/13f/changes?ticker=AAPL" \
  'print({"ok":d.get("data_available"),"changes":len(d.get("changes",[])),"message":d.get("message")})'
check "SP500 conviction" "$API/api/v1/smart-money/13f/conviction?universe=sp500" \
  'print({"ok":d.get("data_available"),"rows":len(d.get("rows",[])),"filers_refreshed":d.get("filers_refreshed"),"tickers_mapped":d.get("tickers_mapped"),"message":d.get("message")})'
check "AAPL insider" "$API/api/v1/institutional/AAPL/insider" \
  'print({"ok":d.get("data_available"),"transactions":len(d.get("transactions",[]))})'
check "Activist feed" "$API/api/v1/smart-money/activist-feed?days=30" \
  'print({"ok":d.get("data_available"),"items":len(d.get("items",[])),"message":d.get("message")})'

echo ""
echo "Done. Expect feed buys+sells > 0, AAPL 13F changes >= 5 on a healthy stack."
