from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from contextlib import suppress
from uuid import UUID

import httpx
import uvicorn

from app.factory import create_app
from app.core.context.models import ActorContext
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.modules.operations.application import CreateOperationCommand, ListOperationsQuery, OperationsService
from app.modules.operations.application.execution import DatabasePollingOperationDispatcher, OperationExecutorRegistry
from app.modules.operations.application.ports import OperationExecutionResult, StoredOperation
from app.modules.operations.application.service import build_operation_page_signature
from app.modules.operations.application.worker import OperationWorker
from app.modules.operations.domain import OperationPage, OperationStatus
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.iam.domain import ProjectRole
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class _FlakyExecutor:
    kind = "unstable.echo"

    def __init__(self, *, succeed_on_attempt: int) -> None:
        self._attempt = 0
        self._succeed_on_attempt = succeed_on_attempt

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        self._attempt += 1
        if self._attempt < self._succeed_on_attempt:
            raise RuntimeError(f"flaky-attempt-{self._attempt}")
        return OperationExecutionResult(
            result_payload={
                "echo": operation.input_payload.get("value"),
                "attempt": self._attempt,
            }
        )


class OperationsStreamingAndRetryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "operations-streaming-and-retry.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.project_id = self._create_project()
        self.user_id = self._create_user()
        self.actor = ActorContext(
            user_id=self.user_id,
            platform_roles=("platform_super_admin",),
            project_roles={self.project_id: ("project_admin",)},
        )
        self.executor = _FlakyExecutor(succeed_on_attempt=3)
        self.service = OperationsService(
            session_factory=self._session_factory,
            dispatcher=DatabasePollingOperationDispatcher(),
        )
        self.worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry((self.executor,)),
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
                name="Operations Streaming Project",
                description="phase-4 operation streaming test",
            )
            return str(project.id)

    def _create_user(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username="stream-admin",
                password_hash=hash_password("admin123456"),
                external_subject="stream-admin",
                email=None,
                is_super_admin=True,
            )
            SqlAlchemyProjectsRepository(session).upsert_project_member(
                project_id=UUID(self.project_id),
                user_id=user.id,
                role=ProjectRole.ADMIN,
            )
            return str(user.id)

    async def test_worker_retries_until_retry_policy_exhausted_or_succeeds(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="unstable.echo",
                project_id=self.project_id,
                input_payload={"value": "ping"},
                metadata={"_retry_policy": {"max_attempts": 3}},
            ),
        )

        first_processed = await self.worker.run_once()
        first_state = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)
        second_processed = await self.worker.run_once()
        second_state = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)
        third_processed = await self.worker.run_once()
        final_state = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(first_processed)
        self.assertTrue(second_processed)
        self.assertTrue(third_processed)
        self.assertEqual(first_state.status, OperationStatus.SUBMITTED)
        self.assertEqual(second_state.status, OperationStatus.SUBMITTED)
        self.assertEqual(final_state.status, OperationStatus.SUCCEEDED)
        self.assertEqual(final_state.result_payload["echo"], "ping")
        self.assertEqual(final_state.result_payload["attempt"], 3)
        self.assertEqual(first_state.metadata["_execution"]["attempts"], 1)
        self.assertEqual(first_state.metadata["_execution"]["retry_count"], 1)
        self.assertEqual(second_state.metadata["_execution"]["attempts"], 2)
        self.assertEqual(second_state.metadata["_execution"]["retry_count"], 2)
        self.assertEqual(final_state.metadata["_execution"]["attempts"], 3)

    async def test_watch_operations_emits_page_after_change(self) -> None:
        query = ListOperationsQuery(project_id=self.project_id, limit=20, offset=0)
        initial_page = await self.service.list_operations(actor=self.actor, query=query)
        self.assertEqual(initial_page.total, 0)

        watch_stream = self.service.watch_operations(
            actor=self.actor,
            query=query,
            poll_interval_seconds=0.01,
            heartbeat_interval_seconds=1.0,
            initial_signature=build_operation_page_signature(initial_page),
        )

        async def submit_later() -> None:
            await asyncio.sleep(0.05)
            await self.service.submit_operation(
                actor=self.actor,
                command=CreateOperationCommand(
                    kind="unstable.echo",
                    project_id=self.project_id,
                    input_payload={"value": "watch"},
                ),
            )

        submit_task = asyncio.create_task(submit_later())
        next_page = await asyncio.wait_for(anext(watch_stream), timeout=0.5)
        await watch_stream.aclose()
        await submit_task

        assert isinstance(next_page, OperationPage)
        self.assertEqual(next_page.total, 1)
        self.assertEqual(next_page.items[0].status, OperationStatus.SUBMITTED)

    async def test_operations_stream_endpoint_emits_initial_page_event(self) -> None:
        app = create_app()
        app.state.settings.platform_db_enabled = True
        app.state.settings.platform_db_auto_create = False
        app.state.settings.database_url = str(self._engine.url)
        app.state.settings.bootstrap_admin_enabled = False
        access_token = create_access_token(
            user_id=self.user_id,
            username="stream-admin",
            settings=app.state.settings,
        )
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=0,
            log_level="error",
            lifespan="on",
        )
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())

        base_url = ""
        try:
            for _ in range(100):
                if server.started and getattr(server, "servers", None):
                    sockets = server.servers[0].sockets if server.servers else []
                    if sockets:
                        host, port = sockets[0].getsockname()[:2]
                        base_url = f"http://{host}:{port}"
                        break
                await asyncio.sleep(0.05)

            self.assertTrue(base_url, "uvicorn test server did not start in time")

            async with httpx.AsyncClient(base_url=base_url, timeout=2.0) as client:
                async with client.stream(
                    "GET",
                    "/api/operations/stream",
                    params={
                        "project_id": self.project_id,
                        "limit": 20,
                        "offset": 0,
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "text/event-stream",
                    },
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        response.headers.get("content-type"),
                        "text/event-stream; charset=utf-8",
                    )
                    chunks: list[str] = []
                    async for chunk in response.aiter_text():
                        if chunk:
                            chunks.append(chunk)
                        if "event: page" in "".join(chunks):
                            break

                body = "".join(chunks)
                self.assertIn("event: page", body)
                self.assertIn("\"items\"", body)
        finally:
            server.should_exit = True
            with suppress(asyncio.CancelledError):
                await asyncio.wait_for(server_task, timeout=5)


if __name__ == "__main__":
    unittest.main()
