#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AEGRA_SPIKE_ENV_FILE:-${HOME}/.my_best/.env}"
PID_FILE="$SCRIPT_DIR/.aegra.pid"
LOG_FILE="$SCRIPT_DIR/aegra.log"

if [[ -f "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
  printf 'Aegra already running (pid %s)\n' "$(<"$PID_FILE")"
  exit 0
fi

"$SCRIPT_DIR/scripts/check-env.sh"

env_value() {
  awk -F= -v key="$1" '$1 == key { print $2; exit }' "$ENV_FILE"
}

postgres_port="${AEGRA_SPIKE_POSTGRES_PORT:-$(env_value AEGRA_SPIKE_POSTGRES_PORT)}"
redis_port="${AEGRA_SPIKE_REDIS_PORT:-$(env_value AEGRA_SPIKE_REDIS_PORT)}"
server_port="${AEGRA_SPIKE_PORT:-$(env_value AEGRA_SPIKE_PORT)}"
postgres_port="${postgres_port:-55432}"
redis_port="${redis_port:-56379}"
server_port="${server_port:-2026}"

docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.yml" up -d --remove-orphans

export AEGRA_CONFIG="$SCRIPT_DIR/aegra.json"
export POSTGRES_HOST="127.0.0.1"
export POSTGRES_PORT="$postgres_port"
export POSTGRES_DB="aegra_spike"
export POSTGRES_USER="aegra_spike"
export POSTGRES_PASSWORD="aegra_spike"
export REDIS_BROKER_ENABLED="true"
export REDIS_URL="redis://127.0.0.1:${redis_port}/0"
export PYTHONPATH="$SCRIPT_DIR/../../src:$SCRIPT_DIR:${PYTHONPATH:-}"
export PORT="$server_port"

if [[ "$(env_value LANGFUSE_ENABLED | tr '[:upper:]' '[:lower:]')" == "true" ]]; then
  export OTEL_TARGETS="${OTEL_TARGETS:-LANGFUSE}"
fi

uv run --project "$SCRIPT_DIR" --env-file "$ENV_FILE" \
  python "$SCRIPT_DIR/validate_config.py" "$SCRIPT_DIR/aegra.json"

nohup uv run --project "$SCRIPT_DIR" --env-file "$ENV_FILE" \
  uvicorn aegra_api.main:app --host 127.0.0.1 --port "$PORT" \
  >"$LOG_FILE" 2>&1 </dev/null &
echo $! >"$PID_FILE"

for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    printf 'Aegra started locally with uv (pid %s), log: %s\n' "$(<"$PID_FILE")" "$LOG_FILE"
    exit 0
  fi
  if ! kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
    printf 'Aegra exited during startup; see %s\n' "$LOG_FILE" >&2
    exit 1
  fi
  sleep 0.5
done

printf 'Aegra did not become ready; see %s\n' "$LOG_FILE" >&2
exit 1
