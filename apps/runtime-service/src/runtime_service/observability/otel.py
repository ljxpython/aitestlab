"""Optional, fail-soft OpenTelemetry trace export for Runtime diagnostics."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Status, StatusCode


class OTelConfigurationError(RuntimeError):
    """Raised when an explicitly configured OTLP exporter is invalid."""


_provider: TracerProvider | None = None
_lock = threading.Lock()
_on_error: Callable[[BaseException], None] | None = None


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise OTelConfigurationError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise OTelConfigurationError(f"{name} must be a positive integer")
    return value


def _endpoint(env: Mapping[str, str]) -> str | None:
    value = env.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not value:
        base = env.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        value = f"{base.rstrip('/')}/v1/traces" if base else ""
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise OTelConfigurationError("OTLP endpoint must use http:// or https://")
    return value


class _RecordingExporter(SpanExporter):
    """Convert exporter failures into bounded diagnostics instead of Run errors."""

    def __init__(self, delegate: SpanExporter) -> None:
        self._delegate = delegate

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        try:
            result = self._delegate.export(spans)
        except Exception as exc:  # noqa: BLE001 - telemetry never owns Run failure.
            if _on_error is not None:
                _on_error(exc)
            return SpanExportResult.FAILURE
        if result != SpanExportResult.SUCCESS and _on_error is not None:
            _on_error(RuntimeError("OTLP exporter returned failure"))
        return result

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._delegate.force_flush(timeout_millis)


def initialize_otel(
    *, env: Mapping[str, str] | None = None, on_error: Callable[[BaseException], None] | None = None
) -> TracerProvider | None:
    """Create one process-scoped OTLP provider when an endpoint is configured."""

    global _provider, _on_error
    settings = os.environ if env is None else env
    endpoint = _endpoint(settings)
    if endpoint is None:
        return None
    with _lock:
        if _provider is not None:
            return _provider
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=None,
                timeout=float(_positive_int(settings, "OTEL_EXPORTER_OTLP_TIMEOUT", 10)),
            )
            processor = BatchSpanProcessor(
                _RecordingExporter(exporter),
                max_queue_size=_positive_int(settings, "OTEL_BSP_MAX_QUEUE_SIZE", 2048),
                max_export_batch_size=_positive_int(
                    settings, "OTEL_BSP_MAX_EXPORT_BATCH_SIZE", 512
                ),
                schedule_delay_millis=_positive_int(
                    settings, "OTEL_BSP_SCHEDULE_DELAY", 5000
                ),
            )
            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": settings.get(
                            "OTEL_SERVICE_NAME", "runtime-service"
                        )
                    }
                )
            )
            provider.add_span_processor(processor)
        except OTelConfigurationError:
            raise
        except Exception as exc:
            raise OTelConfigurationError("unable to initialize OTLP exporter") from exc
        _on_error = on_error
        _provider = provider
        return provider


def close_otel(*, timeout_seconds: float = 5.0) -> bool:
    """Shutdown the provider within a bound; return whether it completed."""

    global _provider, _on_error
    provider = _provider
    if provider is None:
        return True
    done = threading.Event()

    def shutdown() -> None:
        try:
            provider.shutdown()
        except Exception as exc:  # noqa: BLE001 - telemetry shutdown is fail-soft.
            if _on_error is not None:
                _on_error(exc)
        finally:
            done.set()

    threading.Thread(target=shutdown, daemon=True).start()
    completed = done.wait(timeout_seconds)
    _provider = None
    _on_error = None
    return completed


class OTelDiagnosticsCallback(BaseCallbackHandler):
    """Record only the root graph span and bounded Runtime identifiers."""

    def __init__(self, provider: TracerProvider, graph_id: str, metadata: Mapping[str, Any]) -> None:
        self._tracer = provider.get_tracer("runtime-service")
        self._graph_id = graph_id
        self._metadata = {
            key: str(metadata[key])
            for key in ("run_id", "thread_id", "request_id", "platform_trace_id")
            if metadata.get(key) is not None
        }
        self._spans: dict[Any, Span] = {}

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is not None:
            return
        self._spans[run_id] = self._tracer.start_span(
            "runtime.graph",
            attributes={"runtime.graph_id": self._graph_id, **self._metadata},
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            self._finish(run_id, StatusCode.OK)

    def on_chain_error(
        self, error: BaseException, *, run_id: Any, parent_run_id: Any = None, **_: Any
    ) -> None:
        if parent_run_id is None:
            span = self._spans.pop(run_id, None)
            if span is not None:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                span.end()

    def _finish(self, run_id: Any, status: StatusCode) -> None:
        span = self._spans.pop(run_id, None)
        if span is not None:
            span.set_status(Status(status))
            span.end()


__all__ = [
    "OTelConfigurationError",
    "OTelDiagnosticsCallback",
    "close_otel",
    "initialize_otel",
]
