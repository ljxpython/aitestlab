from __future__ import annotations

import ast
from pathlib import Path


def _assistant_graph_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "agents"
        / "assistant_agent"
        / "graph.py"
    )


def test_assistant_graph_is_static_create_agent_export() -> None:
    source = _assistant_graph_path().read_text(encoding="utf-8")
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
        and any(isinstance(target, ast.Name) and target.id == "graph" for target in node.targets)
    ]
    assert graph_assignments, "assistant graph.py must export top-level `graph`."

    graph_value = graph_assignments[-1].value
    assert isinstance(graph_value, ast.Call)
    assert isinstance(graph_value.func, ast.Name)
    assert graph_value.func.id == "create_agent"


def test_assistant_graph_declares_context_schema_runtime_context() -> None:
    source = _assistant_graph_path().read_text(encoding="utf-8")
    tree = ast.parse(source)

    graph_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "graph" for target in node.targets)
    ]
    assert graph_assignments, "assistant graph.py must export top-level `graph`."

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


def test_assistant_graph_uses_runtime_request_middleware() -> None:
    source = _assistant_graph_path().read_text(encoding="utf-8")
    assert "RuntimeRequestMiddleware(" in source
