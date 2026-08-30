from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.auth import provider as auth_provider  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_demo_authenticate_with_bearer_token() -> None:
    user = _run(auth_provider.authenticate({"authorization": "Bearer owner-token"}))
    assert user["identity"] == "owner_user"
    assert user["role"] == "user"


def test_demo_authenticate_with_api_key() -> None:
    user = _run(auth_provider.authenticate({"x-api-key": "viewer-key"}))
    assert user["identity"] == "viewer_user"
    assert user["role"] == "viewer"


def test_on_access_threads_create_inject_owner() -> None:
    ctx = SimpleNamespace(
        resource="threads",
        action="create",
        user=auth_provider._DEMO_USERS["owner-token"],
    )
    payload: dict[str, object] = {}
    result = _run(auth_provider.on_access(ctx, payload))
    assert result == {"owner": "owner_user"}
    assert isinstance(payload.get("metadata"), dict)
    assert payload["metadata"]["owner"] == "owner_user"


def test_on_access_threads_create_forbidden_for_viewer() -> None:
    ctx = SimpleNamespace(
        resource="threads",
        action="create",
        user=auth_provider._DEMO_USERS["viewer-token"],
    )
    with pytest.raises(Exception) as exc_info:
        _run(auth_provider.on_access(ctx, {}))
    err = exc_info.value
    assert getattr(err, "status_code", None) == 403
