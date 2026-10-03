from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest
from pydantic import BaseModel, RootModel, field_serializer

from agent_backend.capabilities.agent_runtime import tool_calling
from agent_backend.capabilities.agent_runtime.execution_control import (
    AgentSpec,
    NodeSpec,
    ToolAccessPolicy,
    ToolAuthorizationGate,
)


def build_executor(
    *, options: tool_calling.ToolExecutionOptions | None = None, authorize: Any = None
) -> tool_calling.ToolExecutor:
    spec = AgentSpec(
        agent_id="test_agent",
        entry_node="run",
        terminal_nodes={"run"},
        node_specs={
            "run": NodeSpec(node_id="run", allowed_tools={"text.upper", "thread.id"})
        },
        edge_specs=[],
    )
    gate = ToolAuthorizationGate(
        agent_spec_resolver=lambda name, version: spec,
        policy_resolver=lambda name, version: ToolAccessPolicy(),
    )
    return tool_calling.ToolExecutor(
        options=options or tool_calling.ToolExecutionOptions(),
        authorize=authorize or gate.check,
    )


def context(**overrides: Any) -> tool_calling.ToolExecutionContext:
    values = {
        "agent_name": "test_agent",
        "agent_version": "v1",
        "task_id": "task-1",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "node_id": "run",
        "goal": "Format the report",
        "purpose": "Uppercase the input text",
        "timeout_ms": 1000,
    }
    values.update(overrides)
    return tool_calling.ToolExecutionContext(**values)


class UpperTool:
    name = "text.upper"
    description = "Format business text."

    def __init__(self, prefix: str = "") -> None:
        self.input_args = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        }
        self.prefix = prefix
        self.calls = 0
        self.received_context: tool_calling.ToolExecutionContext | None = None

    def execute(
        self, args: dict[str, Any], execution_context: tool_calling.ToolExecutionContext
    ) -> str:
        self.calls += 1
        self.received_context = execution_context
        return self.prefix + args["text"].upper()


def test_executor_returns_a_structured_result_and_passes_context_to_business() -> None:
    tool = UpperTool(prefix="business:")
    execution_context = context(tool_call_id="call-1")
    executor = build_executor()

    result = asyncio.run(executor.execute(tool, {"text": "hello"}, execution_context))

    assert isinstance(result, tool_calling.ToolCallResult)
    assert result.data == "business:HELLO"
    assert result.tool_name == "text.upper"
    assert result.tool_version == "v1"
    assert result.tool_call_id == "call-1"
    assert tool.received_context is execution_context


def test_executor_accepts_pydantic_input_and_generates_a_call_id() -> None:
    class TextInput(BaseModel):
        text: str

    execution_context = context()
    result = asyncio.run(
        build_executor().execute(
            UpperTool(), TextInput(text="hello"), execution_context
        )
    )

    assert result.data == "HELLO"
    assert result.tool_call_id
    assert result.tool_call_id == execution_context.tool_call_id


def test_executor_rejects_invalid_input_without_running_business() -> None:
    tool = UpperTool()
    executor = build_executor()

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(executor.execute(tool, {"text": 123}, context()))

    assert caught.value.reason == "Invalid tool input"
    assert caught.value.detail["path"] == "text"
    assert tool.calls == 0


def test_executor_rejects_invalid_output() -> None:
    class InvalidOutputTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> Any:
            return 123

    executor = build_executor(
        options=tool_calling.ToolExecutionOptions(output_schema={"type": "string"})
    )
    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(executor.execute(InvalidOutputTool(), {"text": "hello"}, context()))

    assert caught.value.reason == "Invalid tool output"
    assert not caught.value.retryable


@pytest.mark.parametrize("raw_input", [RootModel[list[str]](["hello"]), {1: "hello"}])
def test_executor_raises_for_malformed_input_without_running_business(
    raw_input: Any,
) -> None:
    tool = UpperTool()
    executor = build_executor()

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(executor.execute(tool, raw_input, context()))

    assert caught.value.reason == "Invalid tool input"
    assert tool.calls == 0


def test_executor_awaits_an_async_business_tool() -> None:
    class AsyncUpperTool(UpperTool):
        async def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> str:
            await asyncio.sleep(0)
            return args["text"].upper()

    result = asyncio.run(
        build_executor().execute(AsyncUpperTool(), {"text": "hello"}, context())
    )
    assert result.data == "HELLO"


def test_executor_awaits_a_coroutine_returned_by_a_sync_execute_method() -> None:
    class CoroutineUpperTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> Any:
            async def upper() -> str:
                return args["text"].upper()

            return upper()

    result = asyncio.run(
        build_executor().execute(CoroutineUpperTool(), {"text": "hello"}, context())
    )
    assert result.data == "HELLO"


def test_executor_runs_sync_business_tools_outside_the_event_loop_thread() -> None:
    class ThreadTool(UpperTool):
        name = "thread.id"
        description = "Read execution thread."

        def __init__(self) -> None:
            self.input_args = {}

        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> int:
            return threading.get_ident()

    async def run() -> None:
        result = await build_executor().execute(ThreadTool(), {}, context())
        assert result.data != threading.get_ident()

    asyncio.run(run())


def test_executor_wraps_business_errors_and_preserves_the_cause() -> None:
    original = ValueError("Business tool failed.")

    class FailingTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> None:
            raise original

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor().execute(FailingTool(), {"text": "hello"}, context())
        )

    assert caught.value.reason == "Tool execution failed"
    assert caught.value.message == "Business tool failed."
    assert caught.value.detail == {"exception_type": "ValueError"}
    assert caught.value.__cause__ is original


