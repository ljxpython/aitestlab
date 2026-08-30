from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.custom_routes.app import app  # noqa: E402


def test_list_tools_route() -> None:
    client = TestClient(app)
    response = client.get("/internal/capabilities/tools")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 1
    names = [item["name"] for item in payload["tools"]]
    assert "word_count" in names
    assert "to_upper" in names
    assert "mcp:local_math" in names
    assert "mcp:local_text" in names


def test_list_models_route() -> None:
    client = TestClient(app)
    response = client.get("/internal/capabilities/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 1
    assert isinstance(payload["models"], list)
    first = payload["models"][0]
    assert "model_id" in first
    assert "display_name" in first
    assert "is_default" in first
    assert "api_key" not in first
    assert "base_url" not in first
