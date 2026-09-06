"""State schema owned by the workflow demo."""

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


MessageValue = Annotated[list[object], add_messages]


class WorkflowState(TypedDict, total=False):
    messages: MessageValue
    message: str
    route: Literal["approve", "reject", "respond"]
    requires_confirmation: bool
    confirmation: Literal["approve", "reject"]
    resume_error: str | None
    prepared_count: int
    response: str
