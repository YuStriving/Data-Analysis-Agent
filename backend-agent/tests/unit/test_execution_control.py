from __future__ import annotations

from typing import Any

from agent_backend.agent_runtime.execution_control import (
    AgentSpec,
    BudgetPolicy,
    EdgeSpec,
    NodeExecutionResult,
    NodeSpec,
    RuntimeExecutionController,
    RuntimePolicy,
    ToolPolicy,
)
from agent_backend.agent_runtime.execution_control.policies import (
    ToolAccessPolicy,
)
from agent_backend.agent_runtime.tool_calling import (
    ToolCallError,
    ToolCallRequest,
    ToolExecutionContext,
)
from agent_backend.capabilities.data_analysis.execution.presets import (
    build_data_analysis_agent_spec,
)


class FakeToolResolver:
    def __init__(self, policy: ToolAccessPolicy) -> None:
        self.policy = policy

    def get_tool_policy(
        self, tool_name: str, tool_version: str | None = None
    ) -> ToolAccessPolicy:
        return self.policy


def make_spec(**overrides: Any) -> AgentSpec:
    payload: dict[str, Any] = {
        "agent_id": "test_agent",
        "entry_node": "start",
        "terminal_nodes": {"done"},
        "node_specs": {
            "start": NodeSpec(node_id="start", allowed_tools={"safe.tool"}),
            "repair_sql": NodeSpec(node_id="repair_sql"),
            "done": NodeSpec(node_id="done", can_emit_final_result=True),
        },
        "edge_specs": [
            EdgeSpec(
                from_node="start",
                to_node="repair_sql",
                loop_name="sql_repair_loop",
                max_traversals=3,
            ),
            EdgeSpec(
                from_node="repair_sql",
                to_node="start",
                loop_name="sql_repair_loop",
                max_traversals=3,
            ),
            EdgeSpec(from_node="start", to_node="done"),
        ],
        "runtime_policy": RuntimePolicy(
            max_steps=6,
            repeated_error_limit=2,
            no_progress_limit=2,
            loop_attempt_limits={"sql_repair_loop": 2},
        ),
        "budget_policy": BudgetPolicy(
            max_model_calls=1, max_tool_calls=3, max_elapsed_ms=120_000
        ),
        "tool_policy": ToolPolicy(same_tool_call_limit=2, same_tool_failure_limit=2),
    }
    payload.update(overrides)
    return AgentSpec(**payload)


def make_request(**overrides: Any) -> ToolCallRequest:
    payload = {
        "tool_call_id": "call-1",
        "tool_name": "safe.tool",
        "tool_version": "v1",
        "agent_name": "test_agent",
        "agent_version": "v1",
        "node_id": "start",
        "task_id": "task-1",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "goal": "Complete the task",
        "purpose": "Run a declared capability",
        "args": {"sql": "select 1"},
        "timeout_ms": 1000,
    }
    payload.update(overrides)
    tool_name = payload.pop("tool_name")
    args = payload.pop("args")
    return ToolCallRequest(
        tool_name=tool_name, args=args, context=ToolExecutionContext(**payload)
    )


def test_data_analysis_preset_reserves_repair_sql_loop() -> None:
    spec = build_data_analysis_agent_spec()

    assert "repair_sql" in spec.node_specs
    assert spec.runtime_policy.loop_attempt_limits["sql_repair_loop"] == 3
    assert spec.edge_from("validate_sql", "repair_sql") is not None
    assert spec.edge_from("repair_sql", "validate_sql") is not None
    assert spec.edge_from("execute_sql", "repair_sql") is not None


def test_controller_rejects_undeclared_edge() -> None:
    controller = RuntimeExecutionController(make_spec())
    controller.before_node("start")

    decision = controller.after_node(
        NodeExecutionResult(node_id="start", status="running", next_node="missing")
    )

    assert decision.should_stop
    assert decision.status == "failed"
    assert decision.failure_code == "undeclared_edge"


def test_controller_rejects_final_result_from_non_terminal_node() -> None:
    controller = RuntimeExecutionController(make_spec())
    controller.before_node("start")

    decision = controller.after_node(
        NodeExecutionResult(node_id="start", status="completed")
    )

    assert decision.should_stop
    assert decision.status == "failed"
    assert decision.failure_code == "final_result_not_allowed"


def test_controller_enforces_sql_repair_loop_attempt_limit() -> None:
    controller = RuntimeExecutionController(make_spec())

    controller.before_node("start")
    assert not controller.after_node(
        NodeExecutionResult(node_id="start", status="running", next_node="repair_sql")
    ).should_stop
    controller.before_node("repair_sql")
    assert not controller.after_node(
        NodeExecutionResult(node_id="repair_sql", status="running", next_node="start")
    ).should_stop
    controller.before_node("start")

    decision = controller.after_node(
        NodeExecutionResult(node_id="start", status="running", next_node="repair_sql")
    )

    assert decision.should_stop
    assert decision.status == "loop_limit_exceeded"
    assert decision.failure_code == "loop_attempt_limit_exceeded"


