"""Small, fail-soft Langfuse adapter for Runtime Service graphs."""

from __future__ import annotations

import inspect
import logging
import os
import threading
import time
from asyncio import CancelledError
from collections import Counter
from collections.abc import Mapping
from typing import Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.observability.otel import (
    OTelDiagnosticsCallback,
    close_otel,
    initialize_otel,
)

logger = logging.getLogger(__name__)

_REQUIRED_SETTINGS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
_CALLER_METADATA = frozenset(
    {
        "request_id",
        "platform_trace_id",
        "run_id",
        "thread_id",
        "assistant_id",
        "assistant_version",
        "deployment_version",
    }
)
_TRUSTED_METADATA = frozenset(
    {
        "tenant_id",
        "project_id",
        "user_id",
        "model_id",
        "config_hash",
        "prompt_version",
        "prompt_hash",
        "policy_version",
        "request_id",
        "platform_trace_id",
    }
)
_ALLOWED_TAGS = frozenset({"environment", "service", "graph_id", "source", "release"})
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


def _error_category(error: BaseException) -> str:
    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        return "unauthorized"
    if status_code == 429:
        return "rate_limited"
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return "upstream_5xx"
    if isinstance(error, TimeoutError):
        return "timeout"
    return type(error).__name__


def _record_export_error(error: BaseException) -> None:
    _metrics["export_error"] += 1
    _metrics["event_dropped"] += 1
    logger.warning(
        "runtime_langfuse_event_dropped",
        extra={"error_category": _error_category(error)},
    )


class _FailSoftCallback(BaseCallbackHandler):
    """Keep SDK callback failures outside the Agent result path."""

    def __init__(self, delegate: BaseCallbackHandler) -> None:
        self._delegate = delegate
        self.raise_error = False

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("on_"):
            delegate = object.__getattribute__(self, "_delegate")
            method = getattr(delegate, name)

            def call(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = method(*args, **kwargs)
                except Exception as error:  # noqa: BLE001 - exporter must remain fail-soft.
                    _record_export_error(error)
                    return None
                if not inspect.isawaitable(result):
                    return result

                async def wait() -> Any:
                    try:
                        return await result
                    except Exception as error:  # noqa: BLE001 - exporter must remain fail-soft.
                        _record_export_error(error)
                        return None

                return wait()

            return call
        return super().__getattribute__(name)


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

    def __init__(self, graph_id: str, metadata: Mapping[str, Any]) -> None:
        self._graph_id = graph_id
        self._metadata = {
            key: metadata.get(key)
            for key in ("run_id", "thread_id", "request_id")
        }
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
                **self._metadata,
                "tool_name": str(kwargs.get("name", "unknown"))[:_MAX_VALUE_LENGTH],
                "error_category": type(error).__name__,
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
            extra={
                "graph_id": self._graph_id,
                **self._metadata,
                "callback_run_id": str(run_id),
                "status": status,
                "duration_ms": duration_ms,
            },
        )


def initialize_langfuse(*, env: Mapping[str, str] | None = None) -> Any | None:
    """Initialize one process-scoped client, or return ``None`` when disabled."""

    global _client
    settings_env = os.environ if env is None else env
    settings = _settings(settings_env)
    initialize_otel(env=settings_env, on_error=_record_export_error)
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

    return _FailSoftCallback(CallbackHandler(public_key=settings["public_key"]))


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
        if str(key) in _CALLER_METADATA
    }
    configurable = _configurable(config)
    for key in ("thread_id", "run_id", "assistant_id"):
        value = configurable.get(key)
        if isinstance(value, (str, int)) and str(value):
            result.setdefault(key, str(value))
    result["graph_id"] = graph_id
    return result


def _trusted_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    return {
        str(key): _redact(value, key=str(key))
        for key, value in metadata.items()
        if str(key) in _TRUSTED_METADATA
    }


def _merge_config(config: RunnableConfig, callback: Any, graph_id: str) -> RunnableConfig:
    bound = dict(config)
    metadata = _approved_metadata(config, graph_id)
    tags = [
        tag
        for tag in _values(config.get("tags"))
        if isinstance(tag, str) and tag in _ALLOWED_TAGS
    ]
    tags.extend(tag for tag in ("runtime-service", graph_id) if tag not in tags)
    callbacks = _values(config.get("callbacks"))
    if callback is not None:
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
        otel_provider = initialize_otel(on_error=_record_export_error)
        if callback is None and otel_provider is None:
            return graph
        bound = _merge_config(config, callback, graph_id)
        callbacks = list(bound["callbacks"])
        bound_metadata = dict(bound.get("metadata") or {})
        if trusted_metadata:
            bound_metadata.update(_trusted_metadata(trusted_metadata))
        if otel_provider is not None:
            callbacks.append(OTelDiagnosticsCallback(otel_provider, graph_id, bound_metadata))
        callbacks.append(_RuntimeDiagnosticsCallback(graph_id, bound_metadata))
        bound["callbacks"] = callbacks
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
        _metrics["export_error"] += 1
        logger.exception("runtime_langfuse_callback_error", extra={"graph_id": graph_id})
        return graph


def close_langfuse(*, timeout_seconds: float = 5.0) -> None:
    """Flush the process client with a bounded best-effort shutdown."""

    global _client
    client = _client
    if client is not None:
        done = threading.Event()

        def flush() -> None:
            try:
                client.flush()
            except Exception:
                _metrics["flush_error"] += 1
                _metrics["export_error"] += 1
                _metrics["event_dropped"] += 1
                logger.exception("runtime_langfuse_flush_error")
            finally:
                done.set()

        threading.Thread(target=flush, daemon=True).start()
        if not done.wait(timeout_seconds):
            _metrics["flush_timeout"] += 1
            _metrics["event_dropped"] += 1
            logger.warning("runtime_langfuse_flush_timeout")
        _client = None

    if not close_otel(timeout_seconds=timeout_seconds):
        _metrics["flush_timeout"] += 1
        _metrics["event_dropped"] += 1
        logger.warning("runtime_otel_flush_timeout")


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
