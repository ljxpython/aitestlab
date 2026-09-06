#!/usr/bin/env bash
set -euo pipefail

WEB_URL="${PLATFORM_WEB_URL:-http://127.0.0.1:3000}"
AGENT_ID="${CHAT_HARNESS_AGENT_ID:-workflow_demo}"
AGENT_NAME="${CHAT_HARNESS_AGENT_NAME:-Workflow Demo HITL}"
TARGET_URL="${WEB_URL%/}/workspace/chat?targetType=assistant&assistantId=${AGENT_ID}&assistantName=${AGENT_NAME}&startNew=1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v playwright-cli >/dev/null 2>&1 || {
  printf '%s\n' '[chat-harness] playwright-cli 不可用，测试未执行' >&2
  exit 2
}

cleanup() {
  playwright-cli close >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

playwright-cli open
if [[ -n "${CHAT_HARNESS_STATE:-}" ]]; then
  playwright-cli state-load "$CHAT_HARNESS_STATE"
fi
playwright-cli goto "$TARGET_URL"
playwright-cli run-code --filename="$SCRIPT_DIR/chat-harness.js"
