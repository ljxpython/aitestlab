from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from langfuse._client.span_processor import LangfuseSpanProcessor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from runtime_service.observability import langfuse, otel


class _Graph:
    def __init__(self) -> None:
        self.bound: dict[str, object] | None = None

    def with_config(self, config: dict[str, object]) -> _Graph:
        self.bound = config
        return self


def test_disabled_returns_original_graph_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _Graph()
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    assert langfuse.with_langfuse_tracing(graph, {}, graph_id="demo") is graph  # type: ignore[arg-type]
    assert graph.bound is None


def test_enabled_requires_complete_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    with pytest.raises(langfuse.LangfuseConfigurationError):
        langfuse.initialize_langfuse()


def test_initialize_reuses_process_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()
    monkeypatch.setattr(langfuse, "_client", client)
    env = {
        "LANGFUSE_ENABLED": "true",
        "LANGFUSE_PUBLIC_KEY": "public",
        "LANGFUSE_SECRET_KEY": "secret",
        "LANGFUSE_BASE_URL": "https://langfuse.invalid",
    }
    assert langfuse.initialize_langfuse(env=env) is client


def test_binding_merges_config_and_trusted_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _Graph()
    callback = object()
    monkeypatch.setattr(langfuse, "_new_callback", lambda: callback)
    bound = langfuse.with_langfuse_tracing(
        graph,  # type: ignore[arg-type]
        {
            "callbacks": ["caller"],
            "metadata": {"request_id": "req", "user_id": "attacker", "custom": "kept"},
            "tags": ["caller", "environment", "x" * 257],
            "configurable": {"thread_id": "thread-1"},
        },
        graph_id="demo",
        trusted_metadata={"user_id": "trusted", "tenant_id": "tenant-1"},
    )
    assert bound is graph
    assert graph.bound is not None
    assert graph.bound["callbacks"][:2] == ["caller", callback]  # type: ignore[index]
    assert type(graph.bound["callbacks"][2]).__name__ == "_RuntimeDiagnosticsCallback"  # type: ignore[index]
    assert graph.bound["metadata"] == {
        "request_id": "req",
        "user_id": "trusted",
        "thread_id": "thread-1",
        "graph_id": "demo",
        "tenant_id": "tenant-1",
        "langfuse_trace_name": "demo",
        "langfuse_session_id": "thread-1",
        "langfuse_user_id": "trusted",
        "langfuse_tags": ["runtime-service", "demo"],
    }
    assert graph.bound["tags"] == ["environment", "runtime-service", "demo"]


def test_untrusted_identity_is_not_added_to_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _Graph()
    monkeypatch.setattr(langfuse, "_new_callback", lambda: object())
    langfuse.with_langfuse_tracing(
        graph,  # type: ignore[arg-type]
        {
            "metadata": {
                "user_id": "attacker",
                "tenant_id": "attacker-tenant",
                "project_id": "attacker-project",
            }
        },
        graph_id="demo",
    )
    assert graph.bound is not None
    metadata = graph.bound["metadata"]  # type: ignore[assignment]
    assert "user_id" not in metadata
    assert "tenant_id" not in metadata
    assert "project_id" not in metadata
    assert "langfuse_user_id" not in metadata


def test_diagnostics_include_runtime_identifiers(caplog: pytest.LogCaptureFixture) -> None:
    callback = langfuse._RuntimeDiagnosticsCallback(
        "demo",
        {"run_id": "run-1", "thread_id": "thread-1", "request_id": "request-1"},
    )
    with caplog.at_level("INFO"):
        callback.on_chain_start({}, {}, run_id="callback-run")
        callback.on_chain_end({}, run_id="callback-run")
    record = next(item for item in caplog.records if item.message == "runtime_run_completed")
    assert record.run_id == "run-1"
    assert record.thread_id == "thread-1"
    assert record.request_id == "request-1"
    assert record.status == "success"
    assert record.callback_run_id == "callback-run"


