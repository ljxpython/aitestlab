from __future__ import annotations

import asyncio
import json
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
import yaml
from support import BindableFakeChatModel

from runtime_service.graphs.reference_agent import get_agent as get_reference_agent
from runtime_service.graphs.workflow_demo import get_agent as get_workflow_agent

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


def test_docker_uses_graphharbor_production_config() -> None:
    config = _load_config("langgraph.json")
    dockerfile = (PROJECT_ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "deploy/docker-compose.runtime-service.yml").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["graphharbor"]' in dockerfile
    assert '"--config", "${RUNTIME_GRAPH_CONFIG:-/app/langgraph.json}"' in compose
    assert list(config["graphs"]) == ["reference_agent"]


def test_docker_does_not_embed_stale_langgraph_api_registries() -> None:
    dockerfile = (PROJECT_ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")

    assert "LANGSERVE_GRAPHS" not in dockerfile
    assert "LANGGRAPH_AUTH" not in dockerfile
    assert "LANGGRAPH_HTTP" not in dockerfile


def test_deploy_env_requires_internal_runtime_context_signing() -> None:
    template = (PROJECT_ROOT / "deploy/.env.runtime-service.example").read_text(encoding="utf-8")

    assert "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET=" in template
    assert "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER=" in template
    assert "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE=graphharbor-worker" in template


def test_host_infra_compose_uses_external_postgres_and_redis() -> None:
    compose_path = PROJECT_ROOT / "deploy/docker-compose.runtime-service.host-infra.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert set(services) == {"migrate", "runtime-service", "worker"}
    assert not set(services) & {"postgres", "redis"}
    assert not any("depends_on" in service for service in services.values())

    expected_database = "${DATABASE_URI:?DATABASE_URI is required}"
    expected_redis = "${REDIS_URI:?REDIS_URI is required}"
    for service in services.values():
        environment = service["environment"]
        assert environment["DATABASE_URI"] == expected_database
        assert environment["REDIS_URI"] == expected_redis

    assert compose["volumes"] == {
        "runtime-service-host-infra-workspace-data": {"driver": "local"}
    }
    template = (PROJECT_ROOT / "deploy/.env.runtime-service.host-infra.example").read_text(
        encoding="utf-8"
    )
    assert "host.docker.internal" in template
    assert "DATABASE_URI=" in template and "REDIS_URI=" in template


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
