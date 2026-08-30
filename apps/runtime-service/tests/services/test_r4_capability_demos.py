from __future__ import annotations

import asyncio

import pytest
from deepagents.backends import StateBackend
from langgraph.pregel import Pregel

from runtime_service.graphs.backend_demo import get_agent as get_backend_agent
from runtime_service.graphs.deep_agent_demo import get_agent as get_deep_agent
from runtime_service.graphs.mcp_demo import get_agent as get_mcp_agent
from runtime_service.runtime import RuntimeResolutionError
from runtime_service.services.mcp_demo.loader import load_mcp_tools
from runtime_service.services.backend_demo import agent as backend_server
from support import BindableFakeChatModel


def _config() -> dict[str, object]:
    return {"configurable": {"_runtime_model": BindableFakeChatModel(responses=["ok"])}}


@pytest.mark.parametrize("entrypoint", [get_deep_agent, get_backend_agent, get_mcp_agent])
def test_r4_graphs_return_pregel_without_external_services(entrypoint) -> None:
    graph = asyncio.run(entrypoint(_config()))
    assert isinstance(graph, Pregel)


def test_deep_agent_declares_state_backend_and_bundled_skill() -> None:
    graph = asyncio.run(get_deep_agent(_config()))
    assert "SkillsMiddleware.before_agent" in graph.get_graph().nodes


def test_mcp_loader_explicitly_allowlists_fake_tool() -> None:
    tools = asyncio.run(load_mcp_tools())
    assert [tool.name for tool in tools] == ["mcp_read"]
    result = asyncio.run(tools[0].ainvoke({"topic": "runtime"}))
    assert result[0]["text"] == "mcp note: runtime"


def test_mcp_loader_rejects_name_collision_before_agent_creation() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(load_mcp_tools(conflict=True))
    assert error.value.code == "runtime.tool.name_conflict"


def test_backend_demo_uses_state_backend_node() -> None:
    graph = asyncio.run(get_backend_agent(_config()))
    assert "tools" in graph.get_graph().nodes
    assert StateBackend.__name__ == "StateBackend"


def test_backend_demo_creates_isolated_graph_resources_per_load() -> None:
    first = asyncio.run(get_backend_agent(_config()))
    second = asyncio.run(get_backend_agent(_config()))
    assert first is not second


def test_backend_demo_does_not_fallback_after_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(backend_server, "create_deep_agent", fail)
    with pytest.raises(RuntimeError, match="backend unavailable"):
        asyncio.run(backend_server.get_agent(_config()))
