#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/apps/lightrag-service"
STATE_DIR="/tmp/aitestlab-lightrag-service"
PID_DIR="$STATE_DIR/pids"
HTTP_HOST="${LIGHTRAG_HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${LIGHTRAG_HTTP_PORT:-9621}"
MCP_HOST="${LIGHTRAG_MCP_HOST:-127.0.0.1}"
MCP_PORT="${LIGHTRAG_MCP_PORT:-8621}"
WORKING_DIR="${LIGHTRAG_WORKING_DIR:-$SERVICE_DIR/data/rag_storage}"
INPUT_DIR="${LIGHTRAG_INPUT_DIR:-$SERVICE_DIR/data/inputs}"
HTTP_LOG="$STATE_DIR/http.log"
MCP_LOG="$STATE_DIR/mcp-sse.log"

mkdir -p "$STATE_DIR" "$PID_DIR"

ensure_file() {
  local target="$1"
  local source="$2"
  if [ -f "$target" ]; then
    return
  fi
  cp "$source" "$target"
  echo "[init] created $(basename "$target") from template"
}

ensure_service_dir() {
  if [ -d "$SERVICE_DIR" ]; then
    return
  fi

  echo "[error] missing optional service root: $SERVICE_DIR" >&2
  echo "        this helper only supports repo-local host-run mode." >&2
  exit 1
}


port_in_use() {
  local port="$1"
  lsof -ti "tcp:${port}" >/dev/null 2>&1
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local code=""

  for ((i = 1; i <= attempts; i++)); do
    code="$(python3 - "$url" <<'PY2'
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        print(response.getcode())
except urllib.error.HTTPError as exc:
    print(exc.code)
except Exception:
    print("000")
PY2
)"
    if [ -n "$code" ] && [ "$code" != "000" ]; then
      echo "[ready] $name -> $url ($code)"
      return 0
    fi
    sleep 1
  done

  echo "[warn] $name did not answer at $url" >&2
  return 1
}

spawn_detached() {
  local workdir="$1"
  local command="$2"
  local logfile="$3"

  python3 - "$workdir" "$command" "$logfile" <<'PY2'
import subprocess
import sys

workdir, command, logfile = sys.argv[1:4]

with open(logfile, 'ab', buffering=0) as stream:
    process = subprocess.Popen(
        ['/bin/bash', '-c', f'exec {command}'],
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    print(process.pid)
PY2
}

resolve_http_command() {
  if [ -n "${LIGHTRAG_HTTP_CMD:-}" ]; then
    printf '%s\n' "$LIGHTRAG_HTTP_CMD"
    return
  fi

  printf '%s\n' "env HOST=$HTTP_HOST PORT=$HTTP_PORT WORKING_DIR=$WORKING_DIR INPUT_DIR=$INPUT_DIR uv run lightrag-server"
}

resolve_mcp_command() {
  if [ -n "${LIGHTRAG_MCP_CMD:-}" ]; then
    printf '%s\n' "$LIGHTRAG_MCP_CMD"
    return
  fi

  printf '%s\n' "env MCP_TRANSPORT=sse MCP_HOST=$MCP_HOST MCP_PORT=$MCP_PORT MCP_PATH=/sse MCP_MESSAGE_PATH=/messages/ WORKING_DIR=$WORKING_DIR INPUT_DIR=$INPUT_DIR uv run --with 'fastmcp>=3.2.0' --with 'starlette==0.49.1' python -m lightrag.mcp"
}

start_service() {
  local name="$1"
  local pid_key="$2"
  local command="$3"
  local port="$4"
  local logfile="$5"
  local pid

  if port_in_use "$port"; then
    echo "[skip] $name already listening on :$port"
    return
  fi

  echo "[start] $name -> :$port"
  pid="$(spawn_detached "$SERVICE_DIR" "$command" "$logfile")"
  printf '%s\n' "$pid" > "$PID_DIR/${pid_key}.pid"
  echo "        pid=$pid log=$logfile"
}

ensure_service_dir
ensure_file "$SERVICE_DIR/.env" "$SERVICE_DIR/.env.example"
mkdir -p "$WORKING_DIR" "$INPUT_DIR"

HTTP_COMMAND="$(resolve_http_command)"
MCP_COMMAND="$(resolve_mcp_command)"

start_service "lightrag http" "http" "$HTTP_COMMAND" "$HTTP_PORT" "$HTTP_LOG"
start_service "lightrag mcp sse" "mcp-sse" "$MCP_COMMAND" "$MCP_PORT" "$MCP_LOG"

wait_for_http "lightrag http" "http://${HTTP_HOST}:${HTTP_PORT}/health" 20 || true
wait_for_http "lightrag mcp sse" "http://${MCP_HOST}:${MCP_PORT}/sse" 20 || true

echo
echo "state_dir=$STATE_DIR"
echo "working_dir=$WORKING_DIR"
echo "input_dir=$INPUT_DIR"
echo "http_log=$HTTP_LOG"
echo "mcp_log=$MCP_LOG"
