from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.modules.assistants.application.service import (
    _normalize_assistant_runtime_contract,
)
from app.modules.assistants.application.contracts import CreateAssistantCommand


class AssistantsRuntimeContractTest(unittest.TestCase):
    def test_agent_create_rejects_legacy_execution_id(self) -> None:
        with self.assertRaises(ValidationError):
            CreateAssistantCommand(
                graph_id="agent",
                name="Agent",
                assistant_id="legacy-upstream-id",
            )

    def test_normalize_assistant_runtime_contract_moves_runtime_fields_into_context(self) -> None:
        config, context, metadata = _normalize_assistant_runtime_contract(
            project_id="project-1",
            config={
                "recursion_limit": 12,
                "model_id": "config-model",
                "configurable": {
                    "thread_id": "thread-1",
                    "enable_tools": True,
                    "tools": ["utc_now"],
                },
                "metadata": {
                    "trace": "assistant-edit",
                    "project_id": "legacy-project",
                },
            },
            context={
                "system_prompt": "context prompt",
            },
            metadata={
                "source": "workspace",
                "projectId": "legacy-project",
            },
        )

        self.assertEqual(
            config,
            {
                "recursion_limit": 12,
                "configurable": {"thread_id": "thread-1"},
                "metadata": {"trace": "assistant-edit"},
            },
        )
        self.assertEqual(
            context,
            {
                "system_prompt": "context prompt",
                "model_id": "config-model",
                "enable_tools": True,
                "tools": ["utc_now"],
            },
        )
        self.assertEqual(metadata, {"source": "workspace"})

    def test_normalize_assistant_runtime_contract_strips_trusted_context_fields(self) -> None:
        config, context, metadata = _normalize_assistant_runtime_contract(
            project_id="project-1",
            config={
                "configurable": {
                    "project_id": "legacy-project",
                    "projectId": "legacy-project-2",
                }
            },
            context={
                "user_id": "user-1",
                "tenant_id": "tenant-1",
                "project_id": "legacy-project",
                "role": "admin",
                "permissions": ["write"],
            },
            metadata={},
        )

        self.assertEqual(config, {})
        self.assertEqual(context, {})
        self.assertEqual(metadata, {})

    def test_normalize_assistant_runtime_contract_prefers_explicit_context_over_legacy_config(self) -> None:
        config, context, metadata = _normalize_assistant_runtime_contract(
            project_id="project-1",
            config={
                "temperature": 0.9,
                "configurable": {
                    "temperature": 0.8,
                    "max_tokens": 4096,
                },
            },
            context={
                "temperature": 0.2,
            },
            metadata={},
        )

        self.assertEqual(config, {})
        self.assertEqual(
            context,
            {
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        )
        self.assertEqual(metadata, {})


if __name__ == "__main__":
    unittest.main()
