from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _graph_source(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("relative_path", "factory_name"),
    [
        ("agents/deepagent_agent/graph.py", "create_deep_agent"),
        ("agents/research_agent/graph.py", "create_deep_agent"),
        ("services/test_case_service/graph.py", "create_deep_agent"),
        ("services/test_case_service_v2/graph.py", "create_deep_agent"),
    ],
)
def test_static_runtime_graph_exports_top_level_graph_call(
    relative_path: str,
    factory_name: str,
) -> None:
    source = _graph_source(relative_path)
    tree = ast.parse(source)

    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "make_graph" not in function_names

    graph_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "graph"
            for target in node.targets
        )
    ]
    assert graph_assignments, f"{relative_path} must export top-level `graph`."

    graph_value = graph_assignments[-1].value
    assert isinstance(graph_value, ast.Call)
    assert isinstance(graph_value.func, ast.Name)
    assert graph_value.func.id == factory_name


@pytest.mark.parametrize(
    "relative_path",
    [
        "agents/deepagent_agent/graph.py",
        "agents/research_agent/graph.py",
        "services/test_case_service/graph.py",
        "services/test_case_service_v2/graph.py",
    ],
)
def test_static_runtime_graph_declares_runtime_context_schema(
    relative_path: str,
) -> None:
    source = _graph_source(relative_path)
    tree = ast.parse(source)

    graph_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "graph"
            for target in node.targets
        )
    ]
    assert graph_assignments, f"{relative_path} must export top-level `graph`."

    graph_call = graph_assignments[-1].value
    assert isinstance(graph_call, ast.Call)

    keywords = {
        keyword.arg: keyword.value
        for keyword in graph_call.keywords
        if keyword.arg is not None
    }
    assert "context_schema" in keywords
    context_schema_value = keywords["context_schema"]
    assert isinstance(context_schema_value, ast.Name)
    assert context_schema_value.id == "RuntimeContext"


@pytest.mark.parametrize(
    "relative_path",
    [
        "agents/deepagent_agent/graph.py",
        "agents/research_agent/graph.py",
        "services/test_case_service/graph.py",
        "services/test_case_service_v2/graph.py",
    ],
)
def test_static_runtime_graph_uses_runtime_request_middleware(
    relative_path: str,
) -> None:
    source = _graph_source(relative_path)
    assert "RuntimeRequestMiddleware(" in source
