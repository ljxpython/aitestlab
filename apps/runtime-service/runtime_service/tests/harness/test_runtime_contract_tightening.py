from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime import __all__ as runtime_public_api  # noqa: E402


def _read_source(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(
        encoding="utf-8"
    )


def test_runtime_public_api_excludes_legacy_runtime_entrypoints() -> None:
    forbidden_exports = {
        "AppRuntimeConfig",
        "ModelSpec",
        "build_runtime_config",
        "merge_trusted_auth_context",
        "resolve_model",
        "apply_model_runtime_params",
        "ResolvedRuntimeRequest",
        "resolve_runtime_request",
    }
    assert forbidden_exports.isdisjoint(set(runtime_public_api))


def test_legacy_runtime_options_module_is_deleted() -> None:
    options_file = Path(__file__).resolve().parents[2] / "runtime" / "options.py"
    assert not options_file.exists()


def test_legacy_graph_entrypoints_and_workflow_service_are_deleted() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    deleted_paths = [
        base_dir / "agents" / "assistant_agent" / "graph_entrypoint.py",
        base_dir / "agents" / "assistant_agent" / "graph_legacy.py",
        base_dir / "services" / "usecase_workflow_agent",
    ]
    for path in deleted_paths:
        assert not path.exists(), f"legacy path must stay deleted: {path}"


def test_runtime_modeling_only_exposes_resolve_model_by_id_path() -> None:
    source = _read_source("runtime/modeling.py")
    assert "def resolve_model(" not in source
    assert "def apply_model_runtime_params(" not in source


def test_runtime_options_are_read_only_from_platform_runtime_config() -> None:
    source = _read_source("runtime/runtime_request_resolver.py")
    assert 'configurable.get("platform_runtime")' in source
    assert 'configurable.get("project_id")' not in source
    assert 'configurable.get("user_id")' not in source
    assert "resolve_trusted_runtime_context(" in source
    assert "runtime," in source


def test_formal_runtime_consumers_do_not_read_legacy_runtime_context() -> None:
    for relative_path in (
        "middlewares/runtime_request.py",
        "services/test_case_service/document_persistence.py",
        "services/test_case_service_v2/document_persistence.py",
        "services/test_case_service/knowledge_query_guard_middleware.py",
        "services/test_case_service_v2/knowledge_query_guard_middleware.py",
    ):
        source = _read_source(relative_path)
        assert "request.runtime.context" not in source
        assert "coerce_runtime_context(" not in source


def test_test_case_document_persistence_does_not_infer_project_id_from_config() -> None:
    source = _read_source("services/test_case_service/document_persistence.py")
    assert 'configurable.get("project_id")' not in source
    assert 'configurable.get("x-project-id")' not in source
    assert 'metadata_map.get("project_id")' not in source
    assert 'state.get("project_id")' not in source
    assert "allow_default_project_fallback" not in source


def test_test_case_knowledge_guard_does_not_infer_project_id() -> None:
    source = _read_source("services/test_case_service/knowledge_query_guard_middleware.py")
    assert "_LATEST_PROJECT_ID_PATTERN" not in source
    assert 'state.get("project_id")' not in source
    assert "system_text" not in source


def test_mainline_graphs_and_services_do_not_use_legacy_build_runtime_config() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    checked_files: list[Path] = []
    for relative_dir in ("agents", "middlewares", "services"):
        for path in (base_dir / relative_dir).rglob("*.py"):
            if "tests" in path.parts:
                continue
            checked_files.append(path)
            source = path.read_text(encoding="utf-8")
            assert "build_runtime_config(" not in source, f"legacy runtime config found in {path}"

    assert checked_files, "expected at least one mainline source file to be checked"


def test_graph_modules_do_not_reintroduce_make_graph_factory_exports() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    checked_graphs: list[Path] = []
    for relative_dir in ("agents", "services"):
        for path in (base_dir / relative_dir).rglob("graph.py"):
            checked_graphs.append(path)
            source = path.read_text(encoding="utf-8")
            assert "def make_graph(" not in source, f"legacy graph factory found in {path}"
            assert (
                "async def make_graph(" not in source
            ), f"legacy async graph factory found in {path}"
            assert "graph = make_graph" not in source, f"legacy graph export found in {path}"

    assert checked_graphs, "expected at least one graph module to be checked"


def test_live_debug_scripts_do_not_use_legacy_runtime_builders() -> None:
    base_dir = Path(__file__).resolve().parents[2] / "tests"
    target_files = [
        base_dir / "services_test_case_service_debug.py",
        base_dir / "services_test_case_service_document_live.py",
        base_dir / "services_test_case_service_knowledge_live.py",
        base_dir / "services_test_case_service_persistence_live.py",
        base_dir / "services_test_case_service_skills.py",
        base_dir / "model_use.py",
        base_dir / "test_model_smoke.py",
    ]

    for path in target_files:
        source = path.read_text(encoding="utf-8")
        assert "build_runtime_config(" not in source, f"legacy runtime config found in {path}"
        assert "merge_trusted_auth_context(" not in source, f"legacy auth merge found in {path}"
        assert "apply_model_runtime_params(" not in source, f"legacy model binding found in {path}"
