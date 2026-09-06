from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.core.errors import BadRequestError, ForbiddenError
from app.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
    _merge_runtime_context,
    _normalize_protocol_lifecycle_frame,
    _runtime_context_snapshot,
)


class RuntimeGatewayRuntimeContractTest(unittest.IsolatedAsyncioTestCase):
    def test_protocol_lifecycle_is_normalized_for_frontend_sdk(self) -> None:
        frame, terminal = _normalize_protocol_lifecycle_frame(
            b'data: {"seq":4,"method":"lifecycle","params":{"namespace":[],"data":{"event":"success","status":"success"},"run_id":"run-1"}}'
        )

        self.assertEqual(
            frame,
            b'data: {"seq":4,"method":"lifecycle","params":{"namespace":[],"data":{"event":"completed","status":"success"},"run_id":"run-1"}}',
        )
        self.assertEqual(terminal, {"run_id": "run-1", "status": "success"})

    def test_protocol_lifecycle_keeps_interrupt_active(self) -> None:
        _, terminal = _normalize_protocol_lifecycle_frame(
            b'data: {"method":"lifecycle","params":{"data":{"event":"interrupted","status":"interrupted"},"run_id":"run-1"}}'
        )

        self.assertIsNone(terminal)

    def test_context_hash_matches_runtime_context_v1_canonicalization(self) -> None:
        context_hash, snapshot = _runtime_context_snapshot(
            {
                "params": {
                    "context": {
                        "model_id": "model-1",
                        "temperature": 0.2,
                        "top_p": 1,
                        "max_tokens": 128,
                        "tools": ["search"],
                    },
                    "config": {
                        "configurable": {
                            "platform_runtime": {
                                "temperature": 0,
                                "tools": ["utc_now", "search"],
                            }
                        }
                    },
                }
            }
        )

        self.assertEqual(
            context_hash,
            "sha256:67b573b27851ae07ed231facfcccf00fe7450a6aab56541e4a9cc790da0c8864",
        )
        self.assertEqual(
            snapshot,
            {
                "model_id": "model-1",
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 128,
                "tools": ["search", "utc_now"],
            },
        )

    def test_runtime_context_precedence_is_explicit_then_agent_then_project(self) -> None:
        self.assertEqual(
            _merge_runtime_context(
                project_default_model="project:model",
                agent_defaults={"model_id": "agent:model", "temperature": 0.4},
                requested={"temperature": 0.8},
            ),
            {"model_id": "agent:model", "temperature": 0.8},
        )
        self.assertEqual(
            _merge_runtime_context(
                project_default_model="project:model",
                agent_defaults={},
                requested={},
            ),
            {"model_id": "project:model"},
        )

    async def test_thread_graph_target_does_not_allow_a_different_target(self) -> None:
        service = RuntimeGatewayService(session_factory=None, upstream=SimpleNamespace())
        service._assistant_belongs_project = AsyncMock(return_value=False)  # type: ignore[method-assign]
        thread = {"metadata": {"project_id": "project-1", "graph_id": "test_case_agent"}}

        await service._assert_runtime_target_allowed(
            project_id="project-1",
            assistant_id="test_case_agent",
            thread=thread,
        )
        with self.assertRaises(ForbiddenError) as denied:
            await service._assert_runtime_target_allowed(
                project_id="project-1",
                assistant_id="sql_agent",
                thread=thread,
            )

        self.assertEqual(denied.exception.code, "runtime_target_denied")

    async def test_agent_profile_defaults_are_filtered_before_runtime_context(self) -> None:
        class _Uow:
            async def __aenter__(self):
                return SimpleNamespace(session=object())

            async def __aexit__(self, exc_type, exc, tb):
                return None

        service = RuntimeGatewayService(session_factory=object(), upstream=SimpleNamespace())
        service._project_default_model_id = AsyncMock(return_value="project:model")  # type: ignore[method-assign]
        agent = SimpleNamespace(
            context={
                "model_id": "agent:model",
                "temperature": 0.4,
                "system_prompt": "must not cross the boundary",
                "project_id": "must not cross the boundary",
                "unknown": "must not cross the boundary",
            }
        )
        with (
            patch("app.modules.runtime_gateway.application.service.SqlAlchemyUnitOfWork", return_value=_Uow()),
            patch("app.modules.runtime_gateway.application.service.SqlAlchemyAssistantsRepository") as repository,
        ):
            repository.return_value.get_by_project_and_graph_id.return_value = agent
            result = await service._inject_project_default_model(
                project_id="00000000-0000-0000-0000-000000000001",
                payload={"assistant_id": "agent", "context": {"temperature": 0.8}},
            )

        self.assertEqual(
            result["context"],
            {"model_id": "agent:model", "temperature": 0.8},
        )

    def test_inject_project_scope_moves_runtime_fields_into_context(self) -> None:
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=SimpleNamespace(),
        )

        payload = service._inject_project_scope(
            project_id="project-1",
            payload={
                "project_id": "legacy-project",
                "context": {
                    "system_prompt": "context prompt",
                    "project_id": "legacy-project",
                    "user_id": "user-1",
                },
                "config": {
                    "recursion_limit": 12,
                    "model_id": "config-model",
                    "metadata": {
                        "request_origin": "workspace-ui",
                        "project_id": "legacy-project",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_id": "checkpoint-1",
                        "enable_tools": True,
                        "tools": ["utc_now"],
                        "project_id": "legacy-project",
                        "tenant_id": "tenant-1",
                    },
                },
                "metadata": {
                    "source": "chat",
                    "project_id": "legacy-project",
                },
            },
        )

        self.assertEqual(
            payload,
            {
                "context": {
                    "system_prompt": "context prompt",
                    "model_id": "config-model",
                    "enable_tools": True,
                    "tools": ["utc_now"],
                },
                "config": {
                    "recursion_limit": 12,
                    "metadata": {
                        "request_origin": "workspace-ui",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_id": "checkpoint-1",
                    },
                },
                "metadata": {
                    "source": "chat",
                },
            },
        )

    async def test_create_global_run_passes_normalized_runtime_payload_to_upstream(self) -> None:
        upstream = SimpleNamespace(create_global_run=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock()  # type: ignore[method-assign]
        service._validate_run_options = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_global_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={
                "assistant_id": " assistant-1 ",
                "context": {
                    "temperature": 0.2,
                    "project_id": "legacy-project",
                },
                "config": {
                    "model_id": "config-model",
                    "metadata": {
                        "request_origin": "workspace-ui",
                        "project_id": "legacy-project",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                        "enable_tools": True,
                        "tools": ["utc_now"],
                        "project_id": "legacy-project",
                    },
                },
                "metadata": {
                    "source": "chat",
                    "project_id": "legacy-project",
                },
            },
        )

        self.assertEqual(result, {"ok": True})
        service._assert_runtime_target_allowed.assert_awaited_once_with(
            project_id="project-1",
            assistant_id="assistant-1",
        )
        upstream.create_global_run.assert_awaited_once_with(
            {
                "assistant_id": " assistant-1 ",
                "context": {
                    "temperature": 0.2,
                    "model_id": "config-model",
                    "enable_tools": True,
                    "tools": ["utc_now"],
                },
                "config": {
                    "metadata": {
                        "request_origin": "workspace-ui",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                    },
                },
                "metadata": {
                    "source": "chat",
                },
            }
        )
        service._project_default_model_id.assert_not_awaited()

    async def test_v2_command_applies_policy_and_forwards_standard_envelope(self) -> None:
        upstream = SimpleNamespace(
            create_thread_run=AsyncMock(return_value={"run_id": "run-1"}),
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"graph_id": "agent"}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value="project-default")  # type: ignore[method-assign]
        service._assert_runtime_options_allowed = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]
        service._reserve_durable_run = AsyncMock(  # type: ignore[method-assign]
            return_value=SimpleNamespace(run_id=None, id="durable-1", operation_id="operation-1", thread_id="thread-1")
        )
        service._mark_durable_run_started = AsyncMock()  # type: ignore[method-assign]

        result = await service.send_thread_command(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            idempotency_key="request-1",
            payload={
                "id": 11,
                "method": "run.start",
                "params": {
                    "assistant_id": "agent",
                    "durability": "sync",
                    "stream_resumable": True,
                    "on_disconnect": "continue",
                    "input": {"messages": []},
                    "config": {"tools": ["utc_now"]},
                },
            },
        )

        self.assertEqual(
            result,
            {
                "type": "success",
                "id": 11,
                "result": {"run_id": "run-1", "thread_id": "thread-1"},
            },
        )
        service._assert_runtime_options_allowed.assert_awaited_once_with(
            project_id="project-1",
            options={"model_id": "project-default", "tools": ["utc_now"]},
        )
        upstream.create_thread_run.assert_awaited_once_with(
            "thread-1",
            {
                "assistant_id": "agent",
                "durability": "sync",
                "stream_resumable": True,
                "input": {"messages": []},
                "context": {
                    "model_id": "project-default",
                    "tools": ["utc_now"],
                },
            },
        )

    async def test_v2_event_subscription_normalizes_terminal_and_syncs_ledger(self) -> None:
        async def stream():
            yield b'data: {"method":"lifecycle","params":{"namespace":[],"data":{"event":"success","status":"success"},"run_id":"run-1"}}\n\n'

        upstream = SimpleNamespace(stream_thread_events=AsyncMock(return_value=stream()))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        service._sync_durable_run_terminal_state = AsyncMock()  # type: ignore[method-assign]
        payload = {"channels": ["messages", "values"], "since": 12}

        result = await service.stream_thread_events(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload=payload,
        )

        self.assertEqual(
            [chunk async for chunk in result],
            [
                b'data: {"method":"lifecycle","params":{"namespace":[],"data":{"event":"completed","status":"success"},"run_id":"run-1"}}\n\n'
            ],
        )
        service._load_thread.assert_awaited_once_with(
            actor=unittest.mock.ANY,
            project_id="project-1",
            thread_id="thread-1",
            write=False,
        )
        upstream.stream_thread_events.assert_awaited_once_with("thread-1", payload)
        service._sync_durable_run_terminal_state.assert_awaited_once_with(
            actor=unittest.mock.ANY,
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
            snapshot={"status": "success"},
        )

    async def test_v2_event_subscription_rejects_unknown_channels_before_upstream(self) -> None:
        upstream = SimpleNamespace(stream_thread_events=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.stream_thread_events(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                payload={"channels": ["debug", "custom:progress"]},
            )

        self.assertEqual(ctx.exception.code, "invalid_protocol_event_subscription")
        upstream.stream_thread_events.assert_not_awaited()

    async def test_join_stream_disconnect_never_cancels_run(self) -> None:
        upstream = SimpleNamespace(join_thread_run_stream=AsyncMock(return_value=object()))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        await service.join_thread_run_stream(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
            params={"stream_mode": "values"},
        )
        upstream.join_thread_run_stream.assert_awaited_once_with(
            "thread-1",
            "run-1",
            {"stream_mode": "values", "cancel_on_disconnect": False},
        )

    async def test_join_stream_rejects_disconnect_cancellation_before_upstream(self) -> None:
        upstream = SimpleNamespace(join_thread_run_stream=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.join_thread_run_stream(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                run_id="run-1",
                params={"cancel_on_disconnect": True},
            )

        self.assertEqual(ctx.exception.code, "cancel_on_disconnect_not_supported")
        upstream.join_thread_run_stream.assert_not_awaited()

    async def test_invalid_v2_command_does_not_reach_upstream(self) -> None:
        upstream = SimpleNamespace(send_thread_command=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.send_thread_command(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                payload={"id": "invalid", "method": "run.start", "params": {}},
            )

        self.assertEqual(ctx.exception.code, "invalid_protocol_command")
        upstream.send_thread_command.assert_not_awaited()

    async def test_run_launch_uses_context_bound_delegation_before_upstream(self) -> None:
        class _ScopedUpstream:
            def __init__(self, headers=None):
                self.headers = headers or {}
                self.create_thread_run = AsyncMock(return_value={"run_id": "run-1"})

            def with_forwarded_headers(self, headers):
                return _ScopedUpstream({**self.headers, **headers})

        upstream = _ScopedUpstream()
        factory = Mock(return_value={"authorization": "Bearer scoped"})
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
            delegation_headers_factory=factory,
        )
        service._reserve_durable_run = AsyncMock(  # type: ignore[method-assign]
            return_value=SimpleNamespace(
                run_id=None,
                id="durable-1",
                operation_id="operation-1",
                thread_id="thread-1",
                agent_key="reference_agent",
                idempotency_key="idem-1",
                status="submitted",
            )
        )
        service._mark_durable_run_started = AsyncMock()  # type: ignore[method-assign]

        _, result = await service.launch_runtime_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            command={
                "method": "run.start",
                "params": {
                    "assistant_id": "reference_agent",
                    "context": {"model_id": "model-1"},
                },
            },
            upstream_payload={"assistant_id": "reference_agent"},
            idempotency_key="idem-1",
        )

        self.assertEqual(result, {"run_id": "run-1"})
        factory.assert_called_once()
        self.assertEqual(factory.call_args.kwargs["agent_key"], "reference_agent")
        self.assertTrue(factory.call_args.kwargs["context_hash"].startswith("sha256:"))
        upstream.create_thread_run.assert_not_awaited()

    async def test_input_respond_preserves_protocol_payload(self) -> None:
        payload = {
            "id": 12,
            "method": "input.respond",
            "params": {
                "interrupt_id": "interrupt-1",
                "response": {"decision": "approve"},
            },
        }
        upstream = SimpleNamespace(
            send_thread_command=AsyncMock(return_value={"type": "success", "id": 12})
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._assert_active_interrupt = AsyncMock()  # type: ignore[method-assign]
        service._mark_interrupt_resolved = AsyncMock()  # type: ignore[method-assign]

        await service.send_thread_command(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload=payload,
        )

        upstream.send_thread_command.assert_awaited_once_with("thread-1", payload)
        service._assert_active_interrupt.assert_awaited_once_with(
            project_id="project-1",
            thread_id="thread-1",
            interrupt_id="interrupt-1",
        )
        service._mark_interrupt_resolved.assert_awaited_once_with(
            project_id="project-1",
            thread_id="thread-1",
            run_id=unittest.mock.ANY,
            interrupt_id="interrupt-1",
        )

    async def test_create_global_run_injects_project_default_model(self) -> None:
        upstream = SimpleNamespace(create_global_run=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value="project-default")  # type: ignore[method-assign]
        service._validate_run_options = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

        await service.create_global_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={"assistant_id": "assistant-1"},
        )

        upstream.create_global_run.assert_awaited_once_with(
            {
                "assistant_id": "assistant-1",
                "context": {
                    "model_id": "project-default",
                },
            }
        )

    async def test_standard_thread_run_uses_durable_reservation(self) -> None:
        upstream = SimpleNamespace(create_thread_run=AsyncMock(return_value={"run_id": "run-1"}))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"graph_id": "agent"}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._validate_run_options = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]
        service._reserve_durable_run = AsyncMock(  # type: ignore[method-assign]
            return_value=SimpleNamespace(
                run_id=None,
                status="submitted",
                id="durable-1",
                operation_id="operation-1",
                thread_id="thread-1",
                idempotency_key="standard:key",
            )
        )
        service._mark_durable_run_started = AsyncMock()  # type: ignore[method-assign]

        result = await service.create_thread_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload={"assistant_id": "agent", "input": {"messages": []}},
        )

        self.assertEqual(result, {"run_id": "run-1"})
        service._reserve_durable_run.assert_awaited_once()
        upstream.create_thread_run.assert_awaited_once()

    async def test_standard_thread_run_reuses_active_idempotent_result(self) -> None:
        upstream = SimpleNamespace(create_thread_run=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"graph_id": "agent"}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._validate_run_options = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]
        service._reserve_durable_run = AsyncMock(  # type: ignore[method-assign]
            return_value=SimpleNamespace(
                run_id="run-1",
                status="running",
                id="durable-1",
                operation_id="operation-1",
                thread_id="thread-1",
                idempotency_key="standard:key",
            )
        )

        result = await service.create_thread_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload={"assistant_id": "agent", "input": {"messages": []}},
        )

        self.assertEqual(result, {"run_id": "run-1", "thread_id": "thread-1"})
        upstream.create_thread_run.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
