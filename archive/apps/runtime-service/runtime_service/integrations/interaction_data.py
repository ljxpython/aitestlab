from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests
from runtime_service.runtime.config_utils import read_configurable

DEFAULT_INTERACTION_DATA_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class InteractionDataServiceConfig:
    service_url: str | None = None
    service_token: str | None = None
    timeout_seconds: int = DEFAULT_INTERACTION_DATA_TIMEOUT_SECONDS


class InteractionDataServiceClient:
    def __init__(self, config: InteractionDataServiceConfig):
        self._config = config

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    @property
    def base_url(self) -> str | None:
        value = self._config.service_url
        if not isinstance(value, str) or not value.strip():
            return None
        return value.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.service_token:
            headers["Authorization"] = f"Bearer {self._config.service_token}"
        return headers

    @property
    def auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._config.service_token:
            headers["Authorization"] = f"Bearer {self._config.service_token}"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_payload: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_url = self.base_url
        if not base_url:
            raise RuntimeError("interaction_data_service_not_configured")
        response = requests.request(
            method=method.upper(),
            url=f"{base_url}{path}",
            headers=self.headers,
            json=dict(json_payload) if json_payload is not None else None,
            params=dict(params) if params is not None else None,
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.request_json("POST", path, json_payload=payload)

    def get_json(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.request_json("GET", path, params=params)

    def patch_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.request_json("PATCH", path, json_payload=payload)

    def delete_json(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.request_json("DELETE", path, params=params)

    def post_multipart(
        self,
        path: str,
        *,
        form_data: Mapping[str, Any],
        file_field_name: str,
        file_name: str,
        file_bytes: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        base_url = self.base_url
        if not base_url:
            raise RuntimeError("interaction_data_service_not_configured")
        response = requests.post(
            url=f"{base_url}{path}",
            headers=self.auth_headers,
            data={
                key: value
                for key, value in form_data.items()
                if value is not None
            },
            files={
                file_field_name: (
                    file_name,
                    file_bytes,
                    content_type,
                )
            },
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def build_interaction_data_service_config(
    config: Mapping[str, Any] | None,
) -> InteractionDataServiceConfig:
    configurable = read_configurable(config)
    timeout_raw = (
        configurable.get("interaction_data_service_timeout_seconds")
        or os.getenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS")
        or DEFAULT_INTERACTION_DATA_TIMEOUT_SECONDS
    )
    try:
        timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_INTERACTION_DATA_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        timeout_seconds = DEFAULT_INTERACTION_DATA_TIMEOUT_SECONDS
    service_url = str(
        configurable.get("interaction_data_service_url")
        or os.getenv("INTERACTION_DATA_SERVICE_URL")
        or ""
    ).strip() or None
    service_token = str(
        configurable.get("interaction_data_service_token")
        or os.getenv("INTERACTION_DATA_SERVICE_TOKEN")
        or ""
    ).strip() or None
    return InteractionDataServiceConfig(
        service_url=service_url,
        service_token=service_token,
        timeout_seconds=timeout_seconds,
    )
