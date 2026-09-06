from __future__ import annotations

from typing import Any

from app.core.context.models import ActorContext
from app.modules.agents.application import AssistantsService
from app.modules.operations.application.artifacts import LocalOperationArtifactStore
from app.modules.operations.application.ports import (
    OperationExecutionResult,
    OperationExecutorProtocol,
    StoredOperation,
)
from app.modules.testcase.application import (
    ExportTestcaseCasesQuery,
    ExportTestcaseDocumentsQuery,
    TestcaseService,
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


class AssistantResyncExecutor(OperationExecutorProtocol):
    kind = "assistant.resync"

    def __init__(self, *, service: AssistantsService) -> None:
        self._service = service

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        assistant_id = _clean(operation.input_payload.get("assistant_id"))
        if not assistant_id:
            raise ValueError("assistant_id is required for assistant resync operation")

        item = await self._service.resync_assistant(actor=actor, assistant_id=assistant_id)
        return OperationExecutionResult(
            result_payload=item.model_dump(mode="json"),
            metadata={
                "assistant_id": item.id,
                "project_id": item.project_id,
            },
        )


class TestcaseDocumentsExportExecutor(OperationExecutorProtocol):
    kind = "testcase.documents.export"

    def __init__(
        self,
        *,
        service: TestcaseService,
        artifact_store: LocalOperationArtifactStore,
    ) -> None:
        self._service = service
        self._artifact_store = artifact_store

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        project_id = _clean(operation.project_id)
        if not project_id:
            raise ValueError("project_id is required for testcase documents export")

        filename, media_type, payload = await self._service.export_documents(
            actor=actor,
            project_id=project_id,
            query=ExportTestcaseDocumentsQuery(
                batch_id=_clean(operation.input_payload.get("batch_id")),
                parse_status=_clean(operation.input_payload.get("parse_status")),
                query=_clean(operation.input_payload.get("query")),
            ),
        )
        artifact = self._artifact_store.save_bytes(
            operation_id=operation.id,
            filename=filename,
            media_type=media_type,
            payload=payload,
        )
        return OperationExecutionResult(
            result_payload={
                "project_id": project_id,
                "filename": filename,
                "media_type": media_type,
                "artifact_ready": True,
                "artifact_storage_backend": artifact.get("storage_backend"),
                "artifact_expires_at": artifact.get("expires_at"),
                "_artifact": artifact,
            },
            metadata={
                "artifact_ready": True,
                "filename": filename,
            },
        )


class TestcaseCasesExportExecutor(OperationExecutorProtocol):
    kind = "testcase.cases.export"

    def __init__(
        self,
        *,
        service: TestcaseService,
        artifact_store: LocalOperationArtifactStore,
    ) -> None:
        self._service = service
        self._artifact_store = artifact_store

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        project_id = _clean(operation.project_id)
        if not project_id:
            raise ValueError("project_id is required for testcase cases export")

        raw_columns = operation.input_payload.get("columns")
        columns = (
            tuple(str(item).strip() for item in raw_columns if str(item).strip())
            if isinstance(raw_columns, list)
            else ()
        )
        filename, media_type, payload = await self._service.export_cases(
            actor=actor,
            project_id=project_id,
            query=ExportTestcaseCasesQuery(
                batch_id=_clean(operation.input_payload.get("batch_id")),
                status=_clean(operation.input_payload.get("status")),
                query=_clean(operation.input_payload.get("query")),
                columns=columns,
            ),
        )
        artifact = self._artifact_store.save_bytes(
            operation_id=operation.id,
            filename=filename,
            media_type=media_type,
            payload=payload,
        )
        return OperationExecutionResult(
            result_payload={
                "project_id": project_id,
                "filename": filename,
                "media_type": media_type,
                "artifact_ready": True,
                "artifact_storage_backend": artifact.get("storage_backend"),
                "artifact_expires_at": artifact.get("expires_at"),
                "_artifact": artifact,
            },
            metadata={
                "artifact_ready": True,
                "filename": filename,
            },
        )
