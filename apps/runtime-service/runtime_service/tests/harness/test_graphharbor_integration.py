"""Integration contract for the GraphHarbor production Agent Server adapter."""

from __future__ import annotations

import json
import asyncio
import os
import time
from pathlib import Path

import httpx
import jwt
from langgraph_runtime_pg.graph_registry import GraphRegistry
from langhost.server import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "runtime_service" / "langgraph.json"
P0_GRAPHS = {
    "assistant",
    "test_case_agent_v2",
    "customer_support_handoffs_demo",
    "deepagent_demo",
    "personal_assistant_demo",
}


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_unchanged_langgraph_config_loads_all_graphs_and_extension_points() -> None:
    config = _config()
    registry = GraphRegistry.from_path(CONFIG_PATH)

    assert len(registry) == len(config["graphs"])
    assert P0_GRAPHS.issubset(registry.ids())
    for graph_id in registry.ids():
        graph = registry.get(graph_id)
        assert hasattr(graph, "ainvoke")
        assert hasattr(graph, "astream_events")
        assert set(graph.get_context_jsonschema()["properties"]) == {
            "user_id",
            "tenant_id",
            "role",
            "permissions",
            "project_id",
        }

    app = create_app(config, base_dir=PROJECT_ROOT)
    assert app.state.auth_handler is not None
    assert app.state.custom_app is not None
    assert getattr(app.state.auth_handler, "_authenticate_handler", None) is not None


def test_custom_capability_routes_are_mounted_on_graphharbor_app(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_MANAGEMENT_API_KEY", "management-key-that-is-32-bytes-long")
    app = create_app(_config(), base_dir=PROJECT_ROOT)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/internal/capabilities/tools",
                headers={"X-API-Key": "management-key-that-is-32-bytes-long"},
            )

    response = asyncio.run(request())

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["tools"])


def test_platform_auth_is_used_by_core_and_custom_routes(monkeypatch) -> None:
    secret = "integration-secret-that-is-at-least-32-bytes"
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", secret)
    claims = {
        "sub": "integration-user",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "role": "user",
        "permissions": ["runtime:read"],
        "iss": "platform-api",
        "aud": "runtime-service",
        "iat": int(time.time()),
        "nbf": int(time.time()),
        "exp": int(time.time()) + 300,
        "jti": "integration-jti",
        "type": "runtime_delegation",
    }
    token = jwt.encode(claims, secret, algorithm="HS256")
    app = create_app(_config(), base_dir=PROJECT_ROOT)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/internal/capabilities/models",
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["count"] >= 0
    assert os.environ["PLATFORM_RUNTIME_DELEGATION_SECRET"] == secret
