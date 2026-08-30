"""Public Runtime contracts and pure resolution entrypoints."""

from runtime_service.runtime.contracts import (
    AgentDefaults,
    ResolvedRuntimeConfig,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
)
from runtime_service.runtime.errors import (
    RuntimeAuthError,
    RuntimeErrorBase,
    RuntimeResolutionError,
)
from runtime_service.runtime.modeling import build_model
from runtime_service.runtime.auth import verify_delegation_token
from runtime_service.runtime.resolver import (
    parse_runtime_context,
    parse_runtime_policy,
    parse_runtime_principal,
    resolve_runtime_config,
)

__all__ = [
    "AgentDefaults",
    "ResolvedRuntimeConfig",
    "RuntimeAuthError",
    "RuntimeContext",
    "RuntimeErrorBase",
    "RuntimePolicy",
    "RuntimePrincipal",
    "RuntimeResolutionError",
    "build_model",
    "verify_delegation_token",
    "parse_runtime_context",
    "parse_runtime_policy",
    "parse_runtime_principal",
    "resolve_runtime_config",
]
