#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="/tmp/aitestlab-platform-web-demo"
PID_DIR="$LOG_DIR/pids"

mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"
mkdir -p "$ROOT_DIR/apps/platform-api/.tmp"
mkdir -p "$ROOT_DIR/apps/platform-api/.data"

ensure_file() {
  local target="$1"
  local source="$2"
  if [ -f "$target" ]; then
    return
  fi
  cp "$source" "$target"
  echo "[init] created $(basename "$target") from template"
}

ensure_web_env() {
  local target="$ROOT_DIR/apps/platform-web/.env.local"
  if [ -f "$target" ]; then
    return
  fi
  cat > "$target" <<'EOF'
VITE_APP_NAME=Agent Platform Console
VITE_PLATFORM_API_URL=/
VITE_PLATFORM_API_RUNTIME_ENABLED=true
VITE_REQUEST_TIMEOUT_MS=30000
VITE_DEV_PORT=3000
VITE_DEV_PROXY_TARGET=http://localhost:2142
VITE_LANGGRAPH_DEBUG_URL=
EOF
  echo "[init] created apps/platform-web/.env.local"
}

port_in_use() {
  local port="$1"
  lsof -ti "tcp:${port}" >/dev/null 2>&1
}

wait_for_http_200() {
  local url="$1"
  local attempts="${2:-30}"
  local code=""

  for ((i = 1; i <= attempts; i++)); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [ "$code" = "200" ]; then
      return 0
    fi
    sleep 1
  done

  return 1
}

spawn_detached() {
  local workdir="$1"
  local command="$2"
  local logfile="$3"

  python3 - "$workdir" "$command" "$logfile" <<'PY'
import subprocess
import sys

workdir, command, logfile = sys.argv[1:4]

with open(logfile, "ab", buffering=0) as stream:
    process = subprocess.Popen(
        ["/bin/bash", "-c", f"exec {command}"],
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

ensure_demo_user() {
  local base_url="http://127.0.0.1:2142"

  if ! wait_for_http_200 "$base_url/_system/health" 30; then
    echo "[warn] platform-api not ready, skip demo user bootstrap"
    return
  fi

  python3 - "$base_url" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")


def request(path: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req) as response:
        body = response.read().decode("utf-8")
        return response.getcode(), json.loads(body) if body else {}


_, login_data = request(
    "/api/identity/session",
    {"username": "admin", "password": "admin123456"},
)
access_token = login_data["tokens"]["access_token"]

try:
    request(
        "/api/users",
        {"username": "test", "password": "test123456", "is_super_admin": False},
        token=access_token,
    )
    print("[init] created demo user test/test123456")
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="ignore")
    if exc.code == 409 and "username_conflict" in body:
        print("[skip] demo user test already exists")
    else:
        print(f"[warn] failed to ensure demo user: http {exc.code} {body[:200]}")
PY
}

start_http_service() {
  local name="$1"
  local service_key="$2"
  local workdir="$3"
  local command="$4"
  local port="$5"
  local logfile="$6"
  local pid

  if port_in_use "$port"; then
    echo "[skip] $name already listening on :$port"
    return
  fi

  echo "[start] $name -> :$port"
  pid="$(spawn_detached "$workdir" "$command" "$logfile")"
  printf '%s\n' "$pid" > "$PID_DIR/${service_key}.pid"
  echo "        pid=$pid log=$(basename "$logfile")"
}

start_worker() {
  local name="$1"
  local service_key="$2"
  local workdir="$3"
  local command="$4"
  local pattern="$5"
  local logfile="$6"
  local pid

  if pgrep -f "$pattern" >/dev/null 2>&1; then
    echo "[skip] $name already running"
    return
  fi

  echo "[start] $name"
  pid="$(spawn_detached "$workdir" "$command" "$logfile")"
  printf '%s\n' "$pid" > "$PID_DIR/${service_key}.pid"
  echo "        pid=$pid log=$(basename "$logfile")"
}

ensure_file "$ROOT_DIR/apps/platform-api/.env" "$ROOT_DIR/apps/platform-api/.env.example"
ensure_web_env

start_http_service \
  "runtime-service" \
  "runtime-service" \
  "$ROOT_DIR/apps/runtime-service" \
  "uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser" \
  "8123" \
  "$LOG_DIR/runtime-service.log"

start_http_service \
  "interaction-data-service" \
  "interaction-data-service" \
  "$ROOT_DIR/apps/interaction-data-service" \
  "uv run uvicorn main:app --host 127.0.0.1 --port 8081 --reload" \
  "8081" \
  "$LOG_DIR/interaction-data-service.log"

echo
echo "[start] lightrag-service bundle"
bash "$ROOT_DIR/scripts/lightrag-service-up.sh"

start_http_service \
  "platform-api" \
  "platform-api" \
  "$ROOT_DIR/apps/platform-api" \
  "uv run uvicorn main:app --host 127.0.0.1 --port 2142 --reload" \
  "2142" \
  "$LOG_DIR/platform-api.log"

start_worker \
  "platform-api worker" \
  "platform-api-worker" \
  "$ROOT_DIR/apps/platform-api" \
  "uv run python worker.py" \
  "uv run python worker.py" \
  "$LOG_DIR/platform-api-worker.log"

start_http_service \
  "platform-web" \
  "platform-web" \
  "$ROOT_DIR/apps/platform-web" \
  "pnpm dev -- --host 127.0.0.1 --port 3000" \
  "3000" \
  "$LOG_DIR/platform-web.log"

ensure_demo_user

echo
echo "[done] platform-web demo stack is starting"
echo "logs:"
echo "  $LOG_DIR/runtime-service.log"
echo "  $LOG_DIR/interaction-data-service.log"
echo "  /tmp/aitestlab-lightrag-service/http.log"
echo "  /tmp/aitestlab-lightrag-service/mcp-sse.log"
echo "  $LOG_DIR/platform-api.log"
echo "  $LOG_DIR/platform-api-worker.log"
echo "  $LOG_DIR/platform-web.log"
echo
echo "next:"
echo "  1. bash \"$ROOT_DIR/scripts/platform-web-demo-health.sh\""
echo "  2. open http://127.0.0.1:3000"
