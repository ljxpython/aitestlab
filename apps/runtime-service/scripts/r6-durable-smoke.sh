#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$APP_DIR/deploy/docker-compose.runtime-service.yml"
PORT="${RUNTIME_SERVICE_PORT:-8123}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is required for the R6 smoke test" >&2
  exit 2
fi

cd "$APP_DIR"
docker compose -f "$COMPOSE_FILE" up -d --build

cleanup() {
  if [[ "${R6_KEEP_SERVICES:-0}" != "1" ]]; then
    docker compose -f "$COMPOSE_FILE" down
  fi
}
trap cleanup EXIT

for _ in {1..60}; do
  if curl --fail --silent "http://127.0.0.1:${PORT}/info" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl --fail --silent "http://127.0.0.1:${PORT}/info" >/dev/null; then
  echo "Runtime Service did not become ready on port ${PORT}" >&2
  exit 1
fi

RUNTIME_DURABLE_URL="${RUNTIME_DURABLE_URL:-http://127.0.0.1:${PORT}}" \
  uv run python scripts/r6_durable_smoke.py
