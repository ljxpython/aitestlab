"""Read-only tools owned by the reference service."""

from langchain.tools import tool


@tool
def read_reference(topic: str) -> str:
    """Return a short reference note for a named topic."""

    return f"reference note: {topic.strip()}"


__all__ = ["read_reference"]
