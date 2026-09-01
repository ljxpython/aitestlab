#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AEGRA_SPIKE_ENV_FILE:-${HOME}/.my_best/.env}"
PID_FILE="$SCRIPT_DIR/.aegra.pid"

if [[ -f "$PID_FILE" ]]; then
  pid="$(<"$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

args=(down)
if [[ "${1:-}" == "--volumes" ]]; then
  args+=(--volumes)
fi
docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.yml" "${args[@]}"
