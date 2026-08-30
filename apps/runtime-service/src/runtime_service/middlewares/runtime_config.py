"""Runtime contract enforcement at LangChain model and tool boundaries."""

from __future__ import annotations

from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ToolCallRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from runtime_service.runtime import (
    AgentDefaults,
    ResolvedRuntimeConfig,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    build_model,
    parse_runtime_context,
    resolve_runtime_config,
)
from runtime_service.runtime.errors import RuntimeResolutionError

ModelBuilder = Callable[[ResolvedRuntimeConfig], BaseChatModel]


def _tool_name(tool: BaseTool | Callable[..., object] | dict[str, object]) -> str | None:
    if isinstance(tool, dict):
        value = tool.get("name")
    else:
        value = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    return value if isinstance(value, str) else None


class RuntimeConfigMiddleware(AgentMiddleware[object, RuntimeContext, object]):
    """Re-resolve immutable Runtime values before model and tool execution."""

    def __init__(
        self,
        *,
        principal: RuntimePrincipal,
        policy: RuntimePolicy,
        defaults: AgentDefaults,
        base_model: BaseChatModel,
        model_builder: ModelBuilder = build_model,
    ) -> None:
        super().__init__()
        self._principal = principal
        self._policy = policy
        self._defaults = defaults
        self._base_model = base_model
        self._model_builder = model_builder

    def _resolve(self, runtime: object) -> ResolvedRuntimeConfig:
        context = parse_runtime_context(getattr(runtime, "context", None))
        return resolve_runtime_config(
            principal=self._principal,
            context=context,
            policy=self._policy,
            defaults=self._defaults,
        )

    async def abefore_agent(self, state: object, runtime: object) -> None:
        self._resolve(runtime)

    async def awrap_model_call(self, request: ModelRequest, handler):
        resolved = self._resolve(request.runtime)
        model = self._base_model
        if (
            resolved.model_id != self._defaults.model_id
            or resolved.temperature != self._defaults.temperature
            or resolved.max_tokens != self._defaults.max_tokens
            or resolved.top_p != self._defaults.top_p
        ):
            model = self._model_builder(resolved)

        allowed = set(resolved.required_tool_names) | set(resolved.optional_tool_names)
        tools = request.tools
        if tools is not None:
            filtered = []
            for tool in tools:
                name = _tool_name(tool)
                if name is None or name not in allowed:
                    continue
                filtered.append(tool)
            tools = filtered
        return await handler(request.override(model=model, tools=tools))

    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        resolved = self._resolve(request.runtime)
        name = request.tool_call.get("name")
        allowed = set(resolved.required_tool_names) | set(resolved.optional_tool_names)
        if not isinstance(name, str) or name not in allowed:
            raise RuntimeResolutionError("runtime.tool.not_allowed", "tool_name")
        return await handler(request)


__all__ = ["RuntimeConfigMiddleware"]
