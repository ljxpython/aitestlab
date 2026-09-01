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
from runtime_service.runtime.auth import (
    RuntimeScope,
    VerifiedDelegation,
    verified_delegation_from_user,
    verify_delegation_claims,
    verify_delegation_token,
)
from runtime_service.runtime.resolver import (
    parse_runtime_context,
    parse_runtime_policy,
    parse_runtime_principal,
    resolve_runtime_config,
    resolved_runtime_config_from_snapshot,
    runtime_config_snapshot,
    runtime_context_hash,
    reject_untrusted_configurable,
)

__all__ = [
    "AgentDefaults",
    "ResolvedRuntimeConfig",
    "RuntimeAuthError",
    "RuntimeContext",
    "RuntimeErrorBase",
    "RuntimePolicy",
    "RuntimePrincipal",
    "RuntimeScope",
    "VerifiedDelegation",
    "verified_delegation_from_user",
    "RuntimeResolutionError",
    "build_model",
    "verify_delegation_token",
    "verify_delegation_claims",
    "parse_runtime_context",
    "parse_runtime_policy",
    "parse_runtime_principal",
    "resolve_runtime_config",
    "resolved_runtime_config_from_snapshot",
    "runtime_config_snapshot",
    "runtime_context_hash",
    "reject_untrusted_configurable",
]
