from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from deepagents.backends import StateBackend
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.pregel import Pregel
from support import BindableFakeChatModel, BindableFakeMessagesChatModel

from runtime_service.graphs.backend_demo import get_agent as get_backend_agent
from runtime_service.graphs.deep_agent_demo import get_agent as get_deep_agent
from runtime_service.graphs.mcp_demo import get_agent as get_mcp_agent
from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeContext,
    RuntimeResolutionError,
)
from runtime_service.services.backend_demo import agent as backend_server
from runtime_service.services.deep_agent_demo import agent as deep_agent_server
from runtime_service.services.mcp_demo import loader as mcp_loader
from runtime_service.services.mcp_demo.loader import load_mcp_tools

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _config(model: object | None = None) -> dict[str, object]:
    return {
        "configurable": {
            "_runtime_test_model": model or BindableFakeChatModel(responses=["ok"]),
            "_runtime_test_local_auth": True,
        }
    }


def _tool_names(graph: Pregel) -> set[str]:
    return set(graph.nodes["tools"].bound._tools_by_name)


@pytest.mark.parametrize("entrypoint", [get_deep_agent, get_backend_agent, get_mcp_agent])
def test_r4_graphs_return_pregel_without_external_services(entrypoint) -> None:
    graph = asyncio.run(entrypoint(_config()))
    assert isinstance(graph, Pregel)


def test_demo_config_registers_all_r4_capability_graphs() -> None:
    config = json.loads((PROJECT_ROOT / "langgraph.demo.json").read_text(encoding="utf-8"))
    graphs = config["graphs"]

    assert set(graphs) == {
        "reference_agent",
        "workflow_demo",
        "deep_agent_demo",
        "mcp_demo",
        "backend_demo",
    }
    assert all(item["description"] for item in graphs.values())
    assert all("runtime_service/agents" not in item["path"] for item in graphs.values())


def test_deep_agent_declares_state_backend_and_bundled_skill() -> None:
    graph = asyncio.run(get_deep_agent(_config()))
    assert "SkillsMiddleware.before_agent" in graph.get_graph().nodes


def test_deep_agent_subagent_is_explicitly_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(deep_agent_server, "create_deep_agent", capture)
    asyncio.run(deep_agent_server.get_agent(_config()))

    subagents = captured["subagents"]
    assert isinstance(subagents, list) and len(subagents) == 1
    subagent = subagents[0]
    assert subagent["name"] == "summarizer"
    assert subagent["tools"] == []
    assert subagent["permissions"] == deep_agent_server._SKILL_READ_ONLY
    assert subagent["middleware"]
    assert subagent["middleware"][0].backend is captured["backend"]
    assert captured["skills"] == [str(deep_agent_server._SKILL_DIR)]


def test_mcp_loader_explicitly_allowlists_fake_tool() -> None:
    tools = asyncio.run(load_mcp_tools())
    assert [tool.name for tool in tools] == ["mcp_read"]
    result = asyncio.run(tools[0].ainvoke({"topic": "runtime"}))
    assert result[0]["text"] == "mcp note: runtime"


def test_mcp_loader_rejects_name_collision_before_agent_creation() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(load_mcp_tools(conflict=True))
    assert error.value.code == "runtime.tool.name_conflict"


def test_mcp_loader_has_explicit_required_and_optional_failure_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(*args: object, **kwargs: object) -> list[object]:
        raise OSError("MCP down")

    monkeypatch.setattr(mcp_loader.MultiServerMCPClient, "get_tools", unavailable)
    with pytest.raises(RuntimeResolutionError, match="runtime.mcp.required_unavailable"):
        asyncio.run(load_mcp_tools(required=True))
    assert asyncio.run(load_mcp_tools(required=False)) == []


def test_mcp_tool_is_registered_in_real_agent_graph() -> None:
    graph = asyncio.run(get_mcp_agent(_config()))
    assert _tool_names(graph) == {"mcp_read"}


def test_mcp_graph_executes_service_loaded_tool() -> None:
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "mcp_read", "args": {"topic": "runtime"}, "id": "mcp-call"}]),
            AIMessage(content="done"),
        ]
    )
    config = _config(model)
    result = asyncio.run(_invoke(get_mcp_agent, config, "read MCP"))
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert any("mcp note: runtime" in str(message.content) for message in tool_messages)


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


@pytest.mark.parametrize("entrypoint", [get_deep_agent, get_backend_agent, get_mcp_agent])
def test_r4_production_entrypoints_fail_closed_without_verified_principal(entrypoint) -> None:
    with pytest.raises(RuntimeAuthError, match="runtime.auth.missing_principal"):
        asyncio.run(entrypoint({}))


@pytest.mark.parametrize("entrypoint", [get_deep_agent, get_backend_agent, get_mcp_agent])
@pytest.mark.parametrize("field", ["backend", "mcp_url", "skill_path", "subagents", "tool_impl", "token"])
def test_r4_entrypoints_reject_client_resource_and_credential_injection(entrypoint, field: str) -> None:
    with pytest.raises(RuntimeResolutionError, match="runtime.configurable.forbidden"):
        asyncio.run(
            entrypoint(
                {
                    "configurable": {
                        "_runtime_test_local_auth": True,
                        field: object(),
                    }
                }
            )
        )


def test_deep_agent_exposes_only_explicit_filesystem_and_task_tools() -> None:
    graph = asyncio.run(get_deep_agent(_config()))
    assert _tool_names(graph) == {"ls", "read_file", "glob", "grep", "task"}
    assert "execute" not in _tool_names(graph)
    assert "write_file" not in _tool_names(graph)


def test_backend_demo_exposes_workspace_tools_without_execute_or_task() -> None:
    graph = asyncio.run(get_backend_agent(_config()))
    assert _tool_names(graph) == {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "glob",
        "grep",
    }
    assert "execute" not in _tool_names(graph)
    assert "task" not in _tool_names(graph)


