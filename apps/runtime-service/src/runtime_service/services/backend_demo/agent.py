"""Composition root for the StateBackend isolation demo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.pregel import Pregel


class _DemoChatModel(FakeListChatModel):
    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


_DEFAULT_MODEL = _DemoChatModel(responses=["backend demo response"])


async def get_agent(config: RunnableConfig) -> Pregel:
    """Create a fresh StateBackend bound to this graph instance."""

    configurable = config.get("configurable") or {}
    candidate = configurable.get("_runtime_model") if isinstance(configurable, Mapping) else None
    model = candidate if isinstance(candidate, BaseChatModel) else _DEFAULT_MODEL
    agent = create_deep_agent(
        model=model,
        backend=StateBackend(),
        name="backend_demo",
    )
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_model", None)
    bound_config["configurable"] = bound_configurable
    return agent.with_config(bound_config)


__all__ = ["get_agent"]
