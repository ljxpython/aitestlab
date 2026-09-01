"""Spike-only graphs for HITL and multimodal checks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from langgraph.pregel import Pregel
from typing_extensions import TypedDict


class ApprovalState(TypedDict, total=False):
    approved: bool
    message: str


def _approval_node(state: ApprovalState) -> dict[str, Any]:
    answer = interrupt({"kind": "approval", "message": state.get("message", "approve")})
    return {"approved": bool(answer), "message": "approved" if answer else "rejected"}


def _finish_node(state: ApprovalState) -> dict[str, Any]:
    return {"message": state.get("message", "completed")}


_hitl_builder = StateGraph(ApprovalState)
_hitl_builder.add_node("approval", _approval_node)
_hitl_builder.add_node("finish", _finish_node)
_hitl_builder.add_edge(START, "approval")
_hitl_builder.add_edge("approval", "finish")
_hitl_builder.add_edge("finish", END)
hitl_graph: Pregel = _hitl_builder.compile(name="aegra_spike_hitl")


def _multimodal_model() -> ChatOpenAI:
    model = os.getenv("GPT_PROXY_DEFAULT_MODEL")
    base_url = os.getenv("GPT_PROXY_URL")
    api_key = os.getenv("GPT_PROXY_API_KEY")
    if not model or not base_url or not api_key:
        raise RuntimeError("GPT proxy settings are required for the multimodal spike")
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key)


async def get_multimodal_agent(config: RunnableConfig) -> Pregel:
    """Build a spike-only GPT multimodal agent from server-side environment settings."""

    del config
    return create_agent(
        model=_multimodal_model(),
        tools=[],
        system_prompt="Describe the supplied image in one sentence.",
        name="aegra_spike_multimodal",
    )


def _doubao_multimodal_model() -> ChatOpenAI:
    model = os.getenv("DOUBAO_MODEL")
    base_url = os.getenv("DOUBAO_API_BASE")
    api_key = os.getenv("DOUBAO_API_KEY")
    if not model or not base_url or not api_key:
        raise RuntimeError("Doubao settings are required for the multimodal spike")
    max_tokens = os.getenv("DOUBAO_MAX_TOKENS")
    kwargs: dict[str, Any] = {"model": model, "base_url": base_url, "api_key": api_key}
    if max_tokens:
        kwargs["max_tokens"] = int(max_tokens)
    return ChatOpenAI(**kwargs)


async def get_doubao_multimodal_agent(config: RunnableConfig) -> Pregel:
    """Build a spike-only Doubao vision agent from server-side settings."""

    del config
    return create_agent(
        model=_doubao_multimodal_model(),
        tools=[],
        system_prompt="Describe the supplied image in one sentence.",
        name="aegra_spike_doubao_multimodal",
    )


class WorkspaceState(TypedDict, total=False):
    marker: str
    path: str


def _workspace_node(state: WorkspaceState, config: RunnableConfig) -> dict[str, str]:
    """Write a marker under the server-authoritative thread scope."""

    thread_id = str((config.get("configurable") or {}).get("thread_id", "missing"))
    root = Path(os.getenv("AEGRA_SPIKE_WORKSPACE_ROOT", "/tmp/aegra-spike-workspaces"))
    path = root / thread_id / "marker.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.get("marker", thread_id), encoding="utf-8")
    return {"path": str(path)}


_workspace_builder = StateGraph(WorkspaceState)
_workspace_builder.add_node("workspace", _workspace_node)
_workspace_builder.add_edge(START, "workspace")
_workspace_builder.add_edge("workspace", END)
workspace_graph: Pregel = _workspace_builder.compile(name="aegra_spike_workspace")


class ReplayState(TypedDict, total=False):
    message: str
    first: str
    second: str


def _replay_first(state: ReplayState) -> dict[str, str]:
    return {"first": f"first:{state.get('message', '')}"}


def _replay_second(state: ReplayState) -> dict[str, str]:
    return {"second": f"second:{state.get('first', '')}"}


_replay_builder = StateGraph(ReplayState)
_replay_builder.add_node("first", _replay_first)
_replay_builder.add_node("second", _replay_second)
_replay_builder.add_edge(START, "first")
_replay_builder.add_edge("first", "second")
_replay_builder.add_edge("second", END)
replay_graph: Pregel = _replay_builder.compile(name="aegra_spike_replay")
