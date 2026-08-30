from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any, get_args, get_origin

from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import BaseTool
from langgraph.prebuilt.tool_node import ToolCallRequest


class ToolRuntimeContextSanitizerMiddleware(AgentMiddleware[Any, Any]):
    """Sanitize runtime.context for tools that explicitly declare no context."""

    def __init__(self) -> None:
        self._requires_sanitized_context_by_tool_name: dict[str, bool] = {}

    def _should_strip_runtime_context(self, tool: BaseTool | None) -> bool:
        if tool is None:
            return False
        tool_name = str(getattr(tool, "name", "") or "")
        if tool_name in self._requires_sanitized_context_by_tool_name:
            return self._requires_sanitized_context_by_tool_name[tool_name]

        should_strip = False
        try:
            input_schema = tool.get_input_schema()
            runtime_field = input_schema.model_fields.get("runtime")
            annotation = runtime_field.annotation if runtime_field is not None else None
            should_strip = self._annotation_expects_none_context(annotation)
        except Exception:
            should_strip = False

        if tool_name:
            self._requires_sanitized_context_by_tool_name[tool_name] = should_strip
        return should_strip

    @staticmethod
    def _annotation_expects_none_context(annotation: Any) -> bool:
        origin = get_origin(annotation)
        if origin is None or getattr(origin, "__name__", "") != "ToolRuntime":
            return False
        args = get_args(annotation)
        if len(args) < 1:
            return False
        return args[0] is type(None)

    @staticmethod
    def _strip_runtime_context(request: ToolCallRequest) -> ToolCallRequest:
        runtime = getattr(request, "runtime", None)
        if runtime is None or getattr(runtime, "context", None) is None:
            return request
        return replace(request, runtime=replace(runtime, context=None))

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        next_request = (
            self._strip_runtime_context(request)
            if self._should_strip_runtime_context(request.tool)
            else request
        )
        return handler(next_request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        next_request = (
            self._strip_runtime_context(request)
            if self._should_strip_runtime_context(request.tool)
            else request
        )
        return await handler(next_request)


__all__ = ["ToolRuntimeContextSanitizerMiddleware"]
