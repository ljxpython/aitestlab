"""Workflow StateGraph topology around the model-backed Agent."""

from collections.abc import Mapping
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables.config import var_child_runnable_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from runtime_service.runtime.contracts import RuntimeContext
from runtime_service.services.demo.workflow_demo.schemas import WorkflowState


def _message_text(value: object) -> str:
    if isinstance(value, Mapping):
        content = value.get("content")
    else:
        content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and isinstance(block.get("text"), str)
        )
    return "" if content is None else str(content)


def _is_user_message(value: object) -> bool:
    if isinstance(value, Mapping):
        return value.get("type") in {"human", "user"} or value.get("role") in {
            "human",
            "user",
        }
    return getattr(value, "type", None) in {"human", "user"} or getattr(
        value, "role", None
    ) in {"human", "user"}


def prepare(state: WorkflowState) -> dict[str, object]:
    message = state.get("message", "").strip()
    for candidate in reversed(state.get("messages", [])):
        if _is_user_message(candidate):
            latest_message = _message_text(candidate).strip()
            if latest_message:
                message = latest_message
                break
    return {
        "prepared_count": state.get("prepared_count", 0) + 1,
        "message": message,
    }


def confirm(state: WorkflowState) -> dict[str, object]:
    decision = interrupt(
        {
            "kind": "workflow_confirmation",
            "message": state["message"],
            "allowed_decisions": ["approve", "reject"],
            "error": state.get("resume_error"),
        }
    )
    if not isinstance(decision, str) or decision not in {"approve", "reject"}:
        return {"resume_error": "workflow.invalid_resume"}
    return {"confirmation": decision, "resume_error": None}


def select_route(state: WorkflowState) -> dict[str, Literal["approve", "reject", "respond"]]:
    return {"route": state.get("confirmation") or state.get("route", "respond")}


def choose_route(state: WorkflowState) -> Literal["approve", "reject", "respond"]:
    return state["route"]


def after_confirm(state: WorkflowState) -> Literal["confirm", "route"]:
    return "confirm" if state.get("resume_error") else "route"


def approve(state: WorkflowState) -> dict[str, object]:
    response = f"workflow approved: {state['message']}"
    return {"response": response, "messages": [AIMessage(content=response)]}


def reject(state: WorkflowState) -> dict[str, object]:
    response = f"workflow rejected: {state['message']}"
    return {"response": response, "messages": [AIMessage(content=response)]}


def build_graph(
    model_agent: object,
    *,
    model_config: Mapping[str, object] | None = None,
    runtime_context: RuntimeContext | None = None,
):
    async def respond(state: WorkflowState, runtime) -> dict[str, object]:
        messages = state.get("messages", [])
        if not messages and state.get("message"):
            messages = [{"role": "user", "content": state["message"]}]
        invoke_config = dict(model_config or {})
        current_config = var_child_runnable_config.get() or {}
        invoke_config.update(current_config)
        if model_config is not None:
            configurable = dict(model_config.get("configurable") or {})
            configurable.update(current_config.get("configurable") or {})
            invoke_config["configurable"] = configurable
        result = await model_agent.ainvoke(  # type: ignore[attr-defined]
            {"messages": messages},
            config=invoke_config,
            # The outer GraphHarbor runtime may omit Context when entering a
            # nested graph. Keep the signed, resolved context for the inner
            # model middleware so its context hash remains consistent.
            context=runtime_context or runtime.context,
        )
        response_message = result["messages"][-1]
        response = _message_text(response_message).strip()
        return {"response": response, "messages": [response_message]}

    def after_prepare(state: WorkflowState) -> Literal["confirm", "route"]:
        return "confirm" if state.get("requires_confirmation", False) else "route"

    graph = StateGraph(WorkflowState)
    graph.add_node("prepare", prepare)
    graph.add_node("confirm", confirm)
    graph.add_node("route", select_route)
    graph.add_node("approve", approve)
    graph.add_node("reject", reject)
    graph.add_node("respond", respond)
    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        after_prepare,
        {"confirm": "confirm", "route": "route"},
    )
    graph.add_conditional_edges(
        "confirm",
        after_confirm,
        {"confirm": "confirm", "route": "route"},
    )
    graph.add_conditional_edges(
        "route",
        choose_route,
        {"approve": "approve", "reject": "reject", "respond": "respond"},
    )
    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=InMemorySaver())
