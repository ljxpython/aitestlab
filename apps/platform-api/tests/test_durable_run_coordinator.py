from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import ConflictError, ForbiddenError, UpstreamServiceError
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
from app.modules.operations.application.execution import OperationExecutorRegistry
from app.modules.operations.application.worker import OperationWorker
from app.modules.runtime_gateway.application.executor import RuntimeDurableRunReconciliationExecutor
from app.modules.runtime_gateway.application.service import RuntimeGatewayService
from app.modules.runtime_gateway.infra.sqlalchemy.repository import SqlAlchemyDurableRunsRepository


class DurableRunCoordinatorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "durable-runs.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.actor = ActorContext(user_id="user-1", subject="user-1")
        run_start = AsyncMock(return_value={"run_id": "run-1"})
        self.upstream = SimpleNamespace(
            create_thread_run=run_start,
            send_thread_command=run_start,
            get_thread_run=AsyncMock(return_value={"run_id": "run-1", "status": "success"}),
            get_thread_state=AsyncMock(
                return_value={"tasks": [{"interrupts": [{"id": "interrupt-1"}]}]}
            ),
            list_thread_runs=AsyncMock(return_value={"runs": []}),
            cancel_thread_run=AsyncMock(return_value={"status": "accepted"}),
        )
        self.dispatcher = SimpleNamespace(dispatch=AsyncMock())
        self.service = RuntimeGatewayService(
            session_factory=self._session_factory,
            upstream=self.upstream,
            operation_dispatcher=self.dispatcher,
        )
        self.service._load_thread = AsyncMock(return_value={"metadata": {"graph_id": "agent-1"}})  # type: ignore[method-assign]
        self.service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        self.service._assert_runtime_options_allowed = AsyncMock()  # type: ignore[method-assign]
        self.service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

    def tearDown(self) -> None:
        self._engine.dispose()
        self._tmpdir.cleanup()

    @staticmethod
    def _command(*, content: str = "hello") -> dict:
        return {
            "id": 1,
            "method": "run.start",
            "params": {
                "assistant_id": "agent-1",
                "input": {"messages": [{"type": "human", "content": content}]},
            },
        }

    async def test_same_key_reuses_run_without_resending_command(self) -> None:
        first = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        second = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        self.assertEqual(first["result"]["run_id"], "run-1")
        self.assertEqual(second["result"]["run_id"], "run-1")
        self.assertEqual(self.upstream.send_thread_command.await_count, 1)

    async def test_known_run_cannot_be_read_from_another_project(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        denied_service = RuntimeGatewayService(
            session_factory=self._session_factory,
            upstream=self.upstream,
        )
        denied_service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        with self.assertRaises(ForbiddenError) as denied:
            await denied_service.get_thread_run(
                actor=self.actor,
                project_id="project-2",
                thread_id="thread-1",
                run_id="run-1",
            )

        self.assertEqual(denied.exception.code, "run_project_denied")
        self.upstream.get_thread_run.assert_not_awaited()

    async def test_missing_project_role_is_rejected_before_thread_or_run_access(self) -> None:
        denied_service = RuntimeGatewayService(
            session_factory=None,
            upstream=SimpleNamespace(get_thread=AsyncMock(), send_thread_command=AsyncMock()),
        )

        with self.assertRaises(ForbiddenError) as denied:
            await denied_service.send_thread_command(
                actor=ActorContext(user_id="user-2", subject="user-2"),
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )

        self.assertEqual(denied.exception.code, "project_role_missing")
        denied_service._upstream.get_thread.assert_not_awaited()
        denied_service._upstream.send_thread_command.assert_not_awaited()

    async def test_key_conflict_and_second_active_run_are_rejected(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "running"}

        with self.assertRaises(ConflictError) as same_key:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(content="different"),
                idempotency_key="request-1",
            )
        with self.assertRaises(ConflictError) as active_run:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-2",
            )

        self.assertEqual(same_key.exception.code, "idempotency_key_conflict")
        self.assertEqual(active_run.exception.code, "thread_active_run_conflict")
        self.assertEqual(self.upstream.send_thread_command.await_count, 1)

    async def test_terminal_active_run_is_reconciled_before_a_new_run(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "success"}
        self.upstream.send_thread_command.return_value = {
            "type": "success",
            "id": 2,
            "result": {"run_id": "run-2"},
        }

        next_run = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(content="next"),
            idempotency_key="request-2",
        )

        self.assertEqual(next_run["result"]["run_id"], "run-2")
        self.upstream.get_thread_run.assert_awaited_once_with("thread-1", "run-1")
        with self._session_factory() as session:
            prior_run = SqlAlchemyDurableRunsRepository(session).get_by_run_id(
                project_id="project-1",
                thread_id="thread-1",
                run_id="run-1",
            )
        self.assertEqual(prior_run.status, "succeeded")  # type: ignore[union-attr]

    async def test_missing_run_id_keeps_thread_reserved_for_reconciliation(self) -> None:
        self.upstream.send_thread_command.return_value = {"type": "success", "id": 1, "result": {}}

        with self.assertRaises(UpstreamServiceError) as missing_run_id:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )
        with self.assertRaises(ConflictError) as retry:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )

        self.assertEqual(missing_run_id.exception.code, "protocol_run_id_missing")
        self.assertEqual(retry.exception.code, "run_start_in_progress")
        self.assertEqual(self.upstream.send_thread_command.await_count, 1)

    async def test_timeout_reconciles_by_idempotency_marker_without_duplicate_create(self) -> None:
        self.upstream.create_thread_run.side_effect = UpstreamServiceError(
            code="langgraph_upstream_timeout",
            message="upstream timed out",
            upstream="langgraph",
        )
        self.upstream.list_thread_runs.return_value = {
            "runs": [
                {
                    "run_id": "run-after-timeout",
                    "metadata": {"platform_idempotency_key": "request-1"},
                }
            ]
        }

        with self.assertRaises(UpstreamServiceError) as unknown:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )
        self.assertEqual(unknown.exception.code, "run_start_unknown")

        reconciled = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        self.assertEqual(reconciled["result"]["run_id"], "run-after-timeout")
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)
        self.dispatcher.dispatch.assert_awaited_once()
        self.upstream.list_thread_runs.assert_awaited_once_with(
            "thread-1",
            {"limit": 100},
        )

    async def test_reconciliation_worker_retries_and_fails_after_three_attempts(self) -> None:
        self.upstream.create_thread_run.side_effect = UpstreamServiceError(
            code="langgraph_upstream_timeout",
            message="upstream timed out",
            upstream="langgraph",
        )
        self.upstream.list_thread_runs.return_value = {"runs": []}

        with self.assertRaises(UpstreamServiceError):
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )

        worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry(
                (RuntimeDurableRunReconciliationExecutor(service=self.service),)
            ),
        )
        self.assertTrue(await worker.run_once())
        self.assertTrue(await worker.run_once())
        self.assertTrue(await worker.run_once())

        async with SqlAlchemyUnitOfWork(self._session_factory) as uow:
            operation = SqlAlchemyOperationsRepository(uow.session).list_operations(
                project_id="project-1",
                kind="runtime.durable_run",
                kinds=(),
                status=None,
                statuses=(),
                requested_by=None,
                archive_scope="exclude",
                limit=10,
                offset=0,
            )[0][0]
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_operation_id(
                operation.id
            )
        self.assertEqual(operation.status.value, "failed")
        self.assertEqual(durable_run.status, "failed")
        self.assertFalse(durable_run.active)
        self.assertEqual(self.upstream.list_thread_runs.await_count, 3)

    async def test_reconciliation_worker_associates_marker_without_duplicate_create(self) -> None:
        self.upstream.create_thread_run.side_effect = UpstreamServiceError(
            code="langgraph_upstream_timeout",
            message="upstream timed out",
            upstream="langgraph",
        )
        self.upstream.list_thread_runs.return_value = {
            "runs": [
                {
                    "run_id": "run-after-timeout",
                    "metadata": {"platform_idempotency_key": "request-1"},
                }
            ]
        }

        with self.assertRaises(UpstreamServiceError):
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="request-1",
            )

        executor = RuntimeDurableRunReconciliationExecutor(service=self.service)
        registry = OperationExecutorRegistry((executor,))
        self.assertIs(registry.get("runtime.durable_run"), executor)
        worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=registry,
        )

        self.assertTrue(await worker.run_once())

        async with SqlAlchemyUnitOfWork(self._session_factory) as uow:
            operation = SqlAlchemyOperationsRepository(uow.session).list_operations(
                project_id="project-1",
                kind="runtime.durable_run",
                kinds=(),
                status=None,
                statuses=(),
                requested_by=None,
                archive_scope="exclude",
                limit=10,
                offset=0,
            )[0][0]
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_operation_id(
                operation.id
            )
        self.assertEqual(operation.status.value, "succeeded")
        self.assertEqual(durable_run.run_id, "run-after-timeout")
        self.assertEqual(durable_run.status, "running")
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)
        self.assertEqual(self.upstream.list_thread_runs.await_count, 1)

    async def test_terminal_snapshot_releases_active_thread_slot(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        snapshot = await self.service.get_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
        )
        self.upstream.send_thread_command.return_value = {
            "type": "success",
            "id": 1,
            "result": {"run_id": "run-2"},
        }
        next_run = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(content="next"),
            idempotency_key="request-2",
        )

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(next_run["result"]["run_id"], "run-2")

    async def test_terminal_snapshot_aliases_reconcile_operation(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "succeeded"}

        await self.service.get_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
        )

        with self._session_factory() as session:
            durable_run = SqlAlchemyDurableRunsRepository(session).get_by_run_id(
                project_id="project-1",
                thread_id="thread-1",
                run_id="run-1",
            )
            operation = SqlAlchemyOperationsRepository(session).get_by_id(durable_run.operation_id)  # type: ignore[union-attr]
        self.assertEqual(durable_run.status, "succeeded")  # type: ignore[union-attr]
        self.assertEqual(operation.status.value, "succeeded")  # type: ignore[union-attr]

    async def test_input_respond_requires_an_interrupt_from_the_active_run(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        response = {
            "id": 2,
            "method": "input.respond",
            "params": {"interrupt_id": "interrupt-1", "response": {"decision": "approve"}},
        }

        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=response,
        )
        self.upstream.send_thread_command.assert_awaited_with("thread-1", response)

        with self.assertRaises(ConflictError) as missing:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload={
                    **response,
                    "params": {"interrupt_id": "interrupt-2", "response": {"decision": "approve"}},
                },
            )
        self.assertEqual(missing.exception.code, "interrupt_not_active")

    async def test_input_respond_persists_exact_interrupt_mapping_and_rejects_replay(self) -> None:
        self.upstream.get_thread_state.return_value = {
            "tasks": [
                {
                    "interrupts": [
                        {"id": "interrupt-1"},
                        {"id": "interrupt-2"},
                    ]
                }
            ]
        }
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        response = {
            "id": 2,
            "method": "input.respond",
            "params": {"interrupt_id": "interrupt-2", "response": {"decision": "approve"}},
        }
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=response,
        )

        with self._session_factory() as session:
            runs = SqlAlchemyDurableRunsRepository(session)
            self.assertFalse(
                runs.is_interrupt_active(
                    project_id="project-1",
                    thread_id="thread-1",
                    run_id="run-1",
                    interrupt_id="interrupt-2",
                )
            )
            self.assertTrue(
                runs.is_interrupt_active(
                    project_id="project-1",
                    thread_id="thread-1",
                    run_id="run-1",
                    interrupt_id="interrupt-1",
                )
            )

        with self.assertRaises(ConflictError) as replay:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=response,
            )
        self.assertEqual(replay.exception.code, "interrupt_not_active")

    async def test_input_respond_accepts_graphharbor_top_level_interrupts(self) -> None:
        self.upstream.get_thread_state.return_value = {
            "interrupts": [{"id": "interrupt-1", "value": {"kind": "approval"}}]
        }
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        response = {
            "id": 2,
            "method": "input.respond",
            "params": {"interrupt_id": "interrupt-1", "response": "approve"},
        }
        result = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=response,
        )

        self.assertEqual(result["run_id"], "run-1")
        self.upstream.send_thread_command.assert_awaited_with("thread-1", response)

    async def test_interrupted_run_stays_active_and_resume_replaces_upstream_run_id(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "interrupted"}
        await self.service.get_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
        )

        self.upstream.send_thread_command.return_value = {
            "type": "success",
            "id": 2,
            "result": {"run_id": "run-2"},
        }
        result = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload={
                "id": 2,
                "method": "input.respond",
                "params": {"interrupt_id": "interrupt-1", "response": "approve"},
            },
        )

        self.assertEqual(result["result"]["run_id"], "run-2")
        with self._session_factory() as session:
            active = SqlAlchemyDurableRunsRepository(session).get_active(
                project_id="project-1", thread_id="thread-1"
            )
        self.assertIsNotNone(active)
        self.assertEqual(active.run_id, "run-2")  # type: ignore[union-attr]

        with self.assertRaises(ConflictError) as duplicate:
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(content="next"),
                idempotency_key="request-2",
            )
        self.assertEqual(duplicate.exception.code, "thread_active_run_conflict")

    async def test_cancel_keeps_run_active_until_terminal_snapshot(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(),
            idempotency_key="request-1",
        )

        result = await self.service.cancel_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
            payload=None,
        )

        with self._session_factory() as session:
            durable_run = SqlAlchemyDurableRunsRepository(session).get_by_run_id(
                project_id="project-1",
                thread_id="thread-1",
                run_id="run-1",
            )
            operation = SqlAlchemyOperationsRepository(session).get_by_id(durable_run.operation_id)  # type: ignore[union-attr]
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(durable_run.active)  # type: ignore[union-attr]
        self.assertIsNotNone(operation.cancel_requested_at)  # type: ignore[union-attr]

        with self.assertRaises(ConflictError):
            await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(content="next"),
                idempotency_key="request-2",
            )

        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "cancelled"}
        await self.service.get_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
        )
        self.upstream.send_thread_command.return_value = {
            "type": "success",
            "id": 1,
            "result": {"run_id": "run-2"},
        }
        next_run = await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(content="next"),
            idempotency_key="request-2",
        )
        self.assertEqual(next_run["result"]["run_id"], "run-2")

    async def test_run_lifecycle_audit_excludes_complete_input(self) -> None:
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(content="do-not-store-this-full-message"),
            idempotency_key="request-1",
        )
        await self.service.cancel_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
            payload=None,
        )
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "cancelled"}
        await self.service.get_thread_run(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
        )

        with self._session_factory() as session:
            events = session.scalars(
                select(AuditLogRecord)
                .where(AuditLogRecord.project_id == "project-1")
                .order_by(AuditLogRecord.created_at, AuditLogRecord.id)
            ).all()

        self.assertEqual(
            {event.action for event in events},
            {
                "runtime.run.submitted",
                "runtime.run.started",
                "runtime.run.cancel_requested",
                "runtime.run.cancelled",
            },
        )
        self.assertTrue(all(event.target_type == "operation" for event in events))
        self.assertTrue(all(event.project_id == "project-1" for event in events))
        self.assertNotIn(
            "do-not-store-this-full-message",
            json.dumps([event.metadata_json for event in events]),
        )


if __name__ == "__main__":
    unittest.main()
