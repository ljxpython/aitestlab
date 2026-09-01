from __future__ import annotations

import asyncio
import threading
import time

import pytest

from runtime_service.observability import langfuse


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
