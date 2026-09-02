#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL_DIR="${GRAPHHARBOR_WHEEL_DIR:-$APP_DIR/scripts/wheels}"
PYTHON="${PYTHON:-$APP_DIR/.venv/bin/python}"
EXPECTED_VERSION="${GRAPHHARBOR_VERSION:-0.13.0.post20}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Runtime Python not found: $PYTHON" >&2
  exit 2
fi
GRAPH_HARBOR_WHEEL="$WHEEL_DIR/graphharbor-${EXPECTED_VERSION}-py3-none-any.whl"
GRAPH_HARBOR_RUNTIME_WHEEL="$WHEEL_DIR/graphharbor_runtime-${EXPECTED_VERSION}-py3-none-any.whl"
for wheel in "$GRAPH_HARBOR_WHEEL" "$GRAPH_HARBOR_RUNTIME_WHEEL"; do
  if [[ ! -f "$wheel" ]]; then
    echo "GraphHarbor wheel not found: $wheel" >&2
    echo "Run scripts/build-graphharbor-local.sh once, then retry." >&2
    exit 2
  fi
done

uv pip install --python "$PYTHON" --no-deps --force-reinstall \
  "$GRAPH_HARBOR_WHEEL" "$GRAPH_HARBOR_RUNTIME_WHEEL"

"$PYTHON" -c \
  "import importlib.metadata as m; import langhost; expected = '$EXPECTED_VERSION'; assert m.version('graphharbor') == expected; assert m.version('graphharbor-runtime') == expected; print('GraphHarbor local wheels verified')"

echo "Installed GraphHarbor $EXPECTED_VERSION from $WHEEL_DIR"
