from __future__ import annotations

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_graph_descriptions(config: dict) -> None:
    graphs = config.get("graphs", {})
    assert isinstance(graphs, dict)
    assert graphs

    for graph_id, value in graphs.items():
        assert isinstance(graph_id, str) and graph_id
        assert isinstance(value, dict)
        assert isinstance(value.get("path"), str) and value["path"]
        assert (
            isinstance(value.get("description"), str) and value["description"].strip()
        )


def test_langgraph_json_graph_entries_include_descriptions() -> None:
    config_path = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    _assert_graph_descriptions(_load_json(config_path))


def test_langgraph_auth_json_graph_entries_include_descriptions() -> None:
    config_path = _PROJECT_ROOT / "runtime_service" / "langgraph_auth.json"
    _assert_graph_descriptions(_load_json(config_path))
