#!/bin/bash
# Basic healthcheck for all platform services.
set -e

BASE_URL="${BASE_URL:-http://localhost}"

services=(
  "api-gateway:8000"
  "workflow-service:8001"
  "memory-service:8002"
  "observability-service:8003"
)

all_healthy=true

for service_port in "${services[@]}"; do
  service="${service_port%%:*}"
  port="${service_port##*:}"
  url="$BASE_URL:$port/health"

  if curl -sf "$url" > /dev/null 2>&1; then
    echo "✓ $service ($url)"
  else
    echo "✗ $service ($url) — not healthy"
    all_healthy=false
  fi
done

if [ "$all_healthy" = true ]; then
  echo ""
  echo "All services healthy."
  exit 0
else
  echo ""
  echo "Some services are not healthy."
  exit 1
fi
