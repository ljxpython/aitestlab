#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAPH_HARBOR_DIR="${GRAPHHARBOR_SOURCE_DIR:-$APP_DIR/../../../graphharbor}"
WHEEL_DIR="${GRAPHHARBOR_WHEEL_DIR:-$APP_DIR/scripts/wheels}"
EXPECTED_VERSION="${GRAPHHARBOR_VERSION:-0.13.0.post20}"
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/graphharbor-build.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT

if [[ ! -f "$GRAPH_HARBOR_DIR/pyproject.toml" ]]; then
  echo "GraphHarbor source not found: $GRAPH_HARBOR_DIR" >&2
  exit 2
fi

cd "$GRAPH_HARBOR_DIR"
uv build --package graphharbor --wheel --out-dir "$BUILD_DIR"
uv build --package graphharbor-runtime --wheel --out-dir "$BUILD_DIR"

mkdir -p "$WHEEL_DIR"
for pattern in \
  "graphharbor-${EXPECTED_VERSION}-*.whl" \
  "graphharbor_runtime-${EXPECTED_VERSION}-*.whl"; do
  wheel="$(find "$BUILD_DIR" -maxdepth 1 -type f -name "$pattern" -print -quit)"
  if [[ -z "$wheel" ]]; then
    echo "Expected wheel not built: $pattern" >&2
    exit 2
  fi
  cp "$wheel" "$WHEEL_DIR/"
done

echo "Built GraphHarbor $EXPECTED_VERSION wheels in $WHEEL_DIR"
