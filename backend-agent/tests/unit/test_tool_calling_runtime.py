from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from pydantic import ValidationError

from agent_backend.capabilities.agent_runtime.tool_calling import (
    DatasetScope,
    ToolCallRequest,
    ToolCallResult,
    ToolCallingRuntime,
    ToolDefinition,
    ToolErrorCode,
    ToolRegistry,
    ToolStatus,
)


class EchoTool:
    def __init__(self, *, output: dict[str, Any] | None = None, delay: float = 0) -> None:
        self.output = output or {"ok": True, "row_count": 1, "truncated": False, "rows": [{"secret": "sample"}], "columns": []}
        self.delay = delay

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="test.echo_query_executor",
            version="v1",
            description="Echo test tool.",
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}, "sql": {"type": "string"}},
                "required": ["dataset_id", "sql"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "row_count": {"type": "integer"}, "truncated": {"type": "boolean"}},
                "required": ["ok", "row_count", "truncated"],
            },
            allowed_agents=["data_analysis_agent"],
            allowed_nodes=["execute_sql"],
            supported_dataset_types=["mysql"],
            required_permissions=["dataset:read", "query:execute"],
            timeout_ms=1000,
        )

    def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        if self.delay:
            time.sleep(self.delay)
        return self.output


def request(**overrides: Any) -> ToolCallRequest:
    payload = {
        "tool_call_id": "call-1",
        "tool_name": "test.echo_query_executor",
        "tool_version": "v1",
        "agent_name": "data_analysis_agent",
        "agent_version": "v1",
        "node_id": "execute_sql",
        "task_id": "task-1",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "dataset_scope": DatasetScope(
            selected_dataset_id="dataset-1",
            allowed_dataset_ids=["dataset-1"],
            dataset_types={"dataset-1": "mysql"},
            permissions=["dataset:read", "query:execute"],
        ),
        "args": {"dataset_id": "dataset-1", "sql": "SELECT * FROM sales"},
        "timeout_ms": 1000,
    }
    payload.update(overrides)
    return ToolCallRequest(**payload)


def test_result_shape_requires_data_on_success() -> None:
    with pytest.raises(ValidationError):
        ToolCallResult(
            tool_call_id="call-1",
            tool_name="tool",
            tool_version="v1",
            success=True,
            status=ToolStatus.SUCCEEDED,
            data=None,
        )


def test_registry_gets_tool_by_name_and_version() -> None:
    registry = ToolRegistry([EchoTool()])

    assert registry.get("test.echo_query_executor", "v1").definition().name == "test.echo_query_executor"


def test_runtime_success_records_started_and_finished_events() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([EchoTool()]))

    result = asyncio.run(runtime.call(request()))

    assert result.success
    assert result.status == ToolStatus.SUCCEEDED
    assert [event["event_type"] for event in runtime.logger.events] == ["tool_call_started", "tool_call_finished"]
    assert runtime.logger.events[-1]["row_count"] == 1
    assert runtime.logger.events[-1]["output_summary"]["sample_rows"] == [{"secret": "sample"}]


def test_runtime_returns_validation_failed_for_missing_tool() -> None:
    runtime = ToolCallingRuntime(ToolRegistry())

    result = asyncio.run(runtime.call(request(tool_name="missing.tool")))

    assert not result.success
    assert result.status == ToolStatus.VALIDATION_FAILED
    assert result.error is not None
    assert result.error.code == ToolErrorCode.TOOL_NOT_FOUND
    assert runtime.logger.events[0]["event_type"] == "tool_call_started"


def test_runtime_rejects_agent_permission() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([EchoTool()]))

    result = asyncio.run(runtime.call(request(agent_name="other_agent")))

    assert not result.success
    assert result.status == ToolStatus.PERMISSION_DENIED
    assert result.error is not None
    assert result.error.code == ToolErrorCode.TOOL_AGENT_NOT_ALLOWED


def test_runtime_rejects_dataset_scope() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([EchoTool()]))
    scope = DatasetScope(
        selected_dataset_id="dataset-1",
        allowed_dataset_ids=["dataset-2"],
        dataset_types={"dataset-1": "mysql"},
        permissions=["dataset:read", "query:execute"],
    )

    result = asyncio.run(runtime.call(request(dataset_scope=scope)))

    assert not result.success
    assert result.error is not None
    assert result.error.code == ToolErrorCode.TOOL_DATASET_NOT_ALLOWED


def test_runtime_rejects_guardrail_failure() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([EchoTool()]))

    result = asyncio.run(runtime.call(request(args={"dataset_id": "dataset-1", "sql": "DELETE FROM sales"})))

    assert not result.success
    assert result.status == ToolStatus.GUARDRAIL_REJECTED
    assert result.error is not None
    assert result.error.code == ToolErrorCode.GUARDRAIL_REJECTED
    assert not result.error.retryable


def test_runtime_times_out_slow_tool() -> None:
    runtime = ToolCallingRuntime(ToolRegistry([EchoTool(delay=0.05)]))

    result = asyncio.run(runtime.call(request(timeout_ms=1)))

    assert not result.success
    assert result.status == ToolStatus.TIMEOUT
    assert result.error is not None
    assert result.error.retryable