def test_controller_detects_repeated_node_errors() -> None:
    spec = make_spec(
        runtime_policy=RuntimePolicy(
            max_steps=6,
            repeated_error_limit=2,
            no_progress_limit=2,
            loop_attempt_limits={"sql_repair_loop": 5},
        )
    )
    controller = RuntimeExecutionController(spec)

    controller.before_node("start")
    assert not controller.after_node(
        NodeExecutionResult(
            node_id="start",
            status="running",
            next_node="repair_sql",
            error_code="sql_invalid",
        )
    ).should_stop
    controller.before_node("repair_sql")
    controller.after_node(
        NodeExecutionResult(node_id="repair_sql", status="running", next_node="start")
    )
    controller.before_node("start")

    decision = controller.after_node(
        NodeExecutionResult(
            node_id="start",
            status="running",
            next_node="repair_sql",
            error_code="sql_invalid",
        )
    )

    assert decision.should_stop
    assert decision.failure_code == "repeated_error_limit_exceeded"


def test_controller_detects_repair_sql_no_progress() -> None:
    spec = make_spec(
        runtime_policy=RuntimePolicy(
            no_progress_limit=2, loop_attempt_limits={"sql_repair_loop": 3}
        )
    )
    controller = RuntimeExecutionController(spec)

    controller.before_node("repair_sql")
    assert not controller.after_node(
        NodeExecutionResult(
            node_id="repair_sql",
            status="running",
            next_node="start",
            metadata={"candidate_sql_hash": "same"},
        )
    ).should_stop
    controller.before_node("start")
    controller.after_node(
        NodeExecutionResult(node_id="start", status="running", next_node="repair_sql")
    )
    controller.before_node("repair_sql")

    decision = controller.after_node(
        NodeExecutionResult(
            node_id="repair_sql",
            status="running",
            next_node="start",
            metadata={"candidate_sql_hash": "same"},
        )
    )

    assert decision.should_stop
    assert decision.failure_code == "no_progress_limit_exceeded"


def test_controller_records_token_usage_without_blocking_on_tokens() -> None:
    controller = RuntimeExecutionController(make_spec())

    assert not controller.before_model_call("start").should_stop
    controller.after_model_call("start")

    decision = controller.before_model_call("start")

    assert decision.should_stop
    assert decision.status == "budget_exceeded"
    assert decision.failure_code == "max_model_calls_exceeded"


def test_controller_rejects_tool_outside_node_allowlist() -> None:
    controller = RuntimeExecutionController(make_spec())

    decision = controller.before_tool_call(make_request(tool_name="unsafe.tool"))

    assert decision.should_stop
    assert decision.status == "guardrail_rejected"
    assert decision.failure_code == "tool_not_allowed_for_node"


def test_controller_rejects_risky_tool_policy() -> None:
    policy = ToolAccessPolicy(
        risk_level="dangerous",
    )
    controller = RuntimeExecutionController(
        make_spec(), tool_resolver=FakeToolResolver(policy)
    )

    decision = controller.before_tool_call(make_request())

    assert decision.should_stop
    assert decision.status == "guardrail_rejected"
    assert decision.failure_code == "tool_risk_level_not_allowed"


def test_controller_rejects_repeated_tool_failure() -> None:
    controller = RuntimeExecutionController(make_spec())
    request = make_request()
    error = ToolCallError("Tool execution failed", "failed")

    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(
        request, ToolCallError(error.reason, "failed with different diagnostic content")
    )
    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(request, error)

    decision = controller.before_tool_call(request)

    assert decision.should_stop
    assert decision.status == "loop_limit_exceeded"
    assert decision.failure_code == "repeated_tool_failure"


def test_controller_success_resets_consecutive_tool_failures() -> None:
    controller = RuntimeExecutionController(
        make_spec(
            budget_policy=BudgetPolicy(max_tool_calls=10),
            tool_policy=ToolPolicy(same_tool_call_limit=10, same_tool_failure_limit=2),
        )
    )
    request = make_request()
    error = ToolCallError("Tool execution failed", "failed")

    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(request, error)
    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(request)
    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(request, error)

    assert not controller.before_tool_call(request).should_stop


def test_controller_counts_failures_by_reason_instead_of_message() -> None:
    controller = RuntimeExecutionController(
        make_spec(
            tool_policy=ToolPolicy(same_tool_call_limit=10, same_tool_failure_limit=2),
        )
    )
    request = make_request()

    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(
        request, ToolCallError("Invalid tool input", "same message")
    )
    assert not controller.before_tool_call(request).should_stop
    controller.after_tool_call(
        request, ToolCallError("Missing permissions", "same message")
    )

    assert not controller.before_tool_call(request).should_stop
