"""Small, fail-soft Langfuse adapter for Runtime Service graphs."""

from __future__ import annotations

import logging
import os
import threading
import time
from asyncio import CancelledError
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

logger = logging.getLogger(__name__)

_REQUIRED_SETTINGS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
_ALLOWED_METADATA = frozenset(
    {
        "request_id",
        "platform_trace_id",
        "run_id",
        "thread_id",
        "graph_id",
        "assistant_id",
        "assistant_version",
        "deployment_version",
        "tenant_id",
        "project_id",
        "user_id",
        "model_id",
        "config_hash",
        "prompt_version",
        "prompt_hash",
        "policy_version",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "token",
        "access_token",
        "api_key",
        "x-api-key",
        "secret",
        "client_secret",
        "password",
    }
)
_MAX_VALUE_LENGTH = 256

_client: Any | None = None
_client_lock = threading.Lock()
_metrics: Counter[str] = Counter()


class LangfuseConfigurationError(RuntimeError):
    """Raised when Langfuse was explicitly enabled with invalid settings."""


def _enabled(env: Mapping[str, str]) -> bool:
    return env.get("LANGFUSE_ENABLED", "").strip().lower() == "true"


def _settings(env: Mapping[str, str]) -> dict[str, str] | None:
    if not _enabled(env):
        return None
    missing = [name for name in _REQUIRED_SETTINGS if not env.get(name)]
    if missing:
        raise LangfuseConfigurationError(
            "Missing Langfuse settings: " + ", ".join(missing)
        )
    return {
        "public_key": env["LANGFUSE_PUBLIC_KEY"],
        "secret_key": env["LANGFUSE_SECRET_KEY"],
        "base_url": env["LANGFUSE_BASE_URL"],
        "environment": env.get("LANGFUSE_TRACING_ENVIRONMENT", "local"),
    }


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        return value[:_MAX_VALUE_LENGTH] if len(value) <= _MAX_VALUE_LENGTH else "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value[:32]]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value[:32])
    return value


def _mask(*, data: Any, **_: Any) -> Any:
    """Mask callback payloads before Langfuse export.

    Metadata is attached separately; callback input/output strings are intentionally not retained.
    """

    if isinstance(data, str):
        return "[REDACTED]"
    return _redact(data)


class _RuntimeDiagnosticsCallback(BaseCallbackHandler):
    """Bounded Run/Tool diagnostics independent of Langfuse export."""

    def __init__(self, graph_id: str) -> None:
        self._graph_id = graph_id
        self._starts: dict[Any, float] = {}

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            self._starts[run_id] = time.monotonic()

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            self._finish(run_id, "success")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            status = (
                "cancelled"
                if isinstance(error, CancelledError)
                else "timeout"
                if isinstance(error, TimeoutError)
                else "failed"
            )
            self._finish(run_id, status)

    def on_tool_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        _metrics["tool_error"] += 1
        logger.warning(
            "runtime_tool_error",
            extra={
                "graph_id": self._graph_id,
                "tool_name": str(kwargs.get("name", "unknown"))[:_MAX_VALUE_LENGTH],
            },
        )

    def on_llm_end(self, response: Any, *, run_id: Any, **_: Any) -> None:
        usage = getattr(response, "llm_output", None) or {}
        token_usage = usage.get("token_usage", {}) if isinstance(usage, Mapping) else {}
        total = token_usage.get("total_tokens") if isinstance(token_usage, Mapping) else None
        if isinstance(total, int) and total >= 0:
            _metrics["token_total"] += total

    def _finish(self, run_id: Any, status: str) -> None:
        started = self._starts.pop(run_id, None)
        duration_ms = round((time.monotonic() - started) * 1000, 2) if started is not None else None
        _metrics[f"run_{status}"] += 1
        logger.info(
            "runtime_run_completed",
            extra={"graph_id": self._graph_id, "status": status, "duration_ms": duration_ms},
        )


def initialize_langfuse(*, env: Mapping[str, str] | None = None) -> Any | None:
    """Initialize one process-scoped client, or return ``None`` when disabled."""

    global _client
    settings = _settings(os.environ if env is None else env)
    if settings is None:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            from langfuse import Langfuse

            _client = Langfuse(mask=_mask, **settings)
    return _client


