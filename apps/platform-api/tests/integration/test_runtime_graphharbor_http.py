from __future__ import annotations

import os
from dataclasses import dataclass
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

_REQUIRED_ENV = (
    "PLATFORM_API_BASE_URL",
    "PLATFORM_API_ACCESS_TOKEN",
    "PLATFORM_API_PROJECT_ID",
    "PLATFORM_API_EXPECTED_UPSTREAM_URL",
)


@dataclass(frozen=True)
class IntegrationConfig:
    base_url: str
    access_token: str
    project_id: str
    expected_upstream_url: str


def _load_config() -> IntegrationConfig:
    if os.getenv("PLATFORM_RUNTIME_INTEGRATION") != "1":
        raise unittest.SkipTest(
            "set PLATFORM_RUNTIME_INTEGRATION=1 to run the real HTTP integration"
        )

    missing = [name for name in _REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise unittest.SkipTest("missing integration environment: " + ", ".join(missing))

    base_url = os.environ["PLATFORM_API_BASE_URL"].strip().rstrip("/")
    expected_upstream_url = os.environ["PLATFORM_API_EXPECTED_UPSTREAM_URL"].strip().rstrip("/")
    if not expected_upstream_url.startswith(("http://", "https://")):
        raise ValueError(
            "PLATFORM_API_EXPECTED_UPSTREAM_URL must be an absolute HTTP URL"
        )

    return IntegrationConfig(
        base_url=base_url,
        access_token=os.environ["PLATFORM_API_ACCESS_TOKEN"].strip(),
        project_id=os.environ["PLATFORM_API_PROJECT_ID"].strip(),
        expected_upstream_url=expected_upstream_url,
    )


def _headers(config: IntegrationConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.access_token}",
        "x-project-id": config.project_id,
        "Content-Type": "application/json",
    }


def _json(response: httpx.Response, *, expected_status: int) -> object:
    if response.status_code != expected_status:
        raise AssertionError(response.text)
    return response.json()


class RuntimeGraphHarborHttpIntegrationTest(unittest.TestCase):
    def test_missing_gate_is_explicit_skip(self) -> None:
        previous = os.environ.pop("PLATFORM_RUNTIME_INTEGRATION", None)
        try:
            with self.assertRaisesRegex(unittest.SkipTest, "PLATFORM_RUNTIME_INTEGRATION"):
                _load_config()
        finally:
            if previous is not None:
                os.environ["PLATFORM_RUNTIME_INTEGRATION"] = previous

    def test_invalid_upstream_configuration_fails_harness(self) -> None:
        values = {
            "PLATFORM_RUNTIME_INTEGRATION": "1",
            "PLATFORM_API_BASE_URL": "http://127.0.0.1:2144",
            "PLATFORM_API_ACCESS_TOKEN": "test-token",
            "PLATFORM_API_PROJECT_ID": "test-project",
            "PLATFORM_API_EXPECTED_UPSTREAM_URL": "not-an-url",
        }
        with patch.dict(os.environ, values):
            with self.assertRaisesRegex(ValueError, "absolute HTTP URL"):
                _load_config()

    def test_platform_rejects_unauthenticated_runtime_request(self) -> None:
        config = _load_config()
        with httpx.Client(base_url=config.base_url, timeout=30.0) as client:
            response = client.get(
                "/api/langgraph/info",
                headers={"x-project-id": config.project_id},
            )

        self.assertIn(response.status_code, {401, 403}, response.text)

    def test_platform_gateway_reaches_graphharbor_for_info_graphs_and_thread(self) -> None:
        config = _load_config()
        headers = _headers(config)
        thread_marker = f"platform-graphharbor-{uuid4().hex}"

        with httpx.Client(base_url=config.base_url, timeout=30.0) as client:
            info = _json(
                client.get("/api/langgraph/info", headers=headers),
                expected_status=200,
            )
            graphs = _json(
                client.post(
                    "/api/langgraph/graphs/search",
                    headers=headers,
                    json={"limit": 20, "offset": 0},
                ),
                expected_status=200,
            )
            thread = _json(
                client.post(
                    "/api/langgraph/threads",
                    headers=headers,
                    json={"metadata": {"harness": thread_marker}},
                ),
                expected_status=200,
            )

        self.assertIsInstance(info, dict)
        self.assertTrue({"flags", "host", "version"}.issubset(info))
        self.assertIsInstance(info["flags"], dict)
        self.assertIsInstance(info["host"], dict)
        self.assertEqual(info["host"].get("kind"), "self-hosted")

        self.assertIsInstance(graphs, dict)
        self.assertIsInstance(graphs.get("items"), list)
        self.assertIsInstance(graphs.get("total"), int)
        self.assertEqual(graphs["limit"], 20)
        self.assertEqual(graphs["offset"], 0)

        self.assertIsInstance(thread, dict)
        metadata = thread.get("metadata")
        self.assertIsInstance(metadata, dict)
        self.assertEqual(metadata.get("harness"), thread_marker)
        self.assertEqual(metadata.get("project_id"), config.project_id)

    def test_integration_config_records_expected_upstream(self) -> None:
        config = _load_config()
        self.assertTrue(config.expected_upstream_url.startswith(("http://", "https://")))
