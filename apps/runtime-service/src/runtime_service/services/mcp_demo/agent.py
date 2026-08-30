"""Composition root for the service-private fake MCP demo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.pregel import Pregel

from runtime_service.observability import with_langfuse_tracing
from runtime_service.services.mcp_demo.loader import load_mcp_tools


class _DemoChatModel(FakeListChatModel):
    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


_DEFAULT_MODEL = _DemoChatModel(responses=["mcp demo response"])


async def get_agent(config: RunnableConfig) -> Pregel:
    """Load fake MCP tools before creating the agent graph."""

    configurable = config.get("configurable") or {}
    candidate = configurable.get("_runtime_model") if isinstance(configurable, Mapping) else None
    conflict = bool(configurable.get("_mcp_conflict")) if isinstance(configurable, Mapping) else False
    model = candidate if isinstance(candidate, BaseChatModel) else _DEFAULT_MODEL
    tools = await load_mcp_tools(conflict=conflict)
    agent = create_agent(model=model, tools=tools, name="mcp_demo")
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_model", None)
    bound_configurable.pop("_mcp_conflict", None)
    bound_config["configurable"] = bound_configurable
    return with_langfuse_tracing(agent, bound_config, graph_id="mcp_demo")


__all__ = ["get_agent"]
