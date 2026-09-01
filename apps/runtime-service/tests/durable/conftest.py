from __future__ import annotations

import os

import pytest


@pytest.fixture
def durable_url() -> str:
    url = os.getenv("RUNTIME_DURABLE_URL")
    if not url:
        pytest.skip("RUNTIME_DURABLE_URL is required for durable tests")
    return url


@pytest.fixture
def durable_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_ASSISTANT_ID", "reference_agent")


@pytest.fixture
def durable_backend_assistant_id() -> str:
    value = os.getenv("RUNTIME_DURABLE_BACKEND_ASSISTANT_ID")
    if not value:
        pytest.skip("RUNTIME_DURABLE_BACKEND_ASSISTANT_ID is required for backend tests")
    return value
