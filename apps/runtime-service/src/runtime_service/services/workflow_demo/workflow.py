"""Deterministic StateGraph topology for the workflow demo."""

from langgraph.graph import END, START, StateGraph

from runtime_service.services.workflow_demo.schemas import WorkflowState


def respond(state: WorkflowState) -> dict[str, str]:
    return {"response": f"workflow response: {state['message']}"}


builder = StateGraph(WorkflowState)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)
