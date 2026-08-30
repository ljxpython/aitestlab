"""State schema owned by the workflow demo."""

from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    message: str
    response: str
