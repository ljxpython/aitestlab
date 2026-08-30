from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from runtime_service.runtime import RuntimeContext
from runtime_service.services.reference_agent.agent import get_agent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.e2e


def test_reference_agent_real_deepseek_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("RUNTIME_E2E") != "1":
        pytest.skip("set RUNTIME_E2E=1 to run real-model E2E")

    settings = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    required = (
        "DEEPSEEK_PROXY_API_KEY",
        "DEEPSEEK_PROXY_DEFAULT_MODEL",
        "DEEPSEEK_PROXY_URL",
    )
    missing = [name for name in required if not settings.get(name)]
    assert not missing, f"real-model E2E configuration missing: {', '.join(missing)}"

    for name in required:
        monkeypatch.setenv(name, str(settings[name]))

    graph = asyncio.run(get_agent({}))
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "Reply with exactly: e2e-ok"}]},
            context=RuntimeContext(),
        )
    )
    content = str(result["messages"][-1].content).lower()
    assert "e2e-ok" in content
