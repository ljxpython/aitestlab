from __future__ import annotations

from collections.abc import Sequence

from langchain_core.language_models.fake_chat_models import FakeListChatModel, FakeMessagesListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class BindableFakeChatModel(FakeListChatModel):
    """Small test model that accepts tools without simulating tool calls."""

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


class BindableFakeMessagesChatModel(FakeMessagesListChatModel):
    """Test model that emits a fixed message through the real agent path."""

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


__all__ = ["BindableFakeChatModel", "BindableFakeMessagesChatModel"]
