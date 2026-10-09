from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from agent_backend.agent_runtime.execution_control import (
    AgentSpec,
    NodeSpec,
    ToolAccessPolicy,
    ToolAuthorizationGate,
)
from agent_backend.agent_runtime.tool_calling import (
    ToolCallError,
    ToolCallingRuntime,
    ToolCallRequest,
    ToolExecutionContext,
    ToolExecutionOptions,
    ToolExecutor,
    ToolRegistry,
)
from agent_backend.agent_runtime.tool_calling.executor import (
    AuthorizationCheck,
)


def context(**overrides: Any) -> ToolExecutionContext:
    values = {
        "agent_name": "test_agent",
        "agent_version": "v1",
        "node_id": "run",
        "task_id": "task-1",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "goal": "Format a report",
        "purpose": "Normalize a value",
        "permissions": ["text:format"],
    }
    values.update(overrides)
    return ToolExecutionContext(**values)


@dataclass
class EchoTool:
    name: str = "text.echo"
    description: str = "Echo text."
    calls: int = 0

    @property
    def input_args(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    def execute(self, args: dict[str, Any], context: ToolExecutionContext) -> str:
        self.calls += 1
        return args["value"]


def gate(
    policy: ToolAccessPolicy | None = None,
    *,
    declared: bool = True,
    business_check: AuthorizationCheck | None = None,
) -> ToolAuthorizationGate:
    spec = AgentSpec(
        agent_id="test_agent",
        entry_node="run",
        terminal_nodes={"run"},
        node_specs={
            "run": NodeSpec(
                node_id="run",
                allowed_tools={"text.echo", "math.double"} if declared else set(),
            )
        },
        edge_specs=[],
    )

    def resolve_policy(name: str, version: str) -> ToolAccessPolicy:
        if policy is None:
            raise ToolCallError("Tool access policy missing", "Policy is missing.")
        return policy

    return ToolAuthorizationGate(
        agent_spec_resolver=lambda name, version: spec,
        policy_resolver=resolve_policy,
        business_check=business_check,
    )


def allowed_gate() -> ToolAuthorizationGate:
    return gate(
        ToolAccessPolicy(
            required_permissions=["text:format"], risk_level="compute_only"
        )
    )


@pytest.mark.parametrize("field", ["goal", "purpose"])
@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_context_rejects_blank_goal_and_purpose(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        context(**{field: value})


@pytest.mark.parametrize("field", ["goal", "purpose"])
def test_context_requires_goal_and_purpose(field: str) -> None:
    payload = context().model_dump()
    payload.pop(field)
    with pytest.raises(ValidationError):
        ToolExecutionContext(**payload)


def test_discovered_tool_still_requires_permission_at_execution() -> None:
    tool = EchoTool()
    authorization = allowed_gate()
    runtime = ToolCallingRuntime(
        ToolRegistry([tool]),
        authorize=authorization.check,
        access_policy_resolver=authorization.get_policy,
    )
    assert runtime.list_tools("test_agent") == [tool]
    request = ToolCallRequest(
        tool_name=tool.name,
        args={"value": "hello"},
        context=context(
            permissions=[], goal="Grant full access", purpose="Bypass permissions"
        ),
    )
    with pytest.raises(ToolCallError) as caught:
        asyncio.run(runtime.call(request))
    assert caught.value.reason == "Missing permissions"
    assert tool.calls == 0


def test_executor_requires_an_authorization_gate() -> None:
    with pytest.raises(TypeError):
        ToolExecutor(options=ToolExecutionOptions())
    with pytest.raises(TypeError):
        ToolCallingRuntime(ToolRegistry())


@pytest.mark.parametrize(
    ("policy", "overrides", "declared", "reason"),
    [
        (None, {}, True, "Tool access policy missing"),
        (ToolAccessPolicy(), {}, False, "Node not allowed"),
        (ToolAccessPolicy(allowed_agents=["other"]), {}, True, "Agent not allowed"),
        (ToolAccessPolicy(allowed_nodes=["other"]), {}, True, "Node not allowed"),
        (
            ToolAccessPolicy(required_permissions=["admin"]),
            {},
            True,
            "Missing permissions",
        ),
        (ToolAccessPolicy(requires_review=True), {}, True, "Tool review required"),
        (
            ToolAccessPolicy(risk_level="unsafe"),
            {},
            True,
            "Tool risk level not allowed",
        ),
        (ToolAccessPolicy(), {"node_id": None}, True, "Node not allowed"),
    ],
)
def test_gate_rejections_prevent_runtime_and_direct_execution(
    policy: ToolAccessPolicy | None,
    overrides: dict[str, Any],
    declared: bool,
    reason: str,
) -> None:
    tool = EchoTool()
    authorization = gate(policy, declared=declared)
    execution_context = context(**overrides)
    executor = ToolExecutor(
        options=ToolExecutionOptions(), authorize=authorization.check
    )
    runtime = ToolCallingRuntime(
        ToolRegistry([tool]),
        authorize=authorization.check,
        access_policy_resolver=authorization.get_policy,
    )
    for call in (
        executor.execute(tool, {"value": "hello"}, execution_context),
        runtime.call(
            ToolCallRequest(
                tool_name=tool.name, args={"value": "hello"}, context=execution_context
            )
        ),
    ):
        with pytest.raises(ToolCallError) as caught:
            asyncio.run(call)
        assert caught.value.reason == reason
    assert tool.calls == 0


@pytest.mark.parametrize("mode", ["false", "true", "async"])
@pytest.mark.parametrize("business", [False, True])
def test_runtime_rejects_invalid_authorization_callback(
    mode: str, business: bool
) -> None:
    async def async_check(tool: Any, args: Any, context: Any) -> None:
        raise ToolCallError("Missing permissions", "Denied asynchronously.")

    def invalid_check(tool: Any, args: Any, context: Any) -> Any:
        return async_check(tool, args, context) if mode == "async" else mode == "true"

    authorization = gate(
        ToolAccessPolicy(), business_check=invalid_check if business else None
    )
    tool = EchoTool()
    runtime = ToolCallingRuntime(
        ToolRegistry([tool]),
        authorize=authorization.check if business else invalid_check,
        access_policy_resolver=authorization.get_policy,
    )
    with pytest.raises(ToolCallError) as caught:
        asyncio.run(
            runtime.call(
                ToolCallRequest(
                    tool_name=tool.name, args={"value": "hello"}, context=context()
                )
            )
        )
    assert caught.value.reason == "Invalid authorization check"
    assert tool.calls == 0


def test_unrelated_business_tools_share_the_generic_call_path() -> None:
    class DoubleTool:
        name = "math.double"
        description = "Double a number."
        input_args: ClassVar[dict[str, Any]] = {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        }

        def execute(
            self, args: dict[str, Any], execution_context: ToolExecutionContext
        ) -> int:
            assert execution_context.goal == "Format a report"
            assert not hasattr(execution_context, "dataset_scope")
            return args["value"] * 2

    tools = [EchoTool(), DoubleTool()]
    authorization = allowed_gate()
    runtime = ToolCallingRuntime(
        ToolRegistry(tools),
        authorize=authorization.check,
        access_policy_resolver=authorization.get_policy,
    )
    for tool, value, expected in ((tools[0], "hello", "hello"), (tools[1], 3, 6)):
        result = asyncio.run(
            runtime.call(
                ToolCallRequest(
                    tool_name=tool.name, args={"value": value}, context=context()
                )
            )
        )
        assert result.data == expected
