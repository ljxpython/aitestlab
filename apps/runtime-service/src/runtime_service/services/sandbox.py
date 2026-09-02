"""Runtime-owned Sandbox reconnect adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping

from deepagents.backends import LangSmithSandbox
from langsmith.sandbox import AsyncSandboxClient

from runtime_service.runtime import (
    RuntimePrincipal,
    RuntimeResolutionError,
    resolve_resource_binding,
)


async def reconnect_langsmith_sandbox(
    config: Mapping[str, object], principal: RuntimePrincipal
) -> LangSmithSandbox:
    """Reconnect only the Sandbox ID recorded on the authenticated Thread."""

    binding = resolve_resource_binding(config, principal, "sandbox")
    if binding.provider != "langsmith":
        raise RuntimeResolutionError("runtime.sandbox.recovery_failed")
    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGSMITH_API_KEY_PROD")
    if not api_key:
        raise RuntimeResolutionError("runtime.sandbox.recovery_failed")
    root = os.environ.get("SANDBOX_LANGSMITH_ENDPOINT") or os.environ.get(
        "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
    )
    endpoint = root.rstrip("/")
    if not endpoint.endswith("/v2/sandboxes"):
        endpoint += "/v2/sandboxes"
    try:
        async with AsyncSandboxClient(api_key=api_key, api_endpoint=endpoint) as client:
            sandbox = await client.get_sandbox(name=binding.resource_id)
            return LangSmithSandbox(sandbox.to_sync())
    except Exception as exc:
        raise RuntimeResolutionError("runtime.sandbox.recovery_failed") from exc


__all__ = ["reconnect_langsmith_sandbox"]