@pytest.mark.parametrize(
    ("error", "status"),
    [(TimeoutError("slow"), "timeout"), (asyncio.CancelledError(), "cancelled")],
)
def test_diagnostics_classify_terminal_failures(
    error: BaseException,
    status: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    callback = langfuse._RuntimeDiagnosticsCallback("demo", {})
    with caplog.at_level("INFO"):
        callback.on_chain_start({}, {}, run_id=f"callback-{status}")
        callback.on_chain_error(error, run_id=f"callback-{status}")
    assert any(record.status == status for record in caplog.records)


def test_diagnostics_count_tool_error_and_tokens(caplog: pytest.LogCaptureFixture) -> None:
    callback = langfuse._RuntimeDiagnosticsCallback(
        "demo", {"run_id": "run-1", "thread_id": "thread-1"}
    )
    before = langfuse.get_observability_metrics()
    with caplog.at_level("WARNING"):
        callback.on_tool_error(ValueError("bad input"), run_id="tool-run", name="read_reference")
    callback.on_llm_end(type("Response", (), {"llm_output": {"token_usage": {"total_tokens": 3}}})(), run_id="llm-run")
    after = langfuse.get_observability_metrics()
    assert after["tool_error"] == before.get("tool_error", 0) + 1
    assert after["token_total"] == before.get("token_total", 0) + 3
    record = next(item for item in caplog.records if item.message == "runtime_tool_error")
    assert record.error_category == "ValueError"
    assert record.tool_name == "read_reference"


def test_sensitive_values_are_redacted_and_long_content_is_dropped() -> None:
    assert langfuse._redact({"Authorization": "Bearer secret", "nested": {"password": "x"}}) == {
        "Authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }
    assert langfuse._mask(data="private prompt") == "[REDACTED]"
    assert langfuse._redact("x" * 257) == "[REDACTED]"
    assert langfuse._mask(data={"args": "x" * 257}) == {"args": "[REDACTED]"}


def test_callback_failure_is_fail_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _Graph()

    def fail() -> object:
        raise OSError("Langfuse unavailable")

    monkeypatch.setattr(langfuse, "_new_callback", fail)
    assert langfuse.with_langfuse_tracing(graph, {}, graph_id="demo") is graph  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (type("HttpError", (RuntimeError,), {"status_code": 401})(), "unauthorized"),
        (type("HttpError", (RuntimeError,), {"status_code": 429})(), "rate_limited"),
        (type("HttpError", (RuntimeError,), {"status_code": 503})(), "upstream_5xx"),
        (TimeoutError("export timeout"), "timeout"),
    ],
)
def test_export_failure_matrix_records_stable_drop_metric(
    error: BaseException,
    category: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    before = langfuse.get_observability_metrics().get("event_dropped", 0)
    with caplog.at_level("WARNING"):
        langfuse._record_export_error(error)
    assert langfuse.get_observability_metrics()["event_dropped"] == before + 1
    record = next(
        item for item in caplog.records if item.message == "runtime_langfuse_event_dropped"
    )
    assert record.error_category == category


def test_sdk_queue_saturation_drops_without_blocking_run(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _BlockingExporter(SpanExporter):
        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            self.started.set()
            self.release.wait(2.0)
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            self.release.set()

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            self.release.set()
            return True

    monkeypatch.setenv("OTEL_BSP_MAX_QUEUE_SIZE", "2")
    exporter = _BlockingExporter()
    processor = LangfuseSpanProcessor(
        public_key="public",
        secret_key="secret",
        base_url="https://langfuse.invalid",
        span_exporter=exporter,
        flush_at=1,
        flush_interval=60,
        should_export_span=lambda _: True,
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("runtime-test")
    try:
        tracer.start_span("first").end()
        assert exporter.started.wait(1.0)
        with caplog.at_level("WARNING"):
            started = time.monotonic()
            for index in range(16):
                tracer.start_span(f"queued-{index}").end()
            elapsed = time.monotonic() - started
        assert elapsed < 0.2
        assert any("Queue full, dropping Span" in record.message for record in caplog.records)
    finally:
        exporter.release.set()
        processor.shutdown()


def test_otlp_http_exports_bounded_root_span_to_independent_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received = threading.Event()
    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            assert self.rfile.read(length)
            paths.append(self.path)
            received.set()
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        f"http://127.0.0.1:{server.server_port}/v1/traces",
    )
    monkeypatch.setenv("OTEL_BSP_MAX_QUEUE_SIZE", "8")
    monkeypatch.setenv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE", "4")
    monkeypatch.setenv("OTEL_BSP_SCHEDULE_DELAY", "60")
    try:
        provider = otel.initialize_otel(on_error=langfuse._record_export_error)
        assert provider is not None
        callback = otel.OTelDiagnosticsCallback(
            provider,
            "workflow_demo",
            {"run_id": "run-otel", "thread_id": "thread-otel"},
        )
        callback.on_chain_start({}, {}, run_id="callback-otel")
        callback.on_chain_end({}, run_id="callback-otel")
        assert provider.force_flush(5_000)
        assert received.wait(5)
        assert paths == ["/v1/traces"]
    finally:
        otel.close_otel(timeout_seconds=5)
        server.shutdown()
        server.server_close()


def test_otlp_http_503_is_recorded_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            received.set()
            self.send_response(503)
            self.end_headers()

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        f"http://127.0.0.1:{server.server_port}/v1/traces",
    )
    monkeypatch.setenv("OTEL_BSP_MAX_QUEUE_SIZE", "8")
    monkeypatch.setenv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE", "4")
    before = langfuse.get_observability_metrics().get("event_dropped", 0)
    try:
        provider = otel.initialize_otel(on_error=langfuse._record_export_error)
        assert provider is not None
        callback = otel.OTelDiagnosticsCallback(provider, "failure_demo", {})
        callback.on_chain_start({}, {}, run_id="callback-503")
        callback.on_chain_end({}, run_id="callback-503")
        assert provider.force_flush(5_000)
        assert received.wait(5)
        assert langfuse.get_observability_metrics()["event_dropped"] >= before + 1
    finally:
        otel.close_otel(timeout_seconds=5)
        server.shutdown()
        server.server_close()


def test_concurrent_runs_keep_metadata_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langfuse, "_new_callback", lambda: object())
    results: list[dict[str, object]] = []

    def bind(thread_id: str) -> None:
        graph = _Graph()
        langfuse.with_langfuse_tracing(
            graph,  # type: ignore[arg-type]
            {"configurable": {"thread_id": thread_id}},
            graph_id="demo",
        )
        assert graph.bound is not None
        results.append(graph.bound["metadata"])  # type: ignore[arg-type]

    threads = [threading.Thread(target=bind, args=(f"thread-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert {item["thread_id"] for item in results} == {"thread-0", "thread-1"}  # type: ignore[index]


def test_close_flush_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Client:
        def flush(self) -> None:
            return None

    monkeypatch.setattr(langfuse, "_client", _Client())
    langfuse.close_langfuse(timeout_seconds=0.5)
    assert langfuse._client is None


def test_close_flush_timeout_is_fail_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SlowClient:
        def flush(self) -> None:
            time.sleep(0.1)

    monkeypatch.setattr(langfuse, "_client", _SlowClient())
    started = time.monotonic()
    langfuse.close_langfuse(timeout_seconds=0.001)
    assert time.monotonic() - started < 0.08
    assert langfuse._client is None
    assert langfuse.get_observability_metrics().get("flush_timeout", 0) >= 1


def test_close_flush_error_is_fail_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingClient:
        def flush(self) -> None:
            raise OSError("endpoint unavailable")

    before = langfuse.get_observability_metrics()
    monkeypatch.setattr(langfuse, "_client", _FailingClient())
    langfuse.close_langfuse(timeout_seconds=0.5)
    after = langfuse.get_observability_metrics()
    assert langfuse._client is None
    assert after["flush_error"] == before.get("flush_error", 0) + 1
    assert after["export_error"] == before.get("export_error", 0) + 1
    assert after["event_dropped"] == before.get("event_dropped", 0) + 1


def test_app_lifespan_owns_initialize_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime_service import webapp

    calls: list[str] = []
    monkeypatch.setattr(webapp, "initialize_langfuse", lambda: calls.append("start"))
    monkeypatch.setattr(webapp, "close_langfuse", lambda *, timeout_seconds: calls.append(f"close:{timeout_seconds}"))

    async def run() -> None:
        async with webapp.lifespan(webapp.app):
            calls.append("serve")

    asyncio.run(run())
    assert calls == ["start", "serve", "close:5.0"]


def test_app_lifespan_rejects_incomplete_explicit_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from runtime_service import webapp

    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    async def run() -> None:
        async with webapp.lifespan(webapp.app):
            raise AssertionError("lifespan must fail before serving")

    with pytest.raises(langfuse.LangfuseConfigurationError):
        asyncio.run(run())
