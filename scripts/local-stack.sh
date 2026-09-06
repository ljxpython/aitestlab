#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/apps/runtime-service"
PLATFORM_API_DIR="$ROOT_DIR/apps/platform-api"
PLATFORM_WEB_DIR="$ROOT_DIR/apps/platform-web"
STATE_DIR="${TMPDIR:-/tmp}/aitestlab-local-stack"
PID_DIR="$STATE_DIR/pids"
LOG_DIR="$STATE_DIR/logs"
RUNTIME_ENV_FILE="${RUNTIME_ENV_FILE:-$RUNTIME_DIR/.env}"
RUNTIME_PORT="${RUNTIME_PORT:-}"
PLATFORM_API_PORT="${PLATFORM_API_PORT:-2142}"
PLATFORM_WEB_PORT="${PLATFORM_WEB_PORT:-3000}"
GRAPH_CONFIG=""
STARTED_KEYS=()

mkdir -p "$PID_DIR" "$LOG_DIR"

usage() {
  cat <<'EOF'
Usage: bash scripts/local-stack.sh <command>

Commands:
  doctor   validate local env, dependencies, config, and ports
  migrate  run GraphHarbor database migrations
  start    start Runtime API/Worker, Platform API/Worker, and Platform Web
  stop     stop only processes started by this script
  restart  stop and start the local stack
  status   show managed processes and HTTP health
  logs     show recent logs; optionally pass runtime-api, runtime-worker,
           platform-api, platform-worker, or platform-web
EOF
}

die() {
  printf 'ERROR %s\n' "$1" >&2
  exit 1
}

load_runtime_env() {
  [ -f "$RUNTIME_ENV_FILE" ] || die "missing Runtime env file: $RUNTIME_ENV_FILE"
  [ -f "$PLATFORM_API_DIR/.env" ] || die "missing Platform API env file: $PLATFORM_API_DIR/.env"
  require_command python3
  local platform_runtime_secret
  platform_runtime_secret="$(python3 - "$PLATFORM_API_DIR/.env" <<'PY'
import sys
from pathlib import Path

from dotenv import dotenv_values

value = dotenv_values(Path(sys.argv[1])).get("PLATFORM_API_RUNTIME_DELEGATION_SECRET")
if not value:
    raise SystemExit("Platform runtime delegation secret is empty")
print(value)
PY
)"
  set -a
  export PLATFORM_API_RUNTIME_DELEGATION_SECRET="$platform_runtime_secret"
  # shellcheck disable=SC1090
  . "$RUNTIME_ENV_FILE"
  set +a
  RUNTIME_PORT="${RUNTIME_PORT:-${RUNTIME_SERVICE_PORT:-8123}}"
  GRAPH_CONFIG="${RUNTIME_GRAPH_CONFIG_PATH:-$RUNTIME_DIR/langgraph.json}"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

shell_quote() {
  printf '%q' "$1"
}

pid_file() {
  printf '%s/%s.pid' "$PID_DIR" "$1"
}

read_pid() {
  local file
  file="$(pid_file "$1")"
  [ -f "$file" ] || return 1
  tr -d '[:space:]' < "$file"
}

pid_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

managed_alive() {
  local pid
  pid="$(read_pid "$1" 2>/dev/null || true)"
  pid_alive "$pid"
}

port_in_use() {
  lsof -ti "tcp:$1" -sTCP:LISTEN >/dev/null 2>&1
}

check_port() {
  local key="$1"
  local port="$2"
  if port_in_use "$port" && ! managed_alive "$key"; then
    die "port $port is already in use; refusing to kill an unmanaged process"
  fi
}

spawn_detached() {
  local workdir="$1"
  local command="$2"
  local logfile="$3"

  python3 - "$workdir" "$command" "$logfile" <<'PY'
import subprocess
import sys

workdir, command, logfile = sys.argv[1:]
with open(logfile, "ab", buffering=0) as stream:
    process = subprocess.Popen(
        ["/bin/bash", "-lc", f"exec {command}"],
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
print(process.pid)
PY
}

start_process() {
  local key="$1"
  local workdir="$2"
  local command="$3"
  local logfile="$4"
  local port="${5:-}"
  local pid

  if managed_alive "$key"; then
    printf '[skip] %s already running\n' "$key"
    return
  fi
  rm -f "$(pid_file "$key")"
  [ -z "$port" ] || check_port "$key" "$port"
  pid="$(spawn_detached "$workdir" "$command" "$logfile")"
  printf '%s\n' "$pid" > "$(pid_file "$key")"
  STARTED_KEYS+=("$key")
  printf '[start] %s pid=%s\n' "$key" "$pid"
}

start_managed_key() {
  local key="$1"
  case "$key" in
    runtime-api)
      start_process runtime-api "$RUNTIME_DIR" \
        "uv run --frozen graphharbor serve --host 127.0.0.1 --port $(shell_quote "$RUNTIME_PORT") --config $(shell_quote "$GRAPH_CONFIG") --n-jobs-per-worker 0" \
        "$LOG_DIR/runtime-api.log" "$RUNTIME_PORT"
      ;;
    runtime-worker)
      start_process runtime-worker "$RUNTIME_DIR" \
        "uv run --frozen graphharbor worker --config $(shell_quote "$GRAPH_CONFIG") --n-jobs-per-worker 1" \
        "$LOG_DIR/runtime-worker.log"
      ;;
    platform-api)
      start_process platform-api "$PLATFORM_API_DIR" \
        "uv run uvicorn main:app --host 127.0.0.1 --port $(shell_quote "$PLATFORM_API_PORT") --reload" \
        "$LOG_DIR/platform-api.log" "$PLATFORM_API_PORT"
      ;;
    platform-worker)
      start_process platform-worker "$PLATFORM_API_DIR" \
        "uv run python worker.py" "$LOG_DIR/platform-worker.log"
      ;;
    platform-web)
      start_process platform-web "$PLATFORM_WEB_DIR" \
        "env VITE_PLATFORM_API_URL=/ VITE_PLATFORM_API_RUNTIME_ENABLED=true VITE_DEV_PORT=$(shell_quote "$PLATFORM_WEB_PORT") VITE_DEV_PROXY_TARGET=http://127.0.0.1:$(shell_quote "$PLATFORM_API_PORT") pnpm dev -- --host 127.0.0.1 --port $(shell_quote "$PLATFORM_WEB_PORT")" \
        "$LOG_DIR/platform-web.log" "$PLATFORM_WEB_PORT"
      ;;
    *)
      die "unknown managed process: $key"
      ;;
  esac
}

