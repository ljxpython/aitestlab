from __future__ import annotations

from typing import Any, Mapping

from app.adapters.langgraph.sdk_client import (
    get_langgraph_client,
    raise_assistants_upstream_error,
)

FORWARDED_HEADER_KEYS = ("authorization", "x-project-id", "x-request-id")


def build_forward_headers(
    headers: Mapping[str, str | None],
    *,
    request_id: str | None = None,
) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key in FORWARDED_HEADER_KEYS:
        value = headers.get(key)
        if value:
            forwarded[key] = value
    if "x-request-id" not in forwarded and request_id:
        forwarded["x-request-id"] = request_id
    return forwarded


class LangGraphAssistantsClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = get_langgraph_client(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            forwarded_headers=forwarded_headers,
            timeout_seconds=timeout_seconds,
        )

    async def get_assistant(self, assistant_id: str) -> Any:
        try:
            return await self._client.assistants.get(assistant_id)
        except Exception as exc:
            raise_assistants_upstream_error(exc, upstream_path=f"/assistants/{assistant_id}")

    async def create_assistant(self, payload: Mapping[str, Any]) -> Any:
        try:
            return await self._client.assistants.create(**dict(payload))
        except Exception as exc:
            raise_assistants_upstream_error(exc, upstream_path="/assistants")

    async def update_assistant(self, assistant_id: str, payload: Mapping[str, Any]) -> Any:
        try:
            return await self._client.assistants.update(assistant_id, **dict(payload))
        except Exception as exc:
            raise_assistants_upstream_error(exc, upstream_path=f"/assistants/{assistant_id}")

    async def delete_assistant(
        self,
        assistant_id: str,
        *,
        delete_threads: bool = False,
    ) -> Any:
        try:
            return await self._client.assistants.delete(
                assistant_id,
                delete_threads=delete_threads,
            )
        except Exception as exc:
            raise_assistants_upstream_error(exc, upstream_path=f"/assistants/{assistant_id}")
