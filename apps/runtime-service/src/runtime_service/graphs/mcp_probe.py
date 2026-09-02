"""Deterministic R6 probe for a Thread-bound MCP resource."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeErrorBase,
    RuntimeResolutionError,
    parse_runtime_context,
    resolve_runtime_config,
    verified_delegation_from_user,
)
from runtime_service.services.mcp_demo.loader import load_mcp_tools


class MCPProbeState(TypedDict, total=False):
    topic: str
    observed: str


_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt="R6 MCP resource probe.",
    prompt_version="mcp-probe-v1",
    optional_tool_names=("mcp_read",),
)


def _result_text(result: object) -> str:
    if isinstance(result, list):
        text_parts = [
            item["text"]
            for item in result
            if isinstance(item, Mapping) and isinstance(item.get("text"), str)
        ]
        if text_parts:
            return "\n".join(text_parts)
    return str(result)


async def mcp_probe(state: MCPProbeState, config: RunnableConfig) -> MCPProbeState:
    """Reconnect the server-owned binding, discover exactly one tool, and call it."""

    try:
        configurable = config.get("configurable") or {}
        if not isinstance(configurable, Mapping):
            raise RuntimeResolutionError("runtime.mcp.recovery_failed")
        facts = verified_delegation_from_user(configurable.get("langgraph_auth_user"))
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=parse_runtime_context(config.get("context")),
            policy=facts.policy,
            defaults=_DEFAULTS,
            tool_permissions={"mcp_read": "runtime.tool.read"},
        )
        tools = await load_mcp_tools(
            allowed_names=resolved.optional_tool_names,
            config=config,
            principal=facts.principal,
        )
        tool = next((candidate for candidate in tools if candidate.name == "mcp_read"), None)
        if tool is None:
            raise RuntimeResolutionError("runtime.mcp.recovery_failed")
        result = await tool.ainvoke({"topic": state.get("topic", "GraphHarbor")})
        return {"observed": _result_text(result)}
    except RuntimeErrorBase:
        raise
    except Exception as exc:
        raise RuntimeResolutionError("runtime.mcp.recovery_failed") from exc


_builder = StateGraph(MCPProbeState)
_builder.add_node("mcp_probe", mcp_probe)
_builder.add_edge(START, "mcp_probe")
_builder.add_edge("mcp_probe", END)
_graph = _builder.compile()


async def get_agent(_config: RunnableConfig) -> Pregel:
    return _graph


__all__ = ["get_agent", "mcp_probe"]
