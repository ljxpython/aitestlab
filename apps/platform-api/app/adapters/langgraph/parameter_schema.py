from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.runtime_contract import (
    RUNTIME_CONTEXT_READONLY_KEYS,
    build_execution_config_schema_properties,
    build_runtime_context_schema_properties,
    build_runtime_options_schema_properties,
)

_CONFIGURABLE_PLATFORM_PROPERTIES: dict[str, dict[str, Any]] = {
    "thread_id": {"type": "string", "required": False},
    "checkpoint_id": {"type": "string", "required": False},
    "assistant_id": {"type": "string", "required": False},
    "graph_id": {"type": "string", "required": False},
    "platform_runtime": {
        "type": "object",
        "required": False,
        "properties": build_runtime_options_schema_properties(),
    },
}

_CONFIGURABLE_NOISE_KEYS = {
    "__pregel_scratchpad",
    "langgraph_auth_user",
}


class GraphParameterSchemaProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_schema(self, graph_id: str) -> dict[str, Any]:
        root = self._discover_graph_source_root()
        if root is None:
            return self._fallback_schema(graph_id, reason="graph_source_not_found")

        graph_config_path = root / "langgraph.json"
        graph_entry_file = self._resolve_graph_entry_file(graph_config_path, graph_id)
        if graph_entry_file is None:
            return self._fallback_schema(graph_id, reason="graph_entry_not_found")

        runtime_context_file = next(
            (
                candidate
                for candidate in (
                    root / "runtime" / "context.py",
                    root / "src" / "runtime_service" / "runtime" / "contracts.py",
                )
                if candidate.exists()
            ),
            root / "runtime" / "context.py",
        )
        config_properties = self._execution_config_properties()
        context_properties = self._extract_context_properties(runtime_context_file)
        configurable_properties = self._extract_configurable_properties(graph_entry_file)

        return {
            "graph_id": graph_id,
            "schema_version": "dynamic-v2",
            "dynamic": True,
            "sources": {
                "root": str(root),
                "langgraph_json": str(graph_config_path),
                "graph_entry": str(graph_entry_file),
                "runtime_context": str(runtime_context_file),
            },
            "sections": [
                {
                    "key": "config",
                    "title": "Execution Config",
                    "type": "object",
                    "required": False,
                    "properties": config_properties,
                },
                {
                    "key": "context",
                    "title": "Runtime Context",
                    "type": "object",
                    "required": False,
                    "properties": context_properties,
                    "readonly_keys": list(RUNTIME_CONTEXT_READONLY_KEYS),
                },
                {
                    "key": "configurable",
                    "title": "Platform / Private Configurable",
                    "type": "object",
                    "required": False,
                    "properties": configurable_properties,
                },
            ],
        }

    def _discover_graph_source_root(self) -> Path | None:
        explicit = self._settings.langgraph_graph_source_root
        candidates: list[Path] = []
        if isinstance(explicit, str) and explicit.strip():
            explicit_path = Path(explicit.strip()).expanduser()
            candidates.append(explicit_path)
            if not (explicit_path / "langgraph.json").exists():
                candidates.append(explicit_path.parent)

        repo_root = Path(__file__).resolve().parents[5]
        candidates.extend(
            [
                repo_root / "apps" / "runtime-service" / "runtime_service",
                repo_root / "apps" / "runtime-service",
            ]
        )

        for path in candidates:
            resolved = path.resolve()
            if resolved.exists() and (resolved / "langgraph.json").exists():
                return resolved
        return None

    def _resolve_graph_entry_file(
        self,
        graph_config_path: Path,
        graph_id: str,
    ) -> Path | None:
        if not graph_config_path.exists():
            return None
        try:
            payload = json.loads(graph_config_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        graphs = payload.get("graphs")
        if not isinstance(graphs, dict):
            return None

        raw_target = graphs.get(graph_id)
        if isinstance(raw_target, dict):
            raw_target = raw_target.get("path")
        if not isinstance(raw_target, str) or not raw_target.strip():
            return None

        relative_file = raw_target.split(":", 1)[0].strip()
        if not relative_file:
            return None

        normalized = relative_file[2:] if relative_file.startswith("./") else relative_file
        candidate_roots = [graph_config_path.parent, graph_config_path.parent.parent]
        for root in candidate_roots:
            file_path = (root / normalized).resolve()
            if file_path.exists() and file_path.is_file():
                return file_path
        return None

    def _execution_config_properties(self) -> dict[str, dict[str, Any]]:
        return build_execution_config_schema_properties()

    def _extract_context_properties(
        self,
        context_file: Path,
    ) -> dict[str, dict[str, Any]]:
        defaults: dict[str, dict[str, Any]] = {}
        if context_file.exists():
            try:
                context_tree = ast.parse(context_file.read_text(encoding="utf-8"))
                context_fields = self._extract_dataclass_fields(
                    context_tree,
                    "RuntimeContext",
                )
                for key, annotation in context_fields.items():
                    defaults[key] = {
                        "type": self._annotation_to_schema_type(annotation),
                        "required": False,
                    }
            except Exception:
                return build_runtime_context_schema_properties()
        return defaults

    def _extract_configurable_properties(
        self,
        graph_entry_file: Path,
    ) -> dict[str, dict[str, Any]]:
        properties = dict(_CONFIGURABLE_PLATFORM_PROPERTIES)
        for key in sorted(
            self._extract_graph_scope_configurable_keys(graph_entry_file)
        ):
            properties.setdefault(key, {"type": "string", "required": False})
        return properties

    def _extract_graph_scope_configurable_keys(self, graph_entry_file: Path) -> set[str]:
        scope_root = graph_entry_file.parent
        keys: set[str] = set()
        for path in scope_root.rglob("*.py"):
            if any(part in {"tests", "__pycache__"} for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            keys.update(
                self._extract_mapping_get_call_string_args(
                    tree,
                    target_names={"configurable", "private_config"},
                )
            )
        return {
            key
            for key in keys
            if key
            and key not in _CONFIGURABLE_NOISE_KEYS
            and not key.startswith("_")
            and len(key) < 128
        }

    def _extract_dataclass_fields(
        self,
        tree: ast.AST,
        class_name: str,
    ) -> dict[str, ast.expr | None]:
        for node in tree.body if isinstance(tree, ast.Module) else []:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                result: dict[str, ast.expr | None] = {}
                for child in node.body:
                    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        result[child.target.id] = child.annotation
                return result
        return {}

    def _extract_mapping_get_call_string_args(
        self,
        tree: ast.AST,
        *,
        target_names: set[str],
    ) -> set[str]:
        keys: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "get":
                continue
            if not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id not in target_names:
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                keys.add(first_arg.value)
        return keys

    def _annotation_to_schema_type(self, annotation: ast.expr | None) -> str:
        if annotation is None:
            return "string"
        if isinstance(annotation, ast.Name):
            mapping = {
                "str": "string",
                "int": "number",
                "float": "number",
                "bool": "boolean",
                "dict": "object",
                "list": "array[string]",
            }
            return mapping.get(annotation.id, "string")
        if isinstance(annotation, ast.Subscript):
            value = annotation.value
            if isinstance(value, ast.Name) and value.id in {"list", "Sequence"}:
                return "array[string]"
            if isinstance(value, ast.Name) and value.id in {"dict", "Mapping"}:
                return "object"
            if isinstance(value, ast.Name) and value.id == "Literal":
                return "string"
        return "string"

    def _fallback_schema(self, graph_id: str, *, reason: str) -> dict[str, Any]:
        return {
            "graph_id": graph_id,
            "schema_version": "fallback-v2",
            "dynamic": False,
            "reason": reason,
            "sections": [
                {
                    "key": "config",
                    "title": "Execution Config",
                    "type": "object",
                    "required": False,
                    "properties": self._execution_config_properties(),
                },
                {
                    "key": "context",
                    "title": "Runtime Context",
                    "type": "object",
                    "required": False,
                    "properties": build_runtime_context_schema_properties(),
                    "readonly_keys": list(RUNTIME_CONTEXT_READONLY_KEYS),
                },
                {
                    "key": "configurable",
                    "title": "Platform / Private Configurable",
                    "type": "object",
                    "required": False,
                    "properties": dict(_CONFIGURABLE_PLATFORM_PROPERTIES),
                },
            ],
        }
