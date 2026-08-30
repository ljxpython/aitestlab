from __future__ import annotations

from importlib import import_module
from typing import Any

_GRAPH_EXPORTS = {
    "assistant_graph": ("runtime_service.agents.assistant_agent.graph", "graph"),
    "customer_support_graph": (
        "runtime_service.agents.customer_support_agent.graph",
        "graph",
    ),
    "deepagent_graph": ("runtime_service.agents.deepagent_agent.graph", "graph"),
    "personal_assistant_graph": (
        "runtime_service.agents.personal_assistant_agent.graph",
        "graph",
    ),
    "research_graph": ("runtime_service.agents.research_agent.graph", "graph"),
    "skills_sql_assistant_graph": (
        "runtime_service.agents.skills_sql_assistant_agent.graph",
        "graph",
    ),
}

__all__ = list(_GRAPH_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _GRAPH_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = target
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
