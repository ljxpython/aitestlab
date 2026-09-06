from __future__ import annotations

import unittest
from pathlib import Path

from app.adapters.langgraph.parameter_schema import GraphParameterSchemaProvider
from app.core.config import Settings


def _runtime_service_root() -> Path:
    return Path(__file__).resolve().parents[2] / "runtime-service" / "runtime_service"


def _section_map(schema: dict) -> dict[str, dict]:
    sections = schema.get("sections")
    if not isinstance(sections, list):
        return {}
    result: dict[str, dict] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = section.get("key")
        if isinstance(key, str) and key:
            result[key] = section
    return result


class GraphParameterSchemaProviderTest(unittest.TestCase):
    def test_build_schema_uses_runtime_contract_v2_sections(self) -> None:
        settings = Settings(
            langgraph_graph_source_root=str(_runtime_service_root()),
        )
        provider = GraphParameterSchemaProvider(settings)

        schema = provider.build_schema("reference_agent")
        sections = _section_map(schema)

        self.assertEqual(schema["graph_id"], "reference_agent")
        self.assertEqual(schema["schema_version"], "dynamic-v2")
        self.assertTrue(schema["dynamic"])
        self.assertEqual(list(sections.keys()), ["config", "context", "configurable"])

    def test_build_schema_separates_trusted_context_and_runtime_options(self) -> None:
        settings = Settings(
            langgraph_graph_source_root=str(_runtime_service_root()),
        )
        provider = GraphParameterSchemaProvider(settings)

        schema = provider.build_schema("reference_agent")
        sections = _section_map(schema)
        config_properties = sections["config"]["properties"]
        context_properties = sections["context"]["properties"]
        platform_runtime = sections["configurable"]["properties"]["platform_runtime"]
        runtime_option_properties = platform_runtime["properties"]

        self.assertIn("recursion_limit", config_properties)
        self.assertIn("run_name", config_properties)
        self.assertNotIn("model_id", config_properties)
        self.assertNotIn("system_prompt", config_properties)
        self.assertNotIn("enable_local_tools", config_properties)
        self.assertNotIn("local_tools", config_properties)
        self.assertNotIn("enable_local_mcp", config_properties)
        self.assertNotIn("mcp_servers", config_properties)

        for key in ("model_id", "temperature", "max_tokens", "top_p", "tools"):
            self.assertIn(key, context_properties)

        for key in ("model_id", "temperature", "max_tokens", "top_p", "tools"):
            self.assertIn(key, context_properties)
            self.assertIn(key, runtime_option_properties)

        for key in ("system_prompt", "enable_tools"):
            self.assertNotIn(key, context_properties)
            self.assertIn(key, runtime_option_properties)

        self.assertEqual(
            sections["context"]["readonly_keys"],
            ["user_id", "tenant_id", "role", "permissions", "project_id"],
        )

    def test_build_schema_exposes_platform_and_service_private_configurable_fields(self) -> None:
        settings = Settings(
            langgraph_graph_source_root=str(_runtime_service_root()),
        )
        provider = GraphParameterSchemaProvider(settings)

        schema = provider.build_schema("reference_agent")
        sections = _section_map(schema)
        configurable_properties = sections["configurable"]["properties"]

        for key in (
            "thread_id",
            "checkpoint_id",
            "assistant_id",
            "graph_id",
            "platform_runtime",
        ):
            self.assertIn(key, configurable_properties)

        self.assertNotIn("__pregel_scratchpad", configurable_properties)
        self.assertNotIn("langgraph_auth_user", configurable_properties)
        self.assertNotIn("_runtime_model", configurable_properties)

    def test_fallback_schema_keeps_new_contract_shape(self) -> None:
        settings = Settings(
            langgraph_graph_source_root=str(_runtime_service_root()),
        )
        provider = GraphParameterSchemaProvider(settings)

        schema = provider.build_schema("graph-does-not-exist")
        sections = _section_map(schema)

        self.assertEqual(schema["schema_version"], "fallback-v2")
        self.assertFalse(schema["dynamic"])
        self.assertEqual(list(sections.keys()), ["config", "context", "configurable"])
        self.assertIn("project_id", sections["context"]["properties"])
        self.assertNotIn("temperature", sections["context"]["properties"])
        runtime_options = sections["configurable"]["properties"]["platform_runtime"]
        self.assertIn("temperature", runtime_options["properties"])
        self.assertIn("max_tokens", runtime_options["properties"])
        self.assertIn("top_p", runtime_options["properties"])
        self.assertEqual(
            sections["context"]["readonly_keys"],
            ["user_id", "tenant_id", "role", "permissions", "project_id"],
        )
