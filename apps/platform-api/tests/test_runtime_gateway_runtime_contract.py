from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.errors import BadRequestError
from app.modules.runtime_gateway.application.service import RuntimeGatewayService


class RuntimeGatewayRuntimeContractTest(unittest.IsolatedAsyncioTestCase):
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
                    "project_id": "project-1",
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
                    "project_id": "project-1",
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
            send_thread_command=AsyncMock(return_value={"type": "success", "id": 11})
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"graph_id": "agent"}})  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value="project-default")  # type: ignore[method-assign]
        service._assert_runtime_options_allowed = AsyncMock()  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

        result = await service.send_thread_command(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload={
                "id": 11,
                "method": "run.start",
                "params": {
                    "assistant_id": "agent",
                    "input": {"messages": []},
                    "config": {"tools": ["utc_now"]},
                },
            },
        )

        self.assertEqual(result, {"type": "success", "id": 11})
        service._assert_runtime_options_allowed.assert_awaited_once_with(
            project_id="project-1",
            options={"model_id": "project-default", "tools": ["utc_now"]},
        )
        upstream.send_thread_command.assert_awaited_once_with(
            "thread-1",
            {
                "id": 11,
                "method": "run.start",
                "params": {
                    "assistant_id": "agent",
                    "input": {"messages": []},
                    "config": {
                        "configurable": {
                            "platform_runtime": {
                                "model_id": "project-default",
                                "tools": ["utc_now"],
                            }
                        }
                    },
                },
            },
        )

    async def test_v2_event_subscription_is_read_scoped_and_unchanged(self) -> None:
        stream = object()
        upstream = SimpleNamespace(stream_thread_events=AsyncMock(return_value=stream))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        payload = {"channels": ["messages", "values"], "since": 12}

        result = await service.stream_thread_events(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload=payload,
        )

        self.assertIs(result, stream)
        service._load_thread.assert_awaited_once_with(
            actor=unittest.mock.ANY,
            project_id="project-1",
            thread_id="thread-1",
            write=False,
        )
        upstream.stream_thread_events.assert_awaited_once_with("thread-1", payload)

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

        await service.send_thread_command(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload=payload,
        )

        upstream.send_thread_command.assert_awaited_once_with("thread-1", payload)

    async def test_create_global_run_injects_project_default_model(self) -> None:
        upstream = SimpleNamespace(create_global_run=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value="project-default")  # type: ignore[method-assign]
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
                    "project_id": "project-1",
                    "model_id": "project-default",
                },
            }
        )


if __name__ == "__main__":
    unittest.main()
