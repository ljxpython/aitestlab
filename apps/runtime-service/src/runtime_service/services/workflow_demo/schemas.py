"""State schema owned by the workflow demo."""

from typing import Literal, TypedDict


class WorkflowState(TypedDict, total=False):
    message: str
    route: Literal["approve", "reject", "respond"]
    requires_confirmation: bool
    confirmation: Literal["approve", "reject"]
    resume_error: str | None
    prepared_count: int
    response: str
