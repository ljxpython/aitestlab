from __future__ import annotations

import threading

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


def test_binding_merges_config_and_trusted_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _Graph()
    callback = object()
    monkeypatch.setattr(langfuse, "_new_callback", lambda: callback)
    bound = langfuse.with_langfuse_tracing(
        graph,  # type: ignore[arg-type]
        {
            "callbacks": ["caller"],
            "metadata": {"request_id": "req", "user_id": "attacker", "custom": "kept"},
            "tags": ["caller"],
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
        "custom": "kept",
        "thread_id": "thread-1",
        "graph_id": "demo",
        "tenant_id": "tenant-1",
        "langfuse_trace_name": "demo",
        "langfuse_session_id": "thread-1",
        "langfuse_user_id": "trusted",
        "langfuse_tags": ["runtime-service", "demo"],
    }
    assert graph.bound["tags"] == ["caller", "runtime-service", "demo"]


def test_sensitive_values_are_redacted_and_long_content_is_dropped() -> None:
    assert langfuse._redact({"Authorization": "Bearer secret", "nested": {"password": "x"}}) == {
        "Authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }
    assert langfuse._mask(data="private prompt") == "[REDACTED]"
    assert langfuse._redact("x" * 257) == "[REDACTED]"


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