@pytest.mark.parametrize("entrypoint", [get_deep_agent, get_backend_agent, get_mcp_agent])
@pytest.mark.parametrize("tool_name", ["execute"])
def test_r4_rejects_forged_unregistered_tool_calls(entrypoint, tool_name: str) -> None:
    model = BindableFakeMessagesChatModel(
        responses=[AIMessage(content="", tool_calls=[{"name": tool_name, "args": {}, "id": "forged-call"}])]
    )
    config = _config(model)
    graph = asyncio.run(entrypoint(config))
    with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
        asyncio.run(graph.ainvoke({"messages": [("human", "trigger")]}, config))


def test_backend_demo_rejects_forged_task_tool_call() -> None:
    model = BindableFakeMessagesChatModel(
        responses=[AIMessage(content="", tool_calls=[{"name": "task", "args": {}, "id": "forged-task"}])]
    )
    config = _config(model)
    graph = asyncio.run(get_backend_agent(config))
    with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
        asyncio.run(graph.ainvoke({"messages": [("human", "trigger")]}, config))


def test_backend_demo_accepts_explicit_test_checkpointer() -> None:
    config = _config()
    config["configurable"] = {
        **config["configurable"],
        "_runtime_test_checkpointer": InMemorySaver(),
    }
    graph = asyncio.run(get_backend_agent(config))
    assert graph is not None


def test_backend_demo_rejects_invalid_test_checkpointer() -> None:
    config = _config()
    config["configurable"] = {
        **config["configurable"],
        "_runtime_test_checkpointer": object(),
    }
    with pytest.raises(RuntimeResolutionError, match="runtime.checkpointer.invalid"):
        asyncio.run(get_backend_agent(config))


def _tool_model(name: str, args: dict[str, object]) -> BindableFakeMessagesChatModel:
    return BindableFakeMessagesChatModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"{name}-call"}]),
            AIMessage(content="done"),
        ]
    )


def _backend_config(model: object, checkpointer: InMemorySaver, thread_id: str) -> dict[str, object]:
    config = _config(model)
    config["configurable"] = {
        **config["configurable"],
        "_runtime_test_checkpointer": checkpointer,
        "thread_id": thread_id,
    }
    return config


async def _invoke(entrypoint, config: dict[str, object], text: str) -> dict[str, object]:
    graph = await entrypoint(config)
    return await graph.ainvoke({"messages": [("human", text)]}, config)


def test_backend_workspace_survives_graph_rebuild_for_same_thread() -> None:
    checkpointer = InMemorySaver()
    write_config = _backend_config(_tool_model("write_file", {"file_path": "/notes.txt", "content": "thread-a"}), checkpointer, "thread-a")
    asyncio.run(_invoke(get_backend_agent, write_config, "write"))

    read_config = _backend_config(_tool_model("read_file", {"file_path": "/notes.txt"}), checkpointer, "thread-a")
    result = asyncio.run(_invoke(get_backend_agent, read_config, "read"))
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert any("thread-a" in str(message.content) for message in tool_messages)


def test_backend_workspace_isolated_between_threads() -> None:
    checkpointer = InMemorySaver()
    write_config = _backend_config(_tool_model("write_file", {"file_path": "/notes.txt", "content": "thread-a"}), checkpointer, "thread-a")
    asyncio.run(_invoke(get_backend_agent, write_config, "write"))

    read_config = _backend_config(_tool_model("read_file", {"file_path": "/notes.txt"}), checkpointer, "thread-b")
    result = asyncio.run(_invoke(get_backend_agent, read_config, "read"))
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert any("not found" in str(message.content).lower() for message in tool_messages)


def test_deep_agent_rejects_skill_write_before_backend_execution() -> None:
    model = _tool_model("write_file", {"file_path": "/skills/runtime-notes/SKILL.md", "content": "tamper"})
    config = _config(model)
    config["configurable"] = {
        **config["configurable"],
        "_runtime_test_checkpointer": InMemorySaver(),
        "thread_id": "skills-write",
    }
    with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
        asyncio.run(_invoke(get_deep_agent, config, "write skill"))


def test_deep_agent_performs_explicit_subagent_delegation() -> None:
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "description": "Summarize the task in one sentence.",
                            "subagent_type": "summarizer",
                        },
                        "id": "task-call",
                    }
                ],
            ),
            AIMessage(content="subagent-summary"),
            AIMessage(content="parent-summary"),
        ]
    )
    result = asyncio.run(_invoke(get_deep_agent, _config(model), "delegate"))
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert any(message.tool_call_id == "task-call" and "subagent-summary" in str(message.content) for message in tool_messages)
    assert _tool_names(asyncio.run(get_deep_agent(_config(model)))) == {
        "ls",
        "read_file",
        "glob",
        "grep",
        "task",
    }


def test_deep_agent_streams_subagent_namespace_and_projection() -> None:
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "description": "Summarize the task.",
                            "subagent_type": "summarizer",
                        },
                        "id": "stream-task-call",
                    }
                ],
            ),
            AIMessage(content="streamed summary"),
            AIMessage(content="parent conclusion"),
        ]
    )
    config = _config(model)

    async def collect() -> list[dict[str, object]]:
        graph = await get_deep_agent(config)
        events = []
        async for event in graph.astream(
            {"messages": [{"role": "user", "content": "delegate"}]},
            context=RuntimeContext(),
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())
    subagent_models = [
        event
        for event in events
        if event.get("ns")
        and isinstance(event.get("data"), dict)
        and isinstance(event["data"].get("model"), dict)
        and event["data"]["model"]["messages"][0].name == "summarizer"
    ]
    assert subagent_models
