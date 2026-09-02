#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${R6_COMPOSE_FILE:-${APP_DIR}/deploy/docker-compose.runtime-service.yml}"
COMPOSE_ENV_FILE="${R6_COMPOSE_ENV_FILE:-${APP_DIR}/deploy/.env.runtime-service}"
COMPOSE_PROJECT="${R6_COMPOSE_PROJECT:?R6_COMPOSE_PROJECT is required}"
RUNTIME_SERVICE_IMAGE="${RUNTIME_SERVICE_IMAGE:?RUNTIME_SERVICE_IMAGE is required}"
RUNTIME_SERVICE_PORT="${R6_RUNTIME_SERVICE_PORT:?R6_RUNTIME_SERVICE_PORT is required}"
RUNTIME_GRAPH_CONFIG="${R6_GRAPH_CONFIG:-/app/langgraph.r6.json}"
API_READY_URL="${R6_API_READY_URL:-http://127.0.0.1:${RUNTIME_SERVICE_PORT}}"
SSE_URL="${R6_SSE_URL:-http://host.docker.internal:${RUNTIME_SERVICE_PORT}}"
SSE_NETWORK="${R6_SSE_NETWORK:-bridge}"
TOKEN="${R6_TEST_TOKEN_SECRET:-${PLATFORM_RUNTIME_DELEGATION_SECRET:-}}"
ISSUER="${PLATFORM_RUNTIME_DELEGATION_ISSUER:-platform-api}"
AUDIENCE="${PLATFORM_RUNTIME_DELEGATION_AUDIENCE:-runtime-service}"
export RUNTIME_SERVICE_IMAGE RUNTIME_SERVICE_PORT RUNTIME_GRAPH_CONFIG

case "${COMPOSE_PROJECT}" in
  r6-*) ;;
  *) echo "R6_COMPOSE_PROJECT must start with r6-" >&2; exit 2 ;;
esac
[[ -f "${COMPOSE_FILE}" ]] || { echo "Compose file does not exist: ${COMPOSE_FILE}" >&2; exit 2; }
[[ -f "${COMPOSE_ENV_FILE}" ]] || { echo "Compose env file does not exist: ${COMPOSE_ENV_FILE}" >&2; exit 2; }
[[ -n "${TOKEN}" ]] || { echo "R6_TEST_TOKEN_SECRET or PLATFORM_RUNTIME_DELEGATION_SECRET is required" >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker CLI is required" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "Docker daemon is required" >&2; exit 2; }

compose=(docker compose --env-file "${COMPOSE_ENV_FILE}" -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}")

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ "${R6_KEEP_SERVICES:-0}" != "1" ]]; then
    "${compose[@]}" down --remove-orphans >/dev/null || status=1
  fi
  exit "${status}"
}
trap cleanup EXIT INT TERM

wait_api_ready() {
  local response
  for _ in $(seq 1 "${R6_API_READY_ATTEMPTS:-120}"); do
    if response="$(curl --silent --show-error --max-time 5 "${API_READY_URL%/}/ready" 2>/dev/null)" \
      && python3 -c 'import json, sys; raise SystemExit(0 if json.loads(sys.stdin.read()).get("ready") is True else 1)' <<<"${response}"; then
      return 0
    fi
    sleep 1
  done
  echo "API readiness did not pass: ${API_READY_URL%/}/ready" >&2
  return 1
}

worker_counts() {
  worker_total="$("${compose[@]}" ps -aq worker 2>/dev/null | awk 'NF { n++ } END { print n + 0 }')"
  worker_running="$(docker ps \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
    --filter "label=com.docker.compose.service=worker" \
    --filter status=running -q | awk 'NF { n++ } END { print n + 0 }')"
}

"${compose[@]}" stop worker >/dev/null 2>&1 || true
"${compose[@]}" up -d --no-build --scale worker=1 runtime-service worker >/dev/null

for _ in $(seq 1 "${R6_WORKER_READY_ATTEMPTS:-120}"); do
  worker_counts
  if [[ "${worker_total}" == "1" && "${worker_running}" == "1" ]]; then
    break
  fi
  sleep 1
done
worker_counts
if [[ "${worker_total}" != "1" || "${worker_running}" != "1" ]]; then
  echo "expected exactly one running Worker in Compose project ${COMPOSE_PROJECT}" >&2
  exit 1
fi

wait_api_ready

docker run --rm \
  --network "${SSE_NETWORK}" \
  --add-host host.docker.internal:host-gateway \
  --entrypoint python \
  -e PYTHONPATH=/app/scripts \
  -e RUNTIME_DURABLE_URL="${SSE_URL}" \
  -e R6_TEST_TOKEN_SECRET="${TOKEN}" \
  -e PLATFORM_RUNTIME_DELEGATION_ISSUER="${ISSUER}" \
  -e PLATFORM_RUNTIME_DELEGATION_AUDIENCE="${AUDIENCE}" \
  -v "${APP_DIR}/scripts/r6_network_sse_acceptance.py:/tmp/r6_network_sse_acceptance.py:ro" \
  "${RUNTIME_SERVICE_IMAGE}" \
  /tmp/r6_network_sse_acceptance.py \
  --url "${SSE_URL}" \
  --assistant-id "${R6_SSE_ASSISTANT_ID:-disconnect_demo}" \
  --worker-ready-assistant-id "${R6_SSE_WORKER_READY_ASSISTANT_ID:-recovery_demo}" \
  --api-ready-timeout "${R6_SSE_API_READY_TIMEOUT:-120}" \
  --worker-ready-timeout "${R6_SSE_WORKER_READY_TIMEOUT:-120}" \
  --timeout "${R6_SSE_STREAM_TIMEOUT:-120}" \
  --disconnect-after "${R6_SSE_DISCONNECT_AFTER:-2}"
