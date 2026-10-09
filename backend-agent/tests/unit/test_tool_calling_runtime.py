from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from pydantic import ValidationError

from agent_backend.agent_runtime.execution_control import (
    AgentSpec,
    NodeSpec,
    ToolAuthorizationGate,
)
from agent_backend.agent_runtime.tool_calling import (
    BusinessTool,
    ToolCallError,
    ToolCallingRuntime,
    ToolCallRequest,
    ToolCallResult,
    ToolExecutionContext,
    ToolExecutionOptions,
    ToolRegistry,
)
from agent_backend.capabilities.data_analysis.tools.contracts import (
    DataAnalysisToolExecutionContext,
    DatasetScope,
)
from agent_backend.capabilities.data_analysis.tools.policy import (
    DataAnalysisToolAccessPolicy,
    DataAnalysisToolPolicyChecker,
    GuardrailsHook,
)


class EchoTool:
    def __init__(
        self, *, output: dict[str, Any] | None = None, delay: float = 0
    ) -> None:
        self.input_args = {
            "type": "object",
            "properties": {"dataset_id": {"type": "string"}, "sql": {"type": "string"}},
            "required": ["dataset_id", "sql"],
            "additionalProperties": False,
        }
        self.output = output or {
            "ok": True,
            "row_count": 1,
            "truncated": False,
            "rows": [{"secret": "sample"}],
            "columns": [],
        }
        self.delay = delay

    name = "test.echo_query_executor"
    description = "Echo test tool."

    def execute(
        self, args: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        if self.delay:
            time.sleep(self.delay)
        return self.output


def echo_runtime(
    registry: ToolRegistry, *, guardrails_hook: GuardrailsHook | None = None
) -> ToolCallingRuntime:
    policy = DataAnalysisToolAccessPolicy(
        allowed_agents=["data_analysis_agent"],
        allowed_nodes=["execute_sql"],
        supported_dataset_types=["mysql"],
        required_permissions=["dataset:read", "query:execute"],
        requires_readonly_sql=True,
    )
    checker = DataAnalysisToolPolicyChecker(
        {("test.echo_query_executor", version): policy for version in ("v1", "v2")},
        guardrails_hook=guardrails_hook,
    )
    spec = AgentSpec(
        agent_id="data_analysis_agent",
        entry_node="execute_sql",
        terminal_nodes={"execute_sql"},
        node_specs={
            "execute_sql": NodeSpec(
                node_id="execute_sql", allowed_tools={"test.echo_query_executor"}
            )
        },
        edge_specs=[],
    )
    gate = ToolAuthorizationGate(
        agent_spec_resolver=lambda name, version: spec,
        policy_resolver=checker.get_policy,
        business_check=checker.check,
    )
    return ToolCallingRuntime(
        registry, authorize=gate.check, access_policy_resolver=gate.get_policy
    )


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
        ),
        "args": {"dataset_id": "dataset-1", "sql": "SELECT * FROM sales"},
        "timeout_ms": 1000,
        "goal": "Analyze sales",
        "purpose": "Execute the readonly query",
        "permissions": ["dataset:read", "query:execute"],
    }
    payload.update(overrides)
    tool_name = payload.pop("tool_name")
    args = payload.pop("args")
    return ToolCallRequest(
        tool_name=tool_name,
        args=args,
        context=DataAnalysisToolExecutionContext(**payload),
    )


def test_result_requires_success_data() -> None:
    with pytest.raises(ValidationError):
        ToolCallResult(
            tool_call_id="call-1",
            tool_name="tool",
            tool_version="v1",
            data=None,
        )


def test_registry_gets_tool_by_name_and_version() -> None:
    tool = EchoTool()
    registry = ToolRegistry([tool])

    assert registry.get("test.echo_query_executor", "v1") is tool
    assert registry.list() == [tool]


def test_runtime_returns_business_data_and_call_identity() -> None:
    tool = EchoTool()
    runtime = echo_runtime(ToolRegistry([tool]))

    result = asyncio.run(runtime.call(request()))

    assert result.model_dump() == {
        "tool_call_id": "call-1",
        "tool_name": "test.echo_query_executor",
        "tool_version": "v1",
        "data": tool.output,
    }


def test_runtime_exposes_registered_business_tool_instances() -> None:
    tool = EchoTool()
    runtime = echo_runtime(ToolRegistry([tool]))

    assert runtime.get_tool("test.echo_query_executor", "v1") is tool
    assert runtime.list_tools("data_analysis_agent") == [tool]
    assert runtime.list_tools("other_agent") == []


@pytest.mark.parametrize(
    ("tool_name", "version", "expected_reason"),
    [
        ("missing.tool", "v1", "Tool not found"),
        ("test.echo_query_executor", "v2", "Tool version not found"),
    ],
)
def test_runtime_raises_for_registry_lookup_errors(
    tool_name: str,
    version: str,
    expected_reason: str,
) -> None:
    runtime = echo_runtime(ToolRegistry([EchoTool()]))

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request(tool_name=tool_name, tool_version=version)))

    assert caught.value.reason == expected_reason
    assert not caught.value.retryable


def test_runtime_executes_the_requested_tool_version() -> None:
    first = EchoTool(output={"ok": True, "row_count": 1, "truncated": False})
    second = EchoTool(output={"ok": True, "row_count": 2, "truncated": False})
    registry = ToolRegistry([first])
    registry.register(second, options=ToolExecutionOptions(version="v2"))
    runtime = echo_runtime(registry)

    first_result = asyncio.run(runtime.call(request(tool_version="v1")))
    second_result = asyncio.run(runtime.call(request(tool_version="v2")))

    assert first_result.data["row_count"] == 1
    assert first_result.tool_version == "v1"
    assert second_result.data["row_count"] == 2
    assert second_result.tool_version == "v2"


def test_runtime_executes_the_business_object_resolved_before_validation() -> None:
    original = EchoTool(output={"ok": True, "row_count": 1, "truncated": False})
    replacement = EchoTool(output={"ok": True, "row_count": 2, "truncated": False})
    registry = ToolRegistry([original])

    def replace_registration(
        tool: BusinessTool, args: dict[str, Any], context: ToolExecutionContext
    ) -> bool:
        registry.register(replacement)
        return True

    runtime = echo_runtime(registry, guardrails_hook=replace_registration)

    result = asyncio.run(runtime.call(request()))

    assert result.data["row_count"] == 1


def test_runtime_rejects_agent_permission() -> None:
    runtime = echo_runtime(ToolRegistry([EchoTool()]))

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request(agent_name="other_agent")))

    assert caught.value.reason == "Agent not allowed"


def test_runtime_rejects_dataset_scope() -> None:
    runtime = echo_runtime(ToolRegistry([EchoTool()]))
    scope = DatasetScope(
        selected_dataset_id="dataset-1",
        allowed_dataset_ids=["dataset-2"],
        dataset_types={"dataset-1": "mysql"},
    )

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request(dataset_scope=scope)))

    assert caught.value.reason == "Dataset not allowed"


def test_runtime_rejects_guardrail_failure() -> None:
    runtime = echo_runtime(ToolRegistry([EchoTool()]))

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(
            runtime.call(
                request(args={"dataset_id": "dataset-1", "sql": "DELETE FROM sales"})
            )
        )

    assert caught.value.reason == "SQL guardrail rejected"
    assert not caught.value.retryable


def test_runtime_times_out_slow_tool() -> None:
    runtime = echo_runtime(ToolRegistry([EchoTool(delay=0.05)]))

    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request(timeout_ms=1)))

    assert caught.value.reason == "Tool execution timed out"
    assert caught.value.retryable
