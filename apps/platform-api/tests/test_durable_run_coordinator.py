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
from app.core.errors import ConflictError, ForbiddenError, UpstreamServiceError
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
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
        self.upstream = SimpleNamespace(
            send_thread_command=AsyncMock(
                return_value={"type": "success", "id": 1, "result": {"run_id": "run-1"}}
            ),
            get_thread_run=AsyncMock(return_value={"run_id": "run-1", "status": "success"}),
            get_thread_state=AsyncMock(
                return_value={"tasks": [{"interrupts": [{"id": "interrupt-1"}]}]}
            ),
            cancel_thread_run=AsyncMock(return_value={"status": "accepted"}),
        )
        self.service = RuntimeGatewayService(
            session_factory=self._session_factory,
            upstream=self.upstream,
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
