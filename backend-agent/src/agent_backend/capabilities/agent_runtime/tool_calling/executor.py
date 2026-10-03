from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    BusinessTool,
    ToolCallResult,
    ToolExecutionContext,
    ToolExecutionOptions,
)
from agent_backend.capabilities.agent_runtime.tool_calling.errors import (
    ToolCallError,
)
from agent_backend.capabilities.agent_runtime.tool_calling.validation import (
    validate_value,
)

AuthorizationCheck = Callable[
    [BusinessTool, dict[str, Any], ToolExecutionContext], None
]


def run_authorization_check(
    authorize: AuthorizationCheck,
    tool: BusinessTool,
    args: dict[str, Any],
    context: ToolExecutionContext,
) -> None:
    """Require the synchronous allow-or-raise authorization contract."""
    decision = authorize(tool, args, context)
    if decision is not None:
        if inspect.iscoroutine(decision):
            decision.close()
        raise ToolCallError(
            "Invalid authorization check",
            "Authorization checks must synchronously return None or raise ToolCallError.",
        )


class ToolExecutor:
    """Own the tool execution lifecycle; inject business tools and policies."""

    def __init__(
        self,
        *,
        options: ToolExecutionOptions,
        authorize: AuthorizationCheck,
    ) -> None:
        if not callable(authorize):
            raise TypeError("ToolExecutor requires an authorization check")
        self.options = options
        self.authorize = authorize

    async def execute(
        self,
        tool: BusinessTool,
        raw_input: dict[str, Any] | BaseModel,
        context: ToolExecutionContext,
    ) -> ToolCallResult:
        try:
            options = self.options
            if context.tool_version != options.version:
                raise ToolCallError(
                    "Tool version mismatch",
                    "Context and execution options must use the same tool version.",
                )
            timeout_ms = context.timeout_ms or options.timeout_ms
            args = self._parse(raw_input)
            validate_value(tool.input_args, args, "Invalid tool input")
            run_authorization_check(self.authorize, tool, args, context)
            try:
                data = await asyncio.wait_for(
                    self._invoke(tool, args, context),
                    timeout=timeout_ms / 1000,
                )
            except TimeoutError as exc:
                raise ToolCallError(
                    "Tool execution timed out",
                    "Tool execution timed out.",
                    retryable=True,
                    detail={"timeout_ms": timeout_ms},
                ) from exc
            try:
                if isinstance(data, BaseModel):
                    data = data.model_dump(mode="json")
                if data is None:
                    raise ToolCallError(
                        "Invalid tool output",
                        "Successful tool output must not be None.",
                    )
                validate_value(options.output_schema, data, "Invalid tool output")
                json.dumps(data, allow_nan=False)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ToolCallError(
                    "Invalid tool output", "Tool output must be JSON serializable."
                ) from exc
            return ToolCallResult(
                tool_call_id=context.tool_call_id,
                tool_name=tool.name,
                tool_version=options.version,
                data=data,
            )
        except ToolCallError:
            raise
        except (
            Exception
        ) as exc:  # Normalize business failures at the execution boundary.
            raise ToolCallError(
                "Tool execution failed",
                str(exc),
                detail={"exception_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _parse(raw_input: dict[str, Any] | BaseModel) -> dict[str, Any]:
        try:
            args = (
                raw_input.model_dump(mode="json")
                if isinstance(raw_input, BaseModel)
                else raw_input
            )
        except (TypeError, ValueError) as exc:
            raise ToolCallError("Invalid tool input", str(exc)) from exc
        if not isinstance(args, dict) or any(not isinstance(key, str) for key in args):
            raise ToolCallError(
                "Invalid tool input", "Tool input must be an object with string keys."
            )
        return args

    async def _invoke(
        self,
        tool: BusinessTool,
        args: dict[str, Any],
        context: ToolExecutionContext,
    ) -> Any:
        handler = tool.execute
        if inspect.iscoroutinefunction(handler):
            return await handler(args, context)
        result = await asyncio.to_thread(handler, args, context)
        return await result if inspect.isawaitable(result) else result
