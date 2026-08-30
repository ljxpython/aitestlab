"""Stable Runtime errors without sensitive payloads."""


class RuntimeErrorBase(ValueError):
    """Base error carrying only a stable code and optional field name."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        super().__init__(code)


class RuntimeResolutionError(RuntimeErrorBase):
    """Invalid Runtime contract or policy decision."""


class RuntimeAuthError(RuntimeErrorBase):
    """Invalid or unverifiable Runtime Delegation token."""
