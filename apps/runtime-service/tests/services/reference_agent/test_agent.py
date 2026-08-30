from __future__ import annotations

import asyncio

import pytest
from runtime_service.runtime import RuntimeContext, RuntimeResolutionError
from runtime_service.services.reference_agent import agent
from runtime_service.services.reference_agent.tools import read_reference
from support import BindableFakeChatModel


def _config(model: BindableFakeChatModel) -> dict[str, object]:
    return {"configurable": {"_runtime_model": model}}


def test_get_agent_accepts_explicit_fake_model_and_runtime_context() -> None:
    agent._STATIC_AGENT = None
    graph = asyncio.run(
        agent.get_agent(_config(BindableFakeChatModel(responses=["runtime-ok"])))
    )

    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(),
        )
    )

    assert result["messages"][-1].content == "runtime-ok"


def test_context_override_is_resolved_before_model_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_model(config: object) -> BindableFakeChatModel:
        captured["config"] = config
        return BindableFakeChatModel(responses=["override-ok"])

    monkeypatch.setattr(agent, "build_model", fake_build_model)
    graph = asyncio.run(
        agent.get_agent({"context": {"temperature": 0}})
    )
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(temperature=0),
        )
    )

    assert captured["config"].temperature == 0.0  # type: ignore[union-attr]
    assert result["messages"][-1].content == "override-ok"


def test_context_policy_violation_fails_before_fake_model_use() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(
            agent.get_agent(
                _config(BindableFakeChatModel(responses=["must-not-run"]))
                | {"context": {"model_id": "openai:gpt-5.5"}}
            )
        )

    assert error.value.code == "runtime.model.not_allowed"


def test_default_path_does_not_fallback_to_fake_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent._STATIC_AGENT = None

    def missing_provider(_: object) -> FakeListChatModel:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")

    monkeypatch.setattr(agent, "build_model", missing_provider)
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(agent.get_agent({}))

    assert error.value.code == "runtime.model.initialization_failed"


def test_reference_tool_is_explicit_and_read_only() -> None:
    assert read_reference.invoke({"topic": "runtime"}) == "reference note: runtime"
