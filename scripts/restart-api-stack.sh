#!/usr/bin/env bash
# Stop a stale host uvicorn on the API port, then recreate the Docker API container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"

cd "$ROOT"

if command -v ss >/dev/null 2>&1; then
  if ss -tlnp 2>/dev/null | grep -q "127.0.0.1:${API_PORT} "; then
    echo "Stopping process bound to 127.0.0.1:${API_PORT} (stale native API)..."
    fuser -k "${API_PORT}/tcp" 2>/dev/null || true
    sleep 1
  fi
fi

echo "Rebuilding and starting API (port ${API_PORT})..."
docker compose build --no-cache api
docker compose up -d --force-recreate api postgres

echo "Waiting for API..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Health:"
curl -s "http://127.0.0.1:${API_PORT}/health" | python3 -m json.tool 2>/dev/null || curl -s "http://127.0.0.1:${API_PORT}/health"

if curl -sf "http://127.0.0.1:${API_PORT}/health" | grep -q llm_configured; then
  echo "OK: Docker API is serving the current build."
else
  echo "WARN: /health missing llm_configured — another process may still own port ${API_PORT}."
  echo "Try: API_PORT=8001 docker compose up -d --force-recreate api web"
  exit 1
fi
