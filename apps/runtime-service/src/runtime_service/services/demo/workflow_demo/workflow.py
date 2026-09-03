"""Deterministic StateGraph topology for the workflow demo."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from runtime_service.services.demo.workflow_demo.schemas import WorkflowState


def prepare(state: WorkflowState) -> dict[str, int]:
    return {"prepared_count": state.get("prepared_count", 0) + 1}


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


def approve(state: WorkflowState) -> dict[str, str]:
    return {"response": f"workflow approved: {state['message']}"}


def reject(state: WorkflowState) -> dict[str, str]:
    return {"response": f"workflow rejected: {state['message']}"}


def respond(state: WorkflowState) -> dict[str, str]:
    return {"response": f"workflow response: {state['message']}"}


def after_prepare(state: WorkflowState) -> Literal["confirm", "route"]:
    return "confirm" if state.get("requires_confirmation", False) else "route"


builder = StateGraph(WorkflowState)
builder.add_node("prepare", prepare)
builder.add_node("confirm", confirm)
builder.add_node("route", select_route)
builder.add_node("approve", approve)
builder.add_node("reject", reject)
builder.add_node("respond", respond)
builder.add_edge(START, "prepare")
builder.add_conditional_edges(
    "prepare",
    after_prepare,
    {"confirm": "confirm", "route": "route"},
)
builder.add_conditional_edges(
    "confirm",
    after_confirm,
    {"confirm": "confirm", "route": "route"},
)
builder.add_conditional_edges(
    "route",
    choose_route,
    {"approve": "approve", "reject": "reject", "respond": "respond"},
)
builder.add_edge("approve", END)
builder.add_edge("reject", END)
builder.add_edge("respond", END)
