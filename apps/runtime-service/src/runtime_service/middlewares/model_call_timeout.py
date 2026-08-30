"""Single async model-call timeout middleware."""

from __future__ import annotations

import asyncio
import math

from langchain.agents.middleware import AgentMiddleware, ModelRequest


class ModelCallTimeoutMiddleware(AgentMiddleware):
    """Cancel a provider call after a bounded wall-clock duration."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__()
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        self.timeout_seconds = float(timeout_seconds)

    async def awrap_model_call(self, request: ModelRequest, handler):
        async with asyncio.timeout(self.timeout_seconds):
            return await handler(request)


__all__ = ["ModelCallTimeoutMiddleware"]
