from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from runtime_service.conf.settings import require_model_spec


def _init_chat_model(
    *,
    model_provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> BaseChatModel:
    kwargs: dict[str, Any] = {
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return init_chat_model(model=model, model_provider=model_provider, **kwargs)


@lru_cache(maxsize=16)
def resolve_model_by_id(model_id: str) -> BaseChatModel:
    resolved_id, model_spec = require_model_spec(model_id)
    del resolved_id
    return _init_chat_model(
        model_provider=model_spec["model_provider"],
        model=model_spec["model"],
        api_key=model_spec["api_key"],
        base_url=model_spec["base_url"],
    )
