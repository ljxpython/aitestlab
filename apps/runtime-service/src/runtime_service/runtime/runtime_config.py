"""Small adapter for the explicit LangGraph Runtime context boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_service.runtime.contracts import RuntimeContext
from runtime_service.runtime.resolver import parse_runtime_context


def parse_context(value: Mapping[str, Any] | RuntimeContext | None) -> RuntimeContext:
    """Parse only the new Context shape; legacy fields are rejected."""

    return parse_runtime_context(value)


def context_from_runtime(runtime: object) -> RuntimeContext:
    """Read ``runtime.context`` without mutating the LangGraph runtime object."""

    return parse_runtime_context(getattr(runtime, "context", None))


__all__ = ["context_from_runtime", "parse_context"]
