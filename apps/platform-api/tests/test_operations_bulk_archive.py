from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.modules.operations.application import (
    BulkArchiveOperationsCommand,
    BulkCancelOperationsCommand,
    BulkRestoreOperationsCommand,
    CreateOperationCommand,
    ListOperationsQuery,
    OperationsService,
)
from app.modules.operations.application.execution import DatabasePollingOperationDispatcher
from app.modules.operations.domain import OperationArchiveScope, OperationStatus
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class OperationsBulkArchiveTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "operations-bulk-archive.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.project_id = self._create_project()
        self.actor = ActorContext(
            user_id=str(uuid4()),
            platform_roles=("platform_super_admin",),
            project_roles={self.project_id: ("project_admin",)},
        )
        self.service = OperationsService(
            session_factory=self._session_factory,
            dispatcher=DatabasePollingOperationDispatcher(),
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
                name="Operations Bulk Project",
                description="phase-4 bulk archive test",
            )
            return str(project.id)

    async def _submit_operation(self, *, kind: str, status: OperationStatus) -> str:
        operation = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind=kind,
                project_id=self.project_id,
                input_payload={"value": kind},
            ),
        )
        if status != OperationStatus.SUBMITTED:
            with session_scope(self._session_factory) as session:
                from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository

                repository = SqlAlchemyOperationsRepository(session)
                repository.update_status(
                    operation_id=operation.id,
                    status=status,
                )
        return operation.id

    async def test_bulk_cancel_archive_restore_and_list_filters(self) -> None:
        running_id = await self._submit_operation(kind="runtime.models.refresh", status=OperationStatus.RUNNING)
        succeeded_id = await self._submit_operation(kind="assistant.resync", status=OperationStatus.SUCCEEDED)
        failed_id = await self._submit_operation(kind="testcase.cases.export", status=OperationStatus.FAILED)

        cancel_result = await self.service.bulk_cancel_operations(
            actor=self.actor,
            command=BulkCancelOperationsCommand(operation_ids=(running_id, succeeded_id, "invalid-id")),
        )
        self.assertEqual(cancel_result.updated_count, 1)
        self.assertEqual(cancel_result.skipped_count, 1)
        self.assertEqual(cancel_result.updated[0].id, running_id)
        self.assertEqual(cancel_result.updated[0].status, OperationStatus.CANCELLED)

        archive_result = await self.service.bulk_archive_operations(
            actor=self.actor,
            command=BulkArchiveOperationsCommand(operation_ids=(running_id, succeeded_id, failed_id)),
        )
        self.assertEqual(archive_result.updated_count, 3)
        self.assertEqual(archive_result.skipped_count, 0)
        self.assertTrue(all(item.archived_at is not None for item in archive_result.updated))

        default_page = await self.service.list_operations(
            actor=self.actor,
            query=ListOperationsQuery(project_id=self.project_id),
        )
        self.assertEqual(default_page.total, 0)

        archived_page = await self.service.list_operations(
            actor=self.actor,
            query=ListOperationsQuery(
                project_id=self.project_id,
                archive_scope=OperationArchiveScope.ONLY,
            ),
        )
        self.assertEqual(archived_page.total, 3)

        filtered_page = await self.service.list_operations(
            actor=self.actor,
            query=ListOperationsQuery(
                project_id=self.project_id,
                archive_scope=OperationArchiveScope.ONLY,
                statuses=(OperationStatus.FAILED, OperationStatus.CANCELLED),
                kinds=("runtime.models.refresh", "testcase.cases.export"),
            ),
        )
        self.assertEqual(filtered_page.total, 2)
        self.assertEqual({item.id for item in filtered_page.items}, {running_id, failed_id})

        restore_result = await self.service.bulk_restore_operations(
            actor=self.actor,
            command=BulkRestoreOperationsCommand(operation_ids=(failed_id, "missing-id")),
        )
        self.assertEqual(restore_result.updated_count, 1)
        self.assertEqual(restore_result.skipped_count, 0)
        self.assertEqual(restore_result.updated[0].id, failed_id)
        self.assertIsNone(restore_result.updated[0].archived_at)

        include_page = await self.service.list_operations(
            actor=self.actor,
            query=ListOperationsQuery(
                project_id=self.project_id,
                archive_scope=OperationArchiveScope.INCLUDE,
            ),
        )
        self.assertEqual(include_page.total, 3)

        active_page = await self.service.list_operations(
            actor=self.actor,
            query=ListOperationsQuery(project_id=self.project_id),
        )
        self.assertEqual(active_page.total, 1)
        self.assertEqual(active_page.items[0].id, failed_id)


if __name__ == "__main__":
    unittest.main()