def test_executor_rejects_version_mismatch_before_running_business() -> None:
    tool = UpperTool()
    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor().execute(
                tool, {"text": "hello"}, context(tool_version="v2")
            )
        )
    assert caught.value.reason == "Tool version mismatch"
    assert tool.calls == 0


def test_executor_preserves_typed_business_errors() -> None:
    original = tool_calling.ToolCallError(
        "Business rule rejected",
        "Rejected by business rule.",
        retryable=True,
        detail={"rule": "quota", "remaining": 0},
    )

    class RejectedTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> None:
            raise original

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor().execute(RejectedTool(), {"text": "hello"}, context())
        )

    assert caught.value is original
    assert caught.value.to_payload() == {
        "reason": "Business rule rejected",
        "message": "Rejected by business rule.",
        "retryable": True,
        "detail": {"rule": "quota", "remaining": 0},
    }


def test_executor_times_out_and_cancels_async_business_execution() -> None:
    cancelled = []

    class SlowTool(UpperTool):
        async def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> str:
            try:
                await asyncio.sleep(1)
                return "late"
            finally:
                cancelled.append(True)

    executor = build_executor()
    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            executor.execute(SlowTool(), {"text": "hello"}, context(timeout_ms=1))
        )

    assert caught.value.reason == "Tool execution timed out"
    assert caught.value.retryable
    assert cancelled == [True]


def test_executor_preserves_cancellation() -> None:
    class CancelledTool(UpperTool):
        async def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> str:
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            build_executor().execute(CancelledTool(), {"text": "hello"}, context())
        )


def test_executor_raises_invalid_input_for_the_calling_event_boundary() -> None:
    tool = UpperTool()

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(build_executor().execute(tool, {"text": 123}, context()))

    assert caught.value.reason == "Invalid tool input"
    assert caught.value.message
    assert not caught.value.retryable
    assert caught.value.detail["path"] == "text"
    assert tool.calls == 0


def test_executor_preserves_injected_policy_rejection_before_business_execution() -> (
    None
):
    original = tool_calling.ToolCallError(
        "Missing permissions", "Access denied.", detail={"missing": ["read"]}
    )
    tool = UpperTool()

    def reject_policy(
        business_tool: tool_calling.BusinessTool,
        args: dict[str, Any],
        execution_context: tool_calling.ToolExecutionContext,
    ) -> None:
        raise original

    executor = build_executor(authorize=reject_policy)

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(executor.execute(tool, {"text": "hello"}, context()))

    assert caught.value is original
    assert tool.calls == 0


def test_tool_call_error_default_payload_can_be_sent_by_the_calling_event_boundary() -> (
    None
):
    error = tool_calling.ToolCallError("Business rule rejected", "Quota exhausted.")

    assert str(error) == "Quota exhausted."
    assert error.to_payload() == {
        "reason": "Business rule rejected",
        "message": "Quota exhausted.",
        "retryable": False,
        "detail": {},
    }


@pytest.mark.parametrize(
    "output", [None, object(), {"value": object()}, float("nan"), float("inf")]
)
def test_executor_rejects_non_json_outputs(output: Any) -> None:
    class OutputTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> Any:
            return output

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor().execute(OutputTool(), {"text": "hello"}, context())
        )
    assert caught.value.reason == "Invalid tool output"


def test_request_preserves_concrete_context_and_serialized_fields() -> None:
    class ReportContext(tool_calling.ToolExecutionContext):
        report_type: str

    supplied = ReportContext(**context().model_dump(), report_type="sales")
    request = tool_calling.ToolCallRequest(
        tool_name="text.upper", args={"text": "hello"}, context=supplied
    )
    assert request.context is supplied
    assert request.model_dump()["context"]["report_type"] == "sales"
    received = []

    def authorize(
        tool: tool_calling.BusinessTool,
        args: dict[str, Any],
        execution_context: tool_calling.ToolExecutionContext,
    ) -> None:
        received.append(execution_context)
        assert execution_context.goal == "Format the report"
        assert execution_context.purpose == "Uppercase the input text"

    tool = UpperTool()
    asyncio.run(
        build_executor(authorize=authorize).execute(tool, request.args, request.context)
    )
    assert received == [supplied]
    assert tool.received_context is supplied


def test_executor_classifies_model_serialization_failure_as_invalid_output() -> None:
    class Output(BaseModel):
        text: str

        @field_serializer("text")
        def serialize_text(self, value: str) -> str:
            raise ValueError("Cannot serialize this output.")

    class OutputTool(UpperTool):
        def execute(
            self,
            args: dict[str, Any],
            execution_context: tool_calling.ToolExecutionContext,
        ) -> Output:
            return Output(text="hello")

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor().execute(OutputTool(), {"text": "hello"}, context())
        )
    assert caught.value.reason == "Invalid tool output"


@pytest.mark.parametrize("decision", [False, True])
def test_executor_rejects_invalid_authorization_return_before_execution(
    decision: bool,
) -> None:
    tool = UpperTool()
    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor(authorize=lambda tool, args, context: decision).execute(
                tool, {"text": "hello"}, context()
            )
        )
    assert caught.value.reason == "Invalid authorization check"
    assert tool.calls == 0


def test_executor_rejects_async_authorization_without_running_business() -> None:
    tool = UpperTool()

    async def authorize(
        tool: tool_calling.BusinessTool,
        args: dict[str, Any],
        execution_context: tool_calling.ToolExecutionContext,
    ) -> None:
        raise tool_calling.ToolCallError("Missing permissions", "Access denied.")

    with pytest.raises(tool_calling.ToolCallError) as caught:
        asyncio.run(
            build_executor(authorize=authorize).execute(
                tool, {"text": "hello"}, context()
            )
        )
    assert caught.value.reason == "Invalid authorization check"
    assert tool.calls == 0
