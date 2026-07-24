from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import Settings
from app.core.db import build_engine, build_session_factory, create_core_tables
from app.modules.identity.application.service import IdentityService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    if settings.platform_db_enabled:
        engine = build_engine(settings.database_url or "")
        session_factory = build_session_factory(engine)
        app.state.db_engine = engine
        app.state.db_session_factory = session_factory
        if settings.platform_db_auto_create:
            create_core_tables(engine)
        if settings.bootstrap_admin_enabled:
            service = IdentityService(
                settings=settings,
                session_factory=session_factory,
            )
            await service.ensure_bootstrap_admin()

    try:
        yield
    finally:
        engine = getattr(app.state, "db_engine", None)
        if engine is not None:
            engine.dispose()