stop_process() {
  local key="$1"
  local pid
  pid="$(read_pid "$key" 2>/dev/null || true)"
  rm -f "$(pid_file "$key")"
  [ -n "$pid" ] || return 0
  pid_alive "$pid" || return 0
  printf '[stop] %s pid=%s\n' "$key" "$pid"
  kill -TERM -- "-$pid" >/dev/null 2>&1 || kill -TERM "$pid" >/dev/null 2>&1 || true
  for _ in {1..20}; do
    pid_alive "$pid" || return 0
    sleep 0.25
  done
  kill -KILL -- "-$pid" >/dev/null 2>&1 || kill -KILL "$pid" >/dev/null 2>&1 || true
}

wait_http() {
  local name="$1"
  local url="$2"
  for _ in {1..40}; do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      printf '[ready] %s %s\n' "$name" "$url"
      return
    fi
    sleep 1
  done
  die "$name did not become ready: $url"
}

require_managed_process() {
  managed_alive "$1" || die "$1 exited during startup; inspect $LOG_DIR/$1.log"
}

cleanup_startup_failure() {
  local exit_code=$?
  [ "$exit_code" -eq 0 ] && return
  set +e
  for ((i = ${#STARTED_KEYS[@]} - 1; i >= 0; i--)); do
    stop_process "${STARTED_KEYS[$i]}"
  done
  exit "$exit_code"
}

validate_runtime() {
  load_runtime_env
  require_command uv
  require_command python3
  [ -f "$GRAPH_CONFIG" ] || die "missing Runtime graph config: $GRAPH_CONFIG"
  (cd "$RUNTIME_DIR" && uv run --frozen python scripts/validate_runtime_config.py \
    --env-file "$RUNTIME_ENV_FILE")
}

check_redis() {
  (cd "$RUNTIME_DIR" && uv run --frozen python - "$RUNTIME_ENV_FILE" <<'PY'
import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from redis.asyncio import Redis


async def main() -> None:
    settings = {**dotenv_values(Path(sys.argv[1])), **os.environ}
    redis_uri = str(settings.get("REDIS_URI") or "").strip()
    if not redis_uri:
        raise SystemExit("REDIS_URI is empty")
    client = Redis.from_url(redis_uri)
    try:
        await client.ping()
    except Exception as exc:
        raise SystemExit("Redis is unavailable at REDIS_URI") from exc
    finally:
        await client.aclose()


asyncio.run(main())
print("Redis connectivity check passed")
PY
  )
}

check_postgres() {
  require_command pg_isready
  local endpoint
  endpoint="$(python3 - "$RUNTIME_ENV_FILE" <<'PY'
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

settings = dotenv_values(Path(sys.argv[1]))
uri = str(settings.get("DATABASE_URI") or "").strip()
parsed = urlparse(uri)
host = parsed.hostname or "127.0.0.1"
port = parsed.port or 5432
print(host, port)
PY
)"
  local host port
  read -r host port <<< "$endpoint"
  if ! pg_isready -q -h "$host" -p "$port"; then
    local detail
    detail="$(pg_isready -h "$host" -p "$port" 2>&1 || true)"
    local data_dir="/usr/local/var/postgresql@17"
    if [ -f "$data_dir/postmaster.pid" ]; then
      local pid
      pid="$(head -n 1 "$data_dir/postmaster.pid" 2>/dev/null || true)"
      if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
        die "PostgreSQL unavailable at $host:$port ($detail); stale postmaster.pid detected at $data_dir/postmaster.pid. Confirm the database process is stopped, remove that lock file manually, then restart PostgreSQL."
      fi
    fi
    die "PostgreSQL unavailable at $host:$port ($detail); start the configured local PostgreSQL service before starting the stack."
  fi
  printf 'PostgreSQL connectivity check passed (%s:%s)\n' "$host" "$port"
}

validate_stack() {
  validate_runtime
  check_postgres
  check_redis
  require_command curl
  require_command lsof
  require_command pnpm
  [ -f "$PLATFORM_API_DIR/.env" ] || die "missing Platform API env file: $PLATFORM_API_DIR/.env"
  (cd "$PLATFORM_API_DIR" && uv run --frozen python - "$RUNTIME_PORT" "$RUNTIME_ENV_FILE" .env <<'PY'
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

runtime_port, runtime_env_path, platform_env_path = sys.argv[1:]
runtime = {**dotenv_values(Path(runtime_env_path)), **os.environ}
platform = {**dotenv_values(platform_env_path), **os.environ}
expected_upstream = f"http://127.0.0.1:{runtime_port}"
upstream = str(platform.get("PLATFORM_API_LANGGRAPH_UPSTREAM_URL") or "").rstrip("/")
if upstream != expected_upstream:
    raise SystemExit(
        f"Platform upstream must be {expected_upstream}, got {upstream or '<empty>'}"
    )
if not platform.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET"):
    raise SystemExit("Platform runtime delegation secret is empty")
if platform["PLATFORM_API_RUNTIME_DELEGATION_SECRET"] != runtime.get(
    "PLATFORM_RUNTIME_DELEGATION_SECRET"
):
    raise SystemExit("Platform and Runtime delegation secrets do not match")
PY
  )
  check_port runtime-api "$RUNTIME_PORT"
  check_port platform-api "$PLATFORM_API_PORT"
  check_port platform-web "$PLATFORM_WEB_PORT"
}

migrate() {
  validate_runtime
  check_postgres
  (cd "$RUNTIME_DIR" && uv run --frozen graphharbor migrate upgrade)
}

start() {
  trap cleanup_startup_failure EXIT
  STARTED_KEYS=()
  validate_stack
  migrate
  start_managed_key runtime-api
  start_managed_key runtime-worker
  require_managed_process runtime-worker
  wait_http runtime-api "http://127.0.0.1:$RUNTIME_PORT/ready"
  start_managed_key platform-api
  start_managed_key platform-worker
  require_managed_process platform-worker
  wait_http platform-api "http://127.0.0.1:$PLATFORM_API_PORT/_system/health"
  start_managed_key platform-web
  wait_http platform-web "http://127.0.0.1:$PLATFORM_WEB_PORT"
  printf '[done] local stack is ready: http://127.0.0.1:%s\n' "$PLATFORM_WEB_PORT"
  trap - EXIT
}

status() {
  load_runtime_env
  for key in runtime-api runtime-worker platform-api platform-worker platform-web; do
    if managed_alive "$key"; then
      printf '%-16s running\n' "$key"
    else
      printf '%-16s stopped\n' "$key"
    fi
  done
  curl -fsS --max-time 2 "http://127.0.0.1:$RUNTIME_PORT/ready" >/dev/null 2>&1 \
    && echo "runtime-ready    yes" || echo "runtime-ready    no"
  curl -fsS --max-time 2 "http://127.0.0.1:$PLATFORM_API_PORT/_system/health" >/dev/null 2>&1 \
    && echo "platform-api     yes" || echo "platform-api     no"
}

logs() {
  local key="${1:-}"
  if [ -n "$key" ]; then
    [ -f "$LOG_DIR/$key.log" ] || die "unknown or unavailable log: $key"
    tail -n 80 "$LOG_DIR/$key.log"
    return
  fi
  for file in "$LOG_DIR"/*.log; do
    [ -e "$file" ] || continue
    printf '\n== %s ==\n' "$(basename "$file")"
    tail -n 20 "$file"
  done
}

restart_one() {
  local key="$1"
  load_runtime_env
  case "$key" in
    runtime-api|runtime-worker|platform-api|platform-worker|platform-web) ;;
    *) die "restart-one requires one of runtime-api, runtime-worker, platform-api, platform-worker, platform-web" ;;
  esac
  stop_process "$key"
  start_managed_key "$key"
  case "$key" in
    runtime-api) wait_http runtime-api "http://127.0.0.1:$RUNTIME_PORT/ready" ;;
    platform-api) wait_http platform-api "http://127.0.0.1:$PLATFORM_API_PORT/_system/health" ;;
    platform-web) wait_http platform-web "http://127.0.0.1:$PLATFORM_WEB_PORT" ;;
    runtime-worker|platform-worker) require_managed_process "$key" ;;
  esac
}

command="${1:-help}"
case "$command" in
  doctor) validate_stack ;;
  migrate) migrate ;;
  start) start ;;
  stop)
    stop_process platform-web
    stop_process platform-worker
    stop_process platform-api
    stop_process runtime-worker
    stop_process runtime-api
    ;;
  restart) stop_process platform-web; stop_process platform-worker; stop_process platform-api; stop_process runtime-worker; stop_process runtime-api; start ;;
  restart-one) restart_one "${2:-}" ;;
  status) status ;;
  logs) logs "${2:-}" ;;
  help|-h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
