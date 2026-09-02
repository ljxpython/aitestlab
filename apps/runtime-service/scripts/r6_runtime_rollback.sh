#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${R6_COMPOSE_FILE:-$APP_DIR/deploy/docker-compose.runtime-service.yml}"
ENV_FILE="${R6_ENV_FILE:-$APP_DIR/deploy/.env.runtime-service}"
PREVIOUS_IMAGE="${R6_PREVIOUS_RUNTIME_IMAGE:-}"
PORT="${RUNTIME_SERVICE_PORT:-8123}"
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --previous-image)
      PREVIOUS_IMAGE="${2:-}"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$PREVIOUS_IMAGE" ]]; then
  echo "--previous-image or R6_PREVIOUS_RUNTIME_IMAGE is required" >&2
  exit 2
fi
if [[ ! "$PREVIOUS_IMAGE" =~ ^[A-Za-z0-9./_:@-]+$ ]]; then
  echo "previous image contains unsupported characters" >&2
  exit 2
fi

compose=(docker compose -f "$COMPOSE_FILE")
if [[ -f "$ENV_FILE" ]]; then
  compose+=(--env-file "$ENV_FILE")
fi
command_text="RUNTIME_SERVICE_IMAGE=$PREVIOUS_IMAGE ${compose[*]} up -d --no-build --force-recreate migrate runtime-service worker"

if [[ "$APPLY" != "1" ]]; then
  printf '%s\n' "{\"status\":\"dry-run\",\"previous_image\":\"$PREVIOUS_IMAGE\",\"command\":\"$command_text\"}"
  exit 0
fi

if [[ "${R6_ROLLBACK_CONFIRM:-}" != "1" ]]; then
  echo "R6_ROLLBACK_CONFIRM=1 is required with --apply" >&2
  exit 2
fi

RUNTIME_SERVICE_IMAGE="$PREVIOUS_IMAGE" "${compose[@]}" up -d --no-build --force-recreate migrate runtime-service worker
curl --fail --silent --show-error "http://127.0.0.1:${PORT}/ready" >/dev/null
printf '%s\n' "{\"status\":\"passed\",\"previous_image\":\"$PREVIOUS_IMAGE\",\"readiness\":\"passed\"}"
