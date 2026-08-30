from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langgraph.types import Command
from runtime_service.middlewares.multimodal import MULTIMODAL_ATTACHMENTS_KEY, MultimodalAgentState
from runtime_service.services.test_case_service.document_persistence import (
    apersist_runtime_documents,
    persist_runtime_documents,
)
from runtime_service.services.test_case_service.schemas import TestCaseServiceConfig


class TestCaseDocumentPersistenceMiddleware(AgentMiddleware[MultimodalAgentState, Any]):
    state_schema = MultimodalAgentState

    def __init__(self, service_config: TestCaseServiceConfig) -> None:
        self._service_config = service_config

    @staticmethod
    def _should_persist(request: ModelRequest) -> bool:
        state = request.state if isinstance(request.state, Mapping) else {}
        attachments = state.get(MULTIMODAL_ATTACHMENTS_KEY)
        return isinstance(attachments, list) and len(attachments) > 0

    @staticmethod
    def _with_updated_state(
        request: ModelRequest,
        updated_attachments: list[dict[str, Any]],
    ) -> ModelRequest:
        next_state = dict(request.state if isinstance(request.state, Mapping) else {})
        next_state[MULTIMODAL_ATTACHMENTS_KEY] = updated_attachments
        return request.override(state=next_state)

    @staticmethod
    def _state_update_command(updated_attachments: list[dict[str, Any]]) -> Command[Any]:
        return Command(update={MULTIMODAL_ATTACHMENTS_KEY: updated_attachments})

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        if not self._service_config.persistence_enabled or not self._should_persist(request):
            return handler(request)
        outcome = persist_runtime_documents(
            runtime=request.runtime,
            state=request.state if isinstance(request.state, Mapping) else {},
            service_config=self._service_config,
            messages=list(request.messages),
        )
        updated_request = self._with_updated_state(request, outcome.attachments)
        response = handler(updated_request)
        return ExtendedModelResponse(
            model_response=response,
            command=self._state_update_command(outcome.attachments),
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        if not self._service_config.persistence_enabled or not self._should_persist(request):
            return await handler(request)
        outcome = await apersist_runtime_documents(
            runtime=request.runtime,
            state=request.state if isinstance(request.state, Mapping) else {},
            service_config=self._service_config,
            messages=list(request.messages),
        )
        updated_request = self._with_updated_state(request, outcome.attachments)
        response = await handler(updated_request)
        return ExtendedModelResponse(
            model_response=response,
            command=self._state_update_command(outcome.attachments),
        )


__all__ = ["TestCaseDocumentPersistenceMiddleware"]
