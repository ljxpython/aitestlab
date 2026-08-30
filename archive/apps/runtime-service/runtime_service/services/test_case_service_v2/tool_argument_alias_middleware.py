from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langgraph.prebuilt.tool_node import ToolCallRequest

READ_FILE_TOOL_NAME = "read_file"


class ToolArgumentAliasMiddleware(AgentMiddleware[Any, Any]):
    """Normalize known tool arg aliases used by models during tool calling."""

    @staticmethod
    def _normalize_tool_args(request: ToolCallRequest) -> ToolCallRequest:
        tool_call = getattr(request, "tool_call", None)
        if not isinstance(tool_call, Mapping):
            return request

        tool_name = str(tool_call.get("name") or "").strip()
        args = tool_call.get("args")
        if tool_name != READ_FILE_TOOL_NAME or not isinstance(args, Mapping):
            return request

        if "file_path" in args or "path" not in args:
            return request

        next_args = dict(args)
        next_args["file_path"] = args.get("path")
        next_tool_call = dict(tool_call)
        next_tool_call["args"] = next_args
        return replace(request, tool_call=next_tool_call)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        return handler(self._normalize_tool_args(request))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        return await handler(self._normalize_tool_args(request))


__all__ = ["ToolArgumentAliasMiddleware"]
