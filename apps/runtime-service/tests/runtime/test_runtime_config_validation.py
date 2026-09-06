from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "validate_runtime_config.py"
SPEC = importlib.util.spec_from_file_location("validate_runtime_config", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _base(**overrides: str) -> dict[str, str]:
    values = {
        "PLATFORM_RUNTIME_DELEGATION_SECRET": "s" * 32,
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": "c" * 32,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
        "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "https://runtime-service.local",
        "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
        "GRAPHHARBOR_WORKSPACE_ROOT": "/tmp/runtime-workspaces",
        "RUNTIME_WORKSPACE_MAX_FILE_BYTES": "1",
        "RUNTIME_WORKSPACE_MAX_FILES": "1",
        "RUNTIME_WORKSPACE_MAX_TOTAL_BYTES": "1",
        "RUNTIME_WORKSPACE_TTL_SECONDS": "1",
        "GRAPHHARBOR_RUN_TIMEOUT_SECONDS": "1",
    }
    values.update(overrides)
    return values


def _write(tmp_path: Path, values: dict[str, str]) -> Path:
    path = tmp_path / "runtime.env"
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    return path


def test_runtime_config_accepts_empty_model_catalog(tmp_path: Path) -> None:
    assert module.validate(_write(tmp_path, _base())) == []


def test_runtime_config_ignores_retired_profile_and_e2e_variables(tmp_path: Path) -> None:
    values = _base(RUNTIME_MODEL_PROFILE="legacy", RUNTIME_E2E="invalid")
    assert module.validate(_write(tmp_path, values)) == []
