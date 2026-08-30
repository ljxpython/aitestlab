from __future__ import annotations

import asyncio
import json
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.graphs.reference_agent import get_agent as get_reference_agent
from runtime_service.graphs.workflow_demo import get_agent as get_workflow_agent
from support import BindableFakeChatModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_config(name: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / name).read_text(encoding="utf-8"))


def test_new_package_is_loaded_from_src() -> None:
    import runtime_service

    assert Path(runtime_service.__file__).resolve().is_relative_to(PROJECT_ROOT / "src")


def test_production_config_registers_only_reference_agent() -> None:
    config = _load_config("langgraph.json")
    graphs = config["graphs"]

    assert list(graphs) == ["reference_agent"]
    assert graphs["reference_agent"]["path"].startswith("./src/runtime_service/graphs/")
    assert graphs["reference_agent"]["description"]


def test_demo_config_registers_capability_graphs() -> None:
    config = _load_config("langgraph.demo.json")
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


def test_service_entrypoints_return_pregel() -> None:
    config: RunnableConfig = {
        "configurable": {"_runtime_model": BindableFakeChatModel(responses=["reference agent response"])}
    }

    reference = asyncio.run(get_reference_agent(config))
    workflow = asyncio.run(get_workflow_agent(config))

    assert isinstance(reference, Pregel)
    assert isinstance(workflow, Pregel)


def test_reference_agent_uses_deterministic_fake_model() -> None:
    graph = asyncio.run(
        get_reference_agent(
            {"configurable": {"_runtime_model": BindableFakeChatModel(responses=["reference agent response"])} }
        )
    )
    result = asyncio.run(
        graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]})
    )

    assert result["messages"][-1].content == "reference agent response"


def test_workflow_demo_has_deterministic_state_transition() -> None:
    graph = asyncio.run(get_workflow_agent({}))
    result = asyncio.run(graph.ainvoke({"message": "hello"}))

    assert result["response"] == "workflow response: hello"
