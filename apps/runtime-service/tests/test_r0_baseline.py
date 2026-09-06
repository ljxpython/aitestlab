from __future__ import annotations

import ast
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
from support import BindableFakeChatModel

from runtime_service.graphs.reference_agent import get_agent as get_reference_agent
from runtime_service.graphs.workflow_demo import get_agent as get_workflow_agent

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_config(name: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / name).read_text(encoding="utf-8"))


def test_installed_package_imports_without_test_path(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runtime_service; print(runtime_service.__file__)",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    module_path = Path(result.stdout.strip())
    assert module_path.name == "__init__.py"
    assert module_path.parent.name == "runtime_service"
    assert not module_path.is_relative_to(PROJECT_ROOT / "runtime_service")


def test_new_package_is_loaded_from_src() -> None:
    import runtime_service

    assert Path(runtime_service.__file__).resolve().is_relative_to(PROJECT_ROOT / "src")


def test_production_config_registers_model_backed_agents() -> None:
    config = _load_config("langgraph.json")
    graphs = config["graphs"]

    assert list(graphs) == ["reference_agent", "workflow_demo"]
    assert all(item["path"].startswith("./src/runtime_service/graphs/") for item in graphs.values())
    assert all(item["description"] for item in graphs.values())


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
    compose = (PROJECT_ROOT / "deploy/docker-compose.runtime-service.yml").read_text(
        encoding="utf-8"
    )

    assert 'ENTRYPOINT ["graphharbor"]' in dockerfile
    assert '"--config", "${RUNTIME_GRAPH_CONFIG:-/app/langgraph.json}"' in compose
    assert list(config["graphs"]) == ["reference_agent", "workflow_demo"]


def test_docker_does_not_embed_stale_langgraph_api_registries() -> None:
    dockerfile = (PROJECT_ROOT / "deploy/Dockerfile").read_text(encoding="utf-8")

    assert "LANGSERVE_GRAPHS" not in dockerfile
    assert "LANGGRAPH_AUTH" not in dockerfile
    assert "LANGGRAPH_HTTP" not in dockerfile


def test_deploy_env_requires_internal_runtime_context_signing() -> None:
    template = (PROJECT_ROOT / "deploy/.env.runtime-service.example").read_text(
        encoding="utf-8"
    )

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
    template = (
        PROJECT_ROOT / "deploy/.env.runtime-service.host-infra.example"
    ).read_text(encoding="utf-8")
    assert "host.docker.internal" in template
    assert "DATABASE_URI=" in template and "REDIS_URI=" in template


def test_r0_services_have_readme_and_dedicated_tests() -> None:
    for package_root, package_name in (
        (PROJECT_ROOT / "src/runtime_service/services", "reference_agent"),
        (PROJECT_ROOT / "src/runtime_service/services/demo", "workflow_demo"),
    ):
        service_root = package_root / package_name
        test_root = PROJECT_ROOT / "tests/services" / package_name

        assert (service_root / "README.md").is_file()
        assert any(test_root.glob("test_*.py"))


def test_production_services_do_not_import_each_other() -> None:
    services_root = PROJECT_ROOT / "src/runtime_service/services"
    service_names = {
        path.name
        for path in services_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    }
    violations: list[str] = []

    for service_root in sorted(services_root.iterdir()):
        if service_root.name not in service_names:
            continue
        for source_path in sorted(service_root.rglob("*.py")):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        base = ["runtime_service", "services", service_root.name]
                        if node.level > 1:
                            base = base[: -(node.level - 1)]
                        imported = node.module or ""
                        modules = [".".join([*base, *imported.split(".")])]
                        if not node.module:
                            modules.extend(
                                ".".join([*base, alias.name]) for alias in node.names
                            )
                    elif node.module:
                        modules = [node.module]
                    else:
                        modules = []
                else:
                    continue

                for module in modules:
                    parts = module.split(".")
                    if (
                        len(parts) >= 4
                        and parts[:3] == ["runtime_service", "services"]
                        and parts[3] in service_names
                        and parts[3] != service_root.name
                    ):
                        violations.append(
                            f"{source_path.relative_to(PROJECT_ROOT)} imports {module}"
                        )

    assert violations == []


def test_service_entrypoints_return_pregel() -> None:
    config: RunnableConfig = {
        "configurable": {
            "_runtime_model": BindableFakeChatModel(
                responses=["reference agent response"]
            )
        }
    }

    reference = asyncio.run(get_reference_agent(config))
    workflow = asyncio.run(get_workflow_agent(config))

    assert isinstance(reference, Pregel)
    assert isinstance(workflow, Pregel)


def test_reference_agent_uses_deterministic_fake_model() -> None:
    graph = asyncio.run(
        get_reference_agent(
            {
                "configurable": {
                    "_runtime_model": BindableFakeChatModel(
                        responses=["reference agent response"]
                    )
                }
            }
        )
    )
    result = asyncio.run(
        graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]})
    )

    assert result["messages"][-1].content == "reference agent response"


def test_workflow_demo_calls_the_model_for_default_route() -> None:
    graph = asyncio.run(
        get_workflow_agent(
            {"configurable": {"_runtime_model": BindableFakeChatModel(responses=["model response"])}}
        )
    )
    result = asyncio.run(
        graph.ainvoke(
            {"message": "hello"},
            {"configurable": {"thread_id": "r0-workflow-baseline"}},
        )
    )

    assert result["response"] == "model response"
