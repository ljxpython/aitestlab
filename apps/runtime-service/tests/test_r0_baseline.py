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


def test_production_config_registers_runtime_auth_adapter() -> None:
    config = _load_config("langgraph.json")
    assert config["auth"]["path"] == "./src/runtime_service/auth/platform.py:auth"
    assert config["auth"]["openapi"] == {
        "securitySchemes": {
            "RuntimeBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        "security": [{"RuntimeBearer": []}],
    }


def test_graph_configs_use_the_runtime_lifespan_app() -> None:
    production = _load_config("langgraph.json")
    demo = _load_config("langgraph.demo.json")

    expected = "./src/runtime_service/webapp.py:app"
    assert production["http"]["app"] == expected
    assert demo["http"]["app"] == expected


def test_docker_graph_registry_matches_production_config() -> None:
    config = _load_config("langgraph.json")
    dockerfile = (PROJECT_ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    registry_lines = [line for line in dockerfile.splitlines() if line.startswith("ENV LANGSERVE_GRAPHS=")]

    assert len(registry_lines) == 1
    registry = json.loads(registry_lines[0].removeprefix("ENV LANGSERVE_GRAPHS='").removesuffix("'"))
    expected = {
        graph_id: {
            "path": f"/deps/runtime-service/{item['path'].removeprefix('./')}",
            "description": item["description"],
        }
        for graph_id, item in config["graphs"].items()
    }

    assert registry == expected


def test_docker_auth_and_http_registry_match_production_config() -> None:
    config = _load_config("langgraph.json")
    dockerfile = (PROJECT_ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")

    def env_json(name: str) -> dict[str, object]:
        prefix = f"ENV {name}='"
        line = next(item for item in dockerfile.splitlines() if item.startswith(prefix))
        return json.loads(line.removeprefix(prefix).removesuffix("'"))

    expected_auth = dict(config["auth"])
    expected_auth["path"] = f"/deps/runtime-service/{config['auth']['path'].removeprefix('./')}"
    expected_http = dict(config["http"])
    expected_http["app"] = f"/deps/runtime-service/{config['http']['app'].removeprefix('./')}"
    assert env_json("LANGGRAPH_AUTH") == expected_auth
    assert env_json("LANGGRAPH_HTTP") == expected_http


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
    result = asyncio.run(
        graph.ainvoke(
            {"message": "hello"},
            {"configurable": {"thread_id": "r0-workflow-baseline"}},
        )
    )

    assert result["response"] == "workflow response: hello"
