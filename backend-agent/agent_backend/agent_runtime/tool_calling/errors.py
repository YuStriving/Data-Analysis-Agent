from __future__ import annotations

from typing import Any


class ToolCallError(Exception):
    """Tool failure information for callers and their event emitters."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.retryable = retryable
        self.detail = detail if detail is not None else {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "message": self.message,
            "retryable": self.retryable,
            "detail": self.detail,
        }
