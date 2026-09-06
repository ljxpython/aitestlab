from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.langgraph import LangGraphRuntimeClient
from app.core.config import Settings
from app.modules.runtime_catalog.application import RuntimeCatalogService


def build_runtime_catalog_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
    forwarded_headers: Mapping[str, str] | None = None,
    tenant_id: str = "__default",
) -> RuntimeCatalogService:
    upstream = LangGraphRuntimeClient(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers=forwarded_headers,
    )
    return RuntimeCatalogService(
        session_factory=session_factory,
        upstream=upstream,
        runtime_base_url=settings.langgraph_upstream_url,
        settings=settings,
        tenant_id=tenant_id,
    )
