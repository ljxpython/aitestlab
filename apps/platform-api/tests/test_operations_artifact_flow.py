from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.modules.assistants.domain import AssistantItem
from app.modules.operations.application import CreateOperationCommand, OperationsService
from app.modules.operations.application.artifacts import LocalOperationArtifactStore
from app.modules.operations.application.execution import (
    DatabasePollingOperationDispatcher,
    OperationExecutorRegistry,
)
from app.modules.operations.application.executors import (
    AssistantResyncExecutor,
    TestcaseCasesExportExecutor,
    TestcaseDocumentsExportExecutor,
)
from app.modules.operations.application.worker import OperationWorker
from app.modules.operations.domain import OperationStatus
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class _FakeAssistantsService:
    async def resync_assistant(self, *, actor: ActorContext, assistant_id: str) -> AssistantItem:
        return AssistantItem(
            id=assistant_id,
            project_id=str(next(iter(actor.project_roles.keys()), "")),
            name="Research Demo",
            description="resynced by worker",
            graph_id="research_demo",
            langgraph_assistant_id="lg-assistant-1",
            runtime_base_url="http://127.0.0.1:8123",
            metadata={"source": "worker-test"},
        )


class _FakeTestcaseService:
    def __init__(self) -> None:
        self.last_documents_query = None
        self.last_cases_query = None

    async def export_documents(self, *, actor: ActorContext, project_id: str, query):  # type: ignore[no-untyped-def]
        self.last_documents_query = query
        return (
            "testcase-documents.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"documents-export",
        )

    async def export_cases(self, *, actor: ActorContext, project_id: str, query):  # type: ignore[no-untyped-def]
        self.last_cases_query = query
        return (
            "testcase-cases.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"cases-export",
        )


class OperationsArtifactFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "platform-api-test.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.project_id = self._create_project()
        self.actor = ActorContext(
            user_id=str(uuid4()),
            platform_roles=("platform_super_admin",),
            project_roles={self.project_id: ("project_admin",)},
        )
        self.artifact_store = LocalOperationArtifactStore(str(Path(self._tmpdir.name) / "artifacts"))
        self.fake_assistants = _FakeAssistantsService()
        self.fake_testcase = _FakeTestcaseService()
        self.service = OperationsService(
            session_factory=self._session_factory,
            dispatcher=DatabasePollingOperationDispatcher(),
            artifact_store=self.artifact_store,
        )
        self.worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry(
                (
                    AssistantResyncExecutor(service=self.fake_assistants),  # type: ignore[arg-type]
                    TestcaseDocumentsExportExecutor(
                        service=self.fake_testcase,  # type: ignore[arg-type]
                        artifact_store=self.artifact_store,
                    ),
                    TestcaseCasesExportExecutor(
                        service=self.fake_testcase,  # type: ignore[arg-type]
                        artifact_store=self.artifact_store,
                    ),
                )
            ),
            poll_interval_seconds=0.01,
            idle_sleep_seconds=0.01,
        )

    def tearDown(self) -> None:
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_project(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyProjectsRepository(session)
            tenant = repository.get_or_create_default_tenant()
            project = repository.create_project(
                tenant_id=tenant.id,
                name="Operations Smoke Project",
                description="phase-3 operation flow test",
            )
            return str(project.id)

    async def test_assistant_resync_operation_flow(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="assistant.resync",
                project_id=self.project_id,
                input_payload={"assistant_id": "assistant-123"},
            ),
        )

        processed = await self.worker.run_once()
        final = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(processed)
        self.assertEqual(final.status, OperationStatus.SUCCEEDED)
        self.assertEqual(final.result_payload["id"], "assistant-123")
        self.assertEqual(final.result_payload["name"], "Research Demo")

    async def test_testcase_documents_export_operation_persists_artifact(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="testcase.documents.export",
                project_id=self.project_id,
                input_payload={
                    "batch_id": "batch-1",
                    "parse_status": "parsed",
                    "query": "invoice",
                },
            ),
        )

        processed = await self.worker.run_once()
        final = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)
        artifact = await self.service.get_operation_artifact(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(processed)
        self.assertEqual(final.status, OperationStatus.SUCCEEDED)
        self.assertEqual(self.fake_testcase.last_documents_query.batch_id, "batch-1")
        self.assertEqual(self.fake_testcase.last_documents_query.parse_status, "parsed")
        self.assertEqual(self.fake_testcase.last_documents_query.query, "invoice")
        self.assertTrue(final.result_payload["artifact_ready"])
        self.assertEqual(final.result_payload["artifact_storage_backend"], "local")
        self.assertTrue(final.result_payload["artifact_expires_at"])
        self.assertEqual(artifact.filename, "testcase-documents.xlsx")
        self.assertEqual(artifact.path.read_bytes(), b"documents-export")

    async def test_testcase_cases_export_operation_persists_artifact(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="testcase.cases.export",
                project_id=self.project_id,
                input_payload={
                    "batch_id": "batch-2",
                    "status": "active",
                    "query": "login",
                    "columns": ["title", "priority", "status"],
                },
            ),
        )

        processed = await self.worker.run_once()
        final = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)
        artifact = await self.service.get_operation_artifact(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(processed)
        self.assertEqual(final.status, OperationStatus.SUCCEEDED)
        self.assertEqual(self.fake_testcase.last_cases_query.batch_id, "batch-2")
        self.assertEqual(self.fake_testcase.last_cases_query.status, "active")
        self.assertEqual(self.fake_testcase.last_cases_query.query, "login")
        self.assertEqual(self.fake_testcase.last_cases_query.columns, ("title", "priority", "status"))
        self.assertTrue(final.result_payload["artifact_ready"])
        self.assertEqual(final.result_payload["artifact_storage_backend"], "local")
        self.assertTrue(final.result_payload["artifact_expires_at"])
        self.assertEqual(artifact.filename, "testcase-cases.xlsx")
        self.assertEqual(artifact.path.read_bytes(), b"cases-export")


if __name__ == "__main__":
    unittest.main()
