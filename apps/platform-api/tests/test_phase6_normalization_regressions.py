from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.runtime_gateway.application.service import RuntimeGatewayService
from app.modules.testcase.application.service import TestcaseService


class RuntimeGatewayNormalizationRegressionTest(unittest.IsolatedAsyncioTestCase):
    def test_cold_import_identity_and_projects_sqlalchemy_modules(self) -> None:
        models_module = importlib.import_module("app.modules.identity.infra.sqlalchemy.models")
        repository_module = importlib.import_module(
            "app.modules.projects.infra.sqlalchemy.repository"
        )
        service_module = importlib.import_module("app.modules.runtime_gateway.application.service")

        self.assertIsNotNone(models_module)
        self.assertTrue(hasattr(repository_module, "SqlAlchemyProjectsRepository"))
        self.assertTrue(hasattr(service_module, "RuntimeGatewayService"))

    async def test_create_thread_promotes_graph_id_from_legacy_graph_metadata(self) -> None:
        upstream = SimpleNamespace(create_thread=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]

        payload = await service.create_thread(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                }
            },
        )

        self.assertEqual(payload, {"ok": True})
        upstream.create_thread.assert_awaited_once_with(
            {
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                    "project_id": "project-1",
                },
                "graph_id": "test_case_agent",
            }
        )

    async def test_thread_run_allows_legacy_graph_thread_without_graph_id(self) -> None:
        upstream = SimpleNamespace(stream_thread_run=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._load_thread = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "thread_id": "thread-1",
                "metadata": {
                    "project_id": "project-1",
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                },
            }
        )
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._inject_project_scope = lambda project_id, payload: payload or {}  # type: ignore[assignment]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

        payload = await service.stream_thread_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload={"assistant_id": "test_case_agent"},
        )

        self.assertEqual(payload, {"ok": True})
        service._assert_runtime_target_allowed.assert_awaited_once_with(
            project_id="project-1",
            assistant_id="test_case_agent",
            thread={
                "thread_id": "thread-1",
                "metadata": {
                    "project_id": "project-1",
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                },
            },
        )

    async def test_create_global_run_normalizes_assistant_id(self) -> None:
        upstream = SimpleNamespace(create_global_run=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._project_default_model_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        service._assert_runtime_target_allowed = AsyncMock()  # type: ignore[method-assign]

        payload = await service.create_global_run(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={"assistant_id": " assistant-1 "},
        )

        self.assertEqual(payload, {"ok": True})
        service._assert_runtime_target_allowed.assert_awaited_once_with(
            project_id="project-1",
            assistant_id="assistant-1",
        )

    async def test_cancel_runs_ignores_blank_thread_id(self) -> None:
        upstream = SimpleNamespace(cancel_runs=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._load_thread = AsyncMock()  # type: ignore[method-assign]

        payload = await service.cancel_runs(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={"thread_id": "   ", "status": "pending"},
        )

        self.assertEqual(payload, {"ok": True})
        service._load_thread.assert_not_called()


class TestcaseNormalizationRegressionTest(unittest.TestCase):
    def test_ensure_project_match_normalizes_project_id(self) -> None:
        service = TestcaseService(
            session_factory=None,
            upstream=SimpleNamespace(),
        )

        payload = service._ensure_project_match(
            {"project_id": " project-1 ", "id": "doc-1"},
            project_id="project-1",
            code="document_not_found",
        )

        self.assertEqual(payload["id"], "doc-1")


if __name__ == "__main__":
    unittest.main()
