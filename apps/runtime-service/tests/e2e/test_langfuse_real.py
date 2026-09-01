from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from runtime_service.observability import langfuse
from runtime_service.services.workflow_demo.agent import get_agent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.e2e


def test_real_langfuse_workflow_trace_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("RUNTIME_R5") != "1":
        pytest.skip("set RUNTIME_R5=1 to run real Langfuse smoke")

    settings = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    required = (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
    )
    missing = [name for name in required if not settings.get(name)]
    if missing:
        pytest.skip(f"real Langfuse configuration missing: {', '.join(missing)}")
    if str(settings.get("LANGFUSE_ENABLED", "")).lower() != "true":
        pytest.skip("LANGFUSE_ENABLED must be true for the real smoke")

    for name in (*required, "LANGFUSE_ENABLED", "LANGFUSE_TRACING_ENVIRONMENT"):
        if settings.get(name) is not None:
            monkeypatch.setenv(name, str(settings[name]))

    try:
        graph = asyncio.run(
            get_agent(
                {
                    "metadata": {
                        "run_id": "r5-smoke-run",
                        "request_id": "r5-smoke-request",
                    },
                    "configurable": {"thread_id": "r5-smoke-thread"},
                }
            )
        )
        result = graph.invoke(
            {"message": "hello", "route": "approve"},
            {"configurable": {"thread_id": "r5-smoke-thread"}},
        )
        assert result["response"] == "workflow approved: hello"

        client = langfuse.initialize_langfuse()
        assert client is not None
        auth_check = getattr(client, "auth_check", None)
        if callable(auth_check):
            assert auth_check() is True
        client.flush()
    finally:
        langfuse.close_langfuse(timeout_seconds=10.0)
