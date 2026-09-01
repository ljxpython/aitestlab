#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AEGRA_SPIKE_ENV_FILE:-${HOME}/.my_best/.env}"
"$SCRIPT_DIR/scripts/check-env.sh"
export PYTHONPATH="$SCRIPT_DIR/../../src:${PYTHONPATH:-}"
export AEGRA_SPIKE_URL="${AEGRA_SPIKE_URL:-http://127.0.0.1:2026}"
targets=("$SCRIPT_DIR/tests")
if (($#)); then
  targets=("$@")
fi
uv run --project "$SCRIPT_DIR" --env-file "$ENV_FILE" pytest "${targets[@]}" -q