def _new_callback() -> Any:
    settings = _settings(os.environ)
    if settings is None:
        return None
    initialize_langfuse()
    from langfuse.langchain import CallbackHandler

    return CallbackHandler(public_key=settings["public_key"])


def _values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _configurable(config: RunnableConfig) -> Mapping[str, Any]:
    value = config.get("configurable")
    return value if isinstance(value, Mapping) else {}


def _approved_metadata(config: RunnableConfig, graph_id: str) -> dict[str, Any]:
    metadata = config.get("metadata")
    result = {
        str(key): _redact(value, key=str(key))
        for key, value in (metadata.items() if isinstance(metadata, Mapping) else ())
        if str(key) in _ALLOWED_METADATA
    }
    configurable = _configurable(config)
    for key in ("thread_id", "run_id", "assistant_id"):
        value = configurable.get(key)
        if isinstance(value, (str, int)) and str(value):
            result.setdefault(key, str(value))
    result["graph_id"] = graph_id
    return result


def _merge_config(config: RunnableConfig, callback: Any, graph_id: str) -> RunnableConfig:
    bound = dict(config)
    metadata = (
        dict(config.get("metadata") or {})
        if isinstance(config.get("metadata"), Mapping)
        else {}
    )
    metadata.update(_approved_metadata(config, graph_id))
    tags = [
        tag
        for tag in _values(config.get("tags"))
        if isinstance(tag, str) and len(tag) <= _MAX_VALUE_LENGTH
    ]
    tags.extend(tag for tag in ("runtime-service", graph_id) if tag not in tags)
    callbacks = _values(config.get("callbacks"))
    callbacks.append(callback)
    bound["metadata"] = metadata
    bound["tags"] = tags
    bound["callbacks"] = callbacks
    return cast(RunnableConfig, bound)


def with_langfuse_tracing(
    graph: Pregel,
    config: RunnableConfig,
    *,
    graph_id: str,
    trusted_metadata: Mapping[str, Any] | None = None,
) -> Pregel:
    """Bind one Langfuse callback without changing graph construction or failures."""

    try:
        callback = _new_callback()
        if callback is None:
            return graph
        bound = _merge_config(config, callback, graph_id)
        callbacks = list(bound["callbacks"])
        callbacks.append(_RuntimeDiagnosticsCallback(graph_id))
        bound["callbacks"] = callbacks
        bound_metadata = dict(bound.get("metadata") or {})
        if trusted_metadata:
            bound_metadata.update(
                {
                    str(key): _redact(value, key=str(key))
                    for key, value in trusted_metadata.items()
                    if str(key) in _ALLOWED_METADATA
                }
            )
        bound_metadata["langfuse_trace_name"] = graph_id
        if isinstance(bound_metadata.get("thread_id"), (str, int)):
            bound_metadata["langfuse_session_id"] = str(bound_metadata["thread_id"])
        if isinstance(bound_metadata.get("user_id"), (str, int)):
            bound_metadata["langfuse_user_id"] = str(bound_metadata["user_id"])
        bound_metadata["langfuse_tags"] = ["runtime-service", graph_id]
        bound["metadata"] = bound_metadata
        _metrics["trace_bound"] += 1
        return cast(Pregel, graph.with_config(bound))
    except LangfuseConfigurationError:
        raise
    except Exception:
        _metrics["callback_error"] += 1
        logger.exception("runtime_langfuse_callback_error", extra={"graph_id": graph_id})
        return graph


def close_langfuse(*, timeout_seconds: float = 5.0) -> None:
    """Flush the process client with a bounded best-effort shutdown."""

    global _client
    client = _client
    if client is None:
        return

    done = threading.Event()

    def flush() -> None:
        try:
            client.flush()
        except Exception:
            _metrics["flush_error"] += 1
            logger.exception("runtime_langfuse_flush_error")
        finally:
            done.set()

    threading.Thread(target=flush, daemon=True).start()
    if not done.wait(timeout_seconds):
        _metrics["flush_timeout"] += 1
        logger.warning("runtime_langfuse_flush_timeout")
    _client = None


def get_observability_metrics() -> dict[str, int]:
    """Return a snapshot for tests and service diagnostics."""

    return dict(_metrics)


__all__ = [
    "LangfuseConfigurationError",
    "close_langfuse",
    "get_observability_metrics",
    "initialize_langfuse",
    "with_langfuse_tracing",
]
