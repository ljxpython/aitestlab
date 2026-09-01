from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values
from langgraph_sdk import get_client


SPIKE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SPIKE_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _private_env() -> dict[str, str]:
    env_file = os.getenv("AEGRA_SPIKE_ENV_FILE") or str(Path.home() / ".my_best" / ".env")
    values = dotenv_values(env_file) if Path(env_file).exists() else {}
    return {key: str(value) for key, value in values.items() if value is not None}


def _require_spike() -> None:
    if os.getenv("AEGRA_SPIKE_E2E") != "1":
        pytest.skip("set AEGRA_SPIKE_E2E=1 to run Aegra compatibility checks")


@pytest.fixture
def base_url() -> str:
    _require_spike()
    return os.getenv("AEGRA_SPIKE_URL", "http://127.0.0.1:2026").rstrip("/")


@pytest.fixture
def client(base_url: str):
    token = os.getenv("AEGRA_SPIKE_AUTH_TOKEN", "aegra-spike-token")
    value = get_client(url=base_url, headers={"Authorization": f"Bearer {token}"})
    # Tests use their own asyncio.run() loop; closing the SDK client from a
    # different loop raises a false teardown error in httpx/httpcore.
    yield value


@pytest.fixture
def real_env() -> dict[str, str]:
    _require_spike()
    merged = _private_env()
    merged.update(os.environ)
    return merged


def require_keys(env: dict[str, str], *keys: str) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        pytest.skip(f"real dependency settings missing: {', '.join(missing)}")
