from __future__ import annotations

import pytest

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    resolve_runtime_config,
)
from runtime_service.runtime import modeling


def _resolved(model_id: str):
    return resolve_runtime_config(
        principal=RuntimePrincipal("u", "t", "p", "developer", ()),
        context=RuntimeContext(),
        policy=RuntimePolicy("p1", (model_id,), ()),
        defaults=AgentDefaults(
            model_id=model_id,
            system_prompt="prompt",
            prompt_version="v1",
            temperature=0,
            max_tokens=100,
        ),
    )


def test_build_deepseek_uses_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_constructor)
    model = modeling.build_model(
        _resolved("deepseek:deepseek-chat"),
        env={"DEEPSEEK_PROXY_API_KEY": "key", "DEEPSEEK_PROXY_URL": "https://deepseek.test/v1"},
    )

    assert model is not None
    assert calls["model"] == "deepseek-chat"
    assert calls["api_key"] == "key"
    assert calls["base_url"] == "https://deepseek.test/v1"
    assert calls["temperature"] == 0.0


def test_build_openai_uses_gpt_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatOpenAI", fake_constructor)
    modeling.build_model(
        _resolved("openai:gpt-5.5"),
        env={"GPT_PROXY_API_KEY": "key", "GPT_PROXY_URL": "https://gpt.test/v1"},
    )

    assert calls["model"] == "gpt-5.5"
    assert calls["api_key"] == "key"
    assert calls["base_url"] == "https://gpt.test/v1"


def test_build_model_uses_catalog_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_constructor)
    modeling.build_model(
        _resolved("deepseek:catalog-chat"),
        env={},
        connection={
            "provider": "deepseek",
            "base_url": "https://catalog.test/v1",
            "protocol": "deepseek",
            "model": "catalog-chat",
            "api_key": "catalog-key",
        },
    )
    assert calls["api_key"] == "catalog-key"
    assert calls["base_url"] == "https://catalog.test/v1"


def test_build_model_rejects_missing_provider_settings() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        modeling.build_model(_resolved("deepseek:deepseek-chat"), env={})
    assert error.value.code == "runtime.model.initialization_failed"


def test_build_model_uses_standard_initializer_for_other_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_initializer(model: str, **kwargs: object) -> object:
        calls["model"] = model
        calls["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(modeling, "init_chat_model", fake_initializer)
    modeling.build_model(_resolved("anthropic:claude-sonnet"), env={})
    assert calls == {"model": "anthropic:claude-sonnet", "kwargs": {"temperature": 0.0, "max_tokens": 100}}


def test_build_model_does_not_accept_raw_context() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        modeling.build_model(RuntimeContext())  # type: ignore[arg-type]
    assert error.value.code == "runtime.model.invalid_config"
