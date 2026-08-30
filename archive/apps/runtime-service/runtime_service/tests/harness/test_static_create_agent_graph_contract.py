from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _graph_source(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("relative_path", "state_schema_name"),
    [
        ("agents/customer_support_agent/graph.py", "SupportState"),
        ("agents/personal_assistant_agent/graph.py", "MultimodalAgentState"),
        ("agents/skills_sql_assistant_agent/graph.py", "MultimodalAgentState"),
    ],
)
def test_static_create_agent_graph_exports_explicit_contract(
    relative_path: str,
    state_schema_name: str,
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

    graph_call = graph_assignments[-1].value
    assert isinstance(graph_call, ast.Call)
    assert isinstance(graph_call.func, ast.Name)
    assert graph_call.func.id == "create_agent"

    keywords = {
        keyword.arg: keyword.value
        for keyword in graph_call.keywords
        if keyword.arg is not None
    }

    assert "context_schema" in keywords
    context_schema_value = keywords["context_schema"]
    assert isinstance(context_schema_value, ast.Name)
    assert context_schema_value.id == "RuntimeContext"

    assert "state_schema" in keywords
    state_schema_value = keywords["state_schema"]
    assert isinstance(state_schema_value, ast.Name)
    assert state_schema_value.id == state_schema_name


@pytest.mark.parametrize(
    "relative_path",
    [
        "agents/customer_support_agent/graph.py",
        "agents/personal_assistant_agent/graph.py",
        "agents/skills_sql_assistant_agent/graph.py",
    ],
)
def test_static_create_agent_graph_uses_runtime_request_middleware(
    relative_path: str,
) -> None:
    source = _graph_source(relative_path)
    assert "RuntimeRequestMiddleware(" in source
