from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
