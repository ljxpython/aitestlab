from __future__ import annotations

import asyncio

from langchain.agents import create_agent as real_create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from runtime_service.services.reference_agent import agent


def test_reference_agent_declares_reliability_middleware_in_order(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        agent,
        "build_model",
        lambda _config: FakeListChatModel(responses=["ok"]),
    )

    def capture_create_agent(**kwargs):
        captured.update(kwargs)
        return real_create_agent(**kwargs)

    monkeypatch.setattr(agent, "create_agent", capture_create_agent)
    asyncio.run(agent.get_agent({"context": {}}))

    middleware = captured["middleware"]
    assert [type(item).__name__ for item in middleware] == [
        "RuntimeConfigMiddleware",
        "ModelCallLimitMiddleware",
        "ToolCallLimitMiddleware",
        "ModelCallTimeoutMiddleware",
    ]
