"""Agent Server application lifespan owned by Runtime Service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from runtime_service.observability import close_langfuse, initialize_langfuse


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_langfuse()
    try:
        yield
    finally:
        close_langfuse(timeout_seconds=5.0)


app = FastAPI(lifespan=lifespan)

__all__ = ["app", "lifespan"]
