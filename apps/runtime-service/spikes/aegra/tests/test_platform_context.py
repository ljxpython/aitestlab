from __future__ import annotations

import time

import jwt
import pytest

from runtime_service.runtime.auth import verify_delegation_token
from runtime_service.runtime.contracts import AgentDefaults
from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.resolver import parse_runtime_context, resolve_runtime_config


_SECRET = "aegra-spike-context-secret-32-bytes"


def _token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": "spike-user",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "role": "developer",
            "permissions": ["runtime.read"],
            "policy_version": "policy-1",
            "allowed_model_ids": ["deepseek:chat"],
            "allowed_tool_names": ["search"],
            "iat": now,
            "exp": now + 60,
            "iss": "aegra-spike",
            "aud": "runtime-service",
        },
        _SECRET,
        algorithm="HS256",
    )


def test_platform_context_fixture_is_server_authoritative() -> None:
    principal, policy = verify_delegation_token(
        _token(), secret=_SECRET, issuer="aegra-spike", audience="runtime-service"
    )
    context = parse_runtime_context({"model_id": "deepseek:chat", "temperature": 0})
    resolved = resolve_runtime_config(
        principal=principal,
        context=context,
        policy=policy,
        defaults=AgentDefaults(
            model_id="deepseek:chat", system_prompt="spike", prompt_version="1"
        ),
    )
    assert resolved.principal.tenant_id == "tenant-a"
    assert resolved.model_id == "deepseek:chat"

    with pytest.raises(RuntimeResolutionError):
        parse_runtime_context({"user_id": "attacker", "tenant_id": "other"})
