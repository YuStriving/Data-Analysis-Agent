from __future__ import annotations

from typing import Any

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import ToolCallError, ToolErrorCode


class ToolCallingException(Exception):
    def __init__(
        self,
        code: ToolErrorCode,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error = ToolCallError(
            code=code,
            message=message,
            detail=detail or {},
            retryable=retryable,
        )
