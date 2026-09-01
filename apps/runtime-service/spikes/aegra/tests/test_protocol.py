from __future__ import annotations

import os

import httpx


def test_server_health_and_reference_graph(base_url: str) -> None:
    headers = {"Authorization": f"Bearer {os.getenv('AEGRA_SPIKE_AUTH_TOKEN', 'aegra-spike-token')}"}
    health = httpx.get(f"{base_url}/health", headers=headers, timeout=10)
    assert health.status_code == 200, health.text

    info = httpx.get(f"{base_url}/info", headers=headers, timeout=10)
    assert info.status_code == 200, info.text
    assert info.json()["version"] == "0.10.4"

    assistants = httpx.get(f"{base_url}/assistants", headers=headers, timeout=10)
    assert assistants.status_code == 200, assistants.text
    assert any(item["graph_id"] == "reference_agent" for item in assistants.json()["assistants"])
