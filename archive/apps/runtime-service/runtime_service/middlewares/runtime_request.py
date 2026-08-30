from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain.messages import SystemMessage, ToolMessage
from langgraph.config import get_config
from langgraph.types import Command
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    ResolvedRuntimeSettings,
    build_tool_catalog,
    dedupe_tools_by_name,
    normalize_tool_name,
    resolve_optional_tools,
    resolve_runtime_settings,
)


class RuntimeRequestMiddleware(AgentMiddleware):
    def __init__(
        self,
        *,
        defaults: AgentDefaults,
        required_tools: Sequence[Any],
        public_tools: Sequence[Any],
        required_tool_resolver: (
            Callable[[ResolvedRuntimeSettings], Sequence[Any]] | None
        ) = None,
        arequired_tool_resolver: (
            Callable[[ResolvedRuntimeSettings], Awaitable[Sequence[Any]]] | None
        ) = None,
        public_tool_resolver: (
            Callable[[ResolvedRuntimeSettings], Sequence[Any]] | None
        ) = None,
        apublic_tool_resolver: (
            Callable[[ResolvedRuntimeSettings], Awaitable[Sequence[Any]]] | None
        ) = None,
        system_prompt_resolver: Callable[[ResolvedRuntimeSettings], str] | None = None,
        allow_internal_context: bool = False,
    ) -> None:
        self.defaults = defaults
        self.required_tools = list(required_tools)
        self.public_tools = list(public_tools)
        self.required_tool_resolver = required_tool_resolver
        self.arequired_tool_resolver = arequired_tool_resolver
        self.public_tool_resolver = public_tool_resolver
        self.apublic_tool_resolver = apublic_tool_resolver
        self.system_prompt_resolver = system_prompt_resolver
        self.allow_internal_context = allow_internal_context

    def _resolve_settings(
        self,
        request: ModelRequest | ToolCallRequest,
    ) -> ResolvedRuntimeSettings:
        return resolve_runtime_settings(
            runtime=request.runtime,
            config=get_config(),
            defaults=self.defaults,
            allow_internal_context=self.allow_internal_context,
        )

    def _resolve_required_tools_sync(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        if self.required_tool_resolver is not None:
            return list(self.required_tool_resolver(settings))
        if self.arequired_tool_resolver is not None:
            raise TypeError("arequired_tool_resolver is not available in sync model calls.")
        return list(self.required_tools)

    async def _resolve_required_tools_async(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        if self.arequired_tool_resolver is not None:
            return list(await self.arequired_tool_resolver(settings))
        if self.required_tool_resolver is not None:
            return list(self.required_tool_resolver(settings))
        return list(self.required_tools)

    def _resolve_public_tools_sync(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        if not settings.enable_tools:
            return []
        if self.public_tool_resolver is not None:
            return list(self.public_tool_resolver(settings))
        if self.apublic_tool_resolver is not None:
            raise TypeError("apublic_tool_resolver is not available in sync model calls.")
        return resolve_optional_tools(
            build_tool_catalog(self.public_tools),
            settings.requested_public_tool_names,
        )

    async def _resolve_public_tools_async(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        if not settings.enable_tools:
            return []
        if self.apublic_tool_resolver is not None:
            return list(await self.apublic_tool_resolver(settings))
        if self.public_tool_resolver is not None:
            return list(self.public_tool_resolver(settings))
        return resolve_optional_tools(
            build_tool_catalog(self.public_tools),
            settings.requested_public_tool_names,
        )

    def _resolve_system_prompt(self, settings: ResolvedRuntimeSettings) -> str:
        if self.system_prompt_resolver is not None:
            return self.system_prompt_resolver(settings)
        return settings.system_prompt

    def _resolve_runtime_tools_sync(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        return dedupe_tools_by_name(
            [
                *self._resolve_required_tools_sync(settings),
                *self._resolve_public_tools_sync(settings),
            ]
        )

    async def _resolve_runtime_tools_async(
        self,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        return dedupe_tools_by_name(
            [
                *(await self._resolve_required_tools_async(settings)),
                *(await self._resolve_public_tools_async(settings)),
            ]
        )

    def _resolve_tools_sync(
        self,
        request: ModelRequest,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        return self._merge_runtime_tools(
            request.tools,
            self._resolve_runtime_tools_sync(settings),
        )

    async def _resolve_tools_async(
        self,
        request: ModelRequest,
        settings: ResolvedRuntimeSettings,
    ) -> list[Any]:
        return self._merge_runtime_tools(
            request.tools,
            await self._resolve_runtime_tools_async(settings),
        )

    def _merge_runtime_tools(
        self,
        registered_tools: Sequence[Any],
        runtime_tools: Sequence[Any],
    ) -> list[Any]:
        public_tool_names = set(build_tool_catalog(self.public_tools))

        base_tools = [
            tool
            for tool in registered_tools
            if str(getattr(tool, "name", "") or "").strip().lower()
            not in public_tool_names
        ]
        return dedupe_tools_by_name([*base_tools, *runtime_tools])

    def _bind_runtime_tool_sync(self, request: ToolCallRequest) -> ToolCallRequest:
        if request.tool is not None:
            return request
        settings = self._resolve_settings(request)
        runtime_tool = build_tool_catalog(
            self._resolve_runtime_tools_sync(settings)
        ).get(normalize_tool_name(request.tool_call["name"]))
        return request.override(tool=runtime_tool) if runtime_tool is not None else request

    async def _bind_runtime_tool_async(
        self,
        request: ToolCallRequest,
    ) -> ToolCallRequest:
        if request.tool is not None:
            return request
        settings = self._resolve_settings(request)
        runtime_tool = build_tool_catalog(
            await self._resolve_runtime_tools_async(settings)
        ).get(normalize_tool_name(request.tool_call["name"]))
        return request.override(tool=runtime_tool) if runtime_tool is not None else request

    def _apply_runtime_request_sync(self, request: ModelRequest) -> ModelRequest:
        settings = self._resolve_settings(request)
        return request.override(
            model=settings.model,
            tools=self._resolve_tools_sync(request, settings),
            system_message=SystemMessage(content=self._resolve_system_prompt(settings)),
        )

    async def _apply_runtime_request_async(self, request: ModelRequest) -> ModelRequest:
        settings = self._resolve_settings(request)
        return request.override(
            model=settings.model,
            tools=await self._resolve_tools_async(request, settings),
            system_message=SystemMessage(content=self._resolve_system_prompt(settings)),
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._apply_runtime_request_sync(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(await self._apply_runtime_request_async(request))

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        return handler(self._bind_runtime_tool_sync(request))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[
            [ToolCallRequest],
            Awaitable[ToolMessage | Command[Any]],
        ],
    ) -> ToolMessage | Command[Any]:
        return await handler(await self._bind_runtime_tool_async(request))
