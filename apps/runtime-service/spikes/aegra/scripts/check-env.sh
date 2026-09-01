#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AEGRA_SPIKE_ENV_FILE:-${HOME}/.my_best/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  exit 2
fi

has_key() {
  awk -F= -v key="$1" '$1 == key { found=1 } END { exit(found ? 0 : 1) }' "$ENV_FILE"
}

missing=()
for key in DEEPSEEK_PROXY_URL DEEPSEEK_PROXY_API_KEY DEEPSEEK_PROXY_DEFAULT_MODEL \
           DOUBAO_API_BASE DOUBAO_API_KEY DOUBAO_MODEL; do
  if ! has_key "$key"; then
    missing+=("$key")
  fi
done

langfuse_enabled="$(awk -F= '$1 == "LANGFUSE_ENABLED" { print tolower($2); exit }' "$ENV_FILE")"
if [[ "$langfuse_enabled" == "true" ]]; then
  for key in LANGFUSE_BASE_URL LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY; do
    if ! has_key "$key"; then
      missing+=("$key")
    fi
  done
fi

if ((${#missing[@]})); then
  printf 'Missing required private settings: %s\n' "${missing[*]}" >&2
  exit 2
fi

printf 'Environment check passed (values not printed): %s\n' "$ENV_FILE"
