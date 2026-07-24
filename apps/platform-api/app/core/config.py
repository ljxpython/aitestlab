from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Platform API"
    app_version: str = "0.1.2"
    app_env: str = "local"
    api_docs_enabled: bool = True
    cors_allow_origins: tuple[str, ...] = ("*",)

    langgraph_upstream_url: str = "http://127.0.0.1:8123"
    langgraph_upstream_api_key: str | None = None
    langgraph_upstream_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    langgraph_graph_source_root: str | None = None
    interaction_data_service_url: str | None = "http://127.0.0.1:8081"
    interaction_data_service_token: str | None = None
    interaction_data_service_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    knowledge_upstream_url: str = "http://127.0.0.1:9621"
    knowledge_upstream_api_key: str | None = None
    knowledge_upstream_timeout_seconds: float = Field(default=60.0, gt=0, le=600)

    platform_db_enabled: bool = False
    platform_db_auto_create: bool = False
    database_url: str | None = None
    operations_queue_backend: str = "db_polling"
    operations_worker_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    operations_worker_idle_sleep_seconds: float = Field(default=2.0, gt=0, le=120)
    operations_worker_heartbeat_interval_seconds: float = Field(default=10.0, gt=1, le=300)
    operations_worker_stale_after_seconds: float = Field(default=45.0, gt=5, le=3600)
    operations_redis_url: str | None = None
    operations_redis_queue_name: str = "platform.operations"
    operations_artifacts_dir: str = ".runtime/operations-artifacts"
    operations_artifact_storage_backend: str = "local"
    operations_artifact_retention_hours: int = Field(default=72, ge=1, le=24 * 365)
    operations_artifact_cleanup_batch_size: int = Field(default=100, ge=1, le=1000)
    observability_metrics_top_paths_limit: int = Field(default=10, ge=1, le=50)

    auth_required: bool = True
    jwt_access_secret: str = "change-me-access-secret-at-least-32-bytes"
    jwt_refresh_secret: str = "change-me-refresh-secret-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "platform-api"
    jwt_audience: str = "platform-control-plane"
    jwt_access_kid: str = "access-v1"
    jwt_refresh_kid: str = "refresh-v1"
    jwt_access_verification_keys: dict[str, str] = Field(default_factory=dict)
    jwt_refresh_verification_keys: dict[str, str] = Field(default_factory=dict)
    jwt_access_ttl_seconds: int = Field(default=1800, ge=60)
    jwt_refresh_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=300)
    oidc_enabled: bool = False
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    service_accounts_enabled: bool = True
    service_account_api_key_header: str = "x-platform-api-key"
    service_account_token_default_ttl_days: int = Field(default=90, ge=1, le=3650)

    bootstrap_admin_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123456"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PLATFORM_API_",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.startswith("["):
                try:
                    parsed = json.loads(normalized)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    return tuple(items or ["*"])
            items = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(items or ["*"])
        if isinstance(value, (list, tuple)):
            items = [str(item).strip() for item in value if str(item).strip()]
            return tuple(items or ["*"])
        return ("*",)

    @model_validator(mode="after")
    def validate_security_guards(self) -> "Settings":
        normalized_env = self.app_env.lower()
        if normalized_env not in {"local", "dev", "staging", "prod", "production"}:
            raise ValueError("app_env must be one of local/dev/staging/prod/production")

        is_production = normalized_env in {"prod", "production"}
        if self.platform_db_enabled and not self.database_url:
            raise ValueError(
                "PLATFORM_API_DATABASE_URL is required when platform_db_enabled=true"
            )
        if self.operations_queue_backend not in {"db_polling", "redis_list"}:
            raise ValueError("operations_queue_backend must be 'db_polling' or 'redis_list'")
        if self.operations_queue_backend == "redis_list" and not self.operations_redis_url:
            raise ValueError("operations_redis_url is required when operations_queue_backend='redis_list'")
        if self.operations_artifact_storage_backend not in {"local"}:
            raise ValueError("operations_artifact_storage_backend must be 'local'")
        if self.operations_worker_stale_after_seconds <= self.operations_worker_heartbeat_interval_seconds:
            raise ValueError(
                "operations_worker_stale_after_seconds must be greater than heartbeat interval"
            )
        if self.oidc_enabled and (not self.oidc_issuer_url or not self.oidc_client_id):
            raise ValueError("oidc_issuer_url and oidc_client_id are required when oidc_enabled=true")
        if self.jwt_algorithm not in {"HS256", "HS384", "HS512"}:
            raise ValueError("jwt_algorithm must be one of HS256/HS384/HS512")
        if is_production:
            if self.api_docs_enabled:
                raise ValueError("API docs must be disabled in production")
            if self.bootstrap_admin_enabled:
                raise ValueError("Bootstrap admin must be disabled in production")
            if self.jwt_access_secret == "change-me-access-secret-at-least-32-bytes":
                raise ValueError("JWT access secret must be overridden in production")
            if self.jwt_refresh_secret == "change-me-refresh-secret-at-least-32-bytes":
                raise ValueError("JWT refresh secret must be overridden in production")
        return self


def load_settings() -> Settings:
    return Settings()
