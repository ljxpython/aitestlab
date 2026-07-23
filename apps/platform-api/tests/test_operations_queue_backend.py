from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.modules.operations.application import CreateOperationCommand, OperationsService
from app.modules.operations.application.execution import OperationExecutorRegistry
from app.modules.operations.application.execution import actor_from_operation
from app.modules.operations.application.ports import OperationExecutionResult, StoredOperation
from app.modules.operations.application.worker import OperationWorker
from app.modules.operations.domain import OperationStatus
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class _InMemoryQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self.dispatched_ids: list[str] = []

    async def dispatch(self, *, operation: StoredOperation) -> None:
        self.dispatched_ids.append(operation.id)
        await self._queue.put(operation.id)

    async def dequeue(self, *, timeout_seconds: float) -> str | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout_seconds)
        except TimeoutError:
            return None


class _FlakyQueueExecutor:
    kind = "queue.flaky"

    def __init__(self) -> None:
        self.attempts = 0

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("queue-backend-first-attempt-failed")
        return OperationExecutionResult(
            result_payload={
                "attempt": self.attempts,
                "project_id": operation.project_id,
            }
        )


class OperationsQueueBackendTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "operations-queue-backend.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.project_id = self._create_project()
        self.actor = ActorContext(
            user_id=str(uuid4()),
            platform_roles=("platform_super_admin",),
            project_roles={self.project_id: ("project_admin",)},
        )
        self.queue = _InMemoryQueue()
        self.service = OperationsService(
            session_factory=self._session_factory,
            dispatcher=self.queue,  # type: ignore[arg-type]
        )
        self.executor = _FlakyQueueExecutor()
        self.worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry((self.executor,)),
            dispatcher=self.queue,  # type: ignore[arg-type]
            queue_consumer=self.queue,  # type: ignore[arg-type]
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
                name="Operations Queue Project",
                description="phase-4 redis queue boundary test",
            )
            return str(project.id)

    async def test_queue_dispatch_and_retry_requeue_flow(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="queue.flaky",
                project_id=self.project_id,
                input_payload={"value": "queued"},
                metadata={"_retry_policy": {"max_attempts": 2}},
            ),
        )

        self.assertNotIn("actor_snapshot", submitted.metadata)
        with session_scope(self._session_factory) as session:
            from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository

            stored = SqlAlchemyOperationsRepository(session).get_by_id(submitted.id)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertIn("actor_snapshot", stored.metadata)
            self.assertEqual(actor_from_operation(stored).user_id, self.actor.user_id)

        self.assertEqual(self.queue.dispatched_ids, [submitted.id])

        first_processed = await self.worker.run_once()
        first_state = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)
        second_processed = await self.worker.run_once()
        final_state = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(first_processed)
        self.assertTrue(second_processed)
        self.assertEqual(first_state.status, OperationStatus.SUBMITTED)
        self.assertEqual(final_state.status, OperationStatus.SUCCEEDED)
        self.assertEqual(final_state.result_payload["attempt"], 2)
        self.assertEqual(self.queue.dispatched_ids, [submitted.id, submitted.id])


if __name__ == "__main__":
    unittest.main()
