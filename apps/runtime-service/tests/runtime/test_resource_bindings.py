from __future__ import annotations

import pytest

from runtime_service.runtime import RuntimePrincipal, RuntimeResolutionError, resolve_resource_binding


def _principal() -> RuntimePrincipal:
    return RuntimePrincipal("user", "tenant", "project", "developer", ())


def _config(metadata: object, thread_id: str = "thread") -> dict[str, object]:
    return {"metadata": metadata, "configurable": {"thread_id": thread_id}}


def _binding(**overrides: str) -> dict[str, object]:
    value = {
        "provider": "graphharbor_workspace",
        "resource_id": "workspace-a",
        "tenant_id": "tenant",
        "project_id": "project",
        "thread_id": "thread",
    }
    value.update(overrides)
    return value


def test_resource_binding_reads_server_owned_thread_metadata() -> None:
    config = _config(
        {
            "__graphharbor_thread_metadata": {
                "runtime_resource_bindings": {
                    "schema": "runtime-resource-bindings/v1",
                    "workspace": _binding(),
                }
            },
            "runtime_resource_bindings": {"schema": "bad"},
        }
    )
    binding = resolve_resource_binding(config, _principal(), "workspace")
    assert binding.resource_id == "workspace-a"


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"runtime_resource_bindings": {"schema": "runtime-resource-bindings/v1"}},
        {
            "runtime_resource_bindings": {
                "schema": "runtime-resource-bindings/v1",
                "workspace": _binding(tenant_id="other-tenant"),
            }
        },
        {
            "runtime_resource_bindings": {
                "schema": "runtime-resource-bindings/v1",
                "workspace": _binding(thread_id="other-thread"),
            }
        },
    ],
)
def test_resource_binding_fails_closed(metadata: object) -> None:
    with pytest.raises(RuntimeResolutionError, match="runtime.workspace.recovery_failed"):
        resolve_resource_binding(_config({"__graphharbor_thread_metadata": metadata}), _principal(), "workspace")


def test_resource_binding_does_not_trust_run_metadata() -> None:
    config = _config({"__graphharbor_thread_metadata": {"runtime_resource_bindings": {"schema": "bad"}}})
    with pytest.raises(RuntimeResolutionError, match="runtime.workspace.recovery_failed"):
        resolve_resource_binding(config, _principal(), "workspace")
