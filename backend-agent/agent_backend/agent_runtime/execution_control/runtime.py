from __future__ import annotations

from agent_backend.agent_runtime.execution_control.budget_guard import (
    BudgetGuard,
)
from agent_backend.agent_runtime.execution_control.contracts import (
    AgentSpec,
    NodeExecutionResult,
    RuntimeExecutionResult,
    RuntimeStatus,
    TerminationDecision,
)
from agent_backend.agent_runtime.execution_control.loop_guard import (
    LoopGuard,
)
from agent_backend.agent_runtime.execution_control.policies import (
    TokenUsage,
)
from agent_backend.agent_runtime.execution_control.termination import (
    decision_from_node_result,
)
from agent_backend.agent_runtime.execution_control.tool_guard import (
    ToolAccessPolicyResolver,
    ToolGuard,
)
from agent_backend.agent_runtime.execution_control.tracker import (
    RuntimeControlState,
    RuntimeExecutionTracker,
)
from agent_backend.agent_runtime.tool_calling.contracts import (
    ToolCallRequest,
)
from agent_backend.agent_runtime.tool_calling.errors import ToolCallError


class RuntimeExecutionController:
    def __init__(
        self,
        agent_spec: AgentSpec,
        *,
        state: RuntimeControlState | None = None,
        tool_resolver: ToolAccessPolicyResolver | None = None,
    ) -> None:
        self.agent_spec = agent_spec
        self.tracker = RuntimeExecutionTracker(state)
        self.loop_guard = LoopGuard(agent_spec, self.tracker)
        self.budget_guard = BudgetGuard(agent_spec.budget_policy, self.tracker)
        self.tool_guard = ToolGuard(agent_spec, tool_resolver=tool_resolver)

    @property
    def state(self) -> RuntimeControlState:
        return self.tracker.state

    def before_node(self, node_id: str) -> TerminationDecision:
        elapsed_decision = self.budget_guard.check_elapsed()
        if elapsed_decision.should_stop:
            return elapsed_decision
        decision = self.loop_guard.before_node(node_id)
        if decision.should_stop:
            return decision
        self.tracker.enter_node(node_id)
        return TerminationDecision.continue_to(node_id)

    def after_node(self, result: NodeExecutionResult) -> TerminationDecision:
        if result.status == "completed" and not self._can_emit_final_result(result.node_id):
            return TerminationDecision.stop(
                "failed",
                failure_code="final_result_not_allowed",
                failure_message=f"Node cannot emit final result: {result.node_id}",
            )
        terminal_decision = decision_from_node_result(result)
        if terminal_decision is not None:
            return terminal_decision
        if not result.next_node:
            return TerminationDecision.stop(
                "failed",
                failure_code="missing_next_node",
                failure_message=f"Node did not provide next_node: {result.node_id}",
            )
        elapsed_decision = self.budget_guard.check_elapsed()
        if elapsed_decision.should_stop:
            return elapsed_decision
        return self.loop_guard.after_transition(result.node_id, result.next_node, result)

    def before_model_call(self, node_id: str) -> TerminationDecision:
        if node_id not in self.agent_spec.node_specs:
            return TerminationDecision.stop(
                "failed",
                failure_code="unknown_node",
                failure_message=f"Node is not declared in AgentSpec: {node_id}",
            )
        return self.budget_guard.before_model_call()

    def after_model_call(
        self,
        node_id: str,
        token_usage: TokenUsage | None = None,
    ) -> None:
        if node_id not in self.agent_spec.node_specs:
            return
        self.budget_guard.after_model_call(token_usage)

    def before_tool_call(self, request: ToolCallRequest) -> TerminationDecision:
        if not request.context.node_id:
            return TerminationDecision.stop(
                "guardrail_rejected",
                failure_code="missing_node_id",
                failure_message="Tool call must include node_id.",
            )
        allowed_decision = self.tool_guard.check_allowed_tool(
            request.context.node_id,
            request.tool_name,
            request.tool_version,
        )
        if allowed_decision.should_stop:
            return allowed_decision

        fingerprint = self.tool_guard.build_fingerprint(request)
        loop_decision = self.loop_guard.before_tool_call(fingerprint)
        if loop_decision.should_stop:
            return loop_decision
        return self.budget_guard.before_tool_call()

    def after_tool_call(
        self,
        request: ToolCallRequest,
        error: ToolCallError | None = None,
    ) -> None:
        fingerprint = self.tool_guard.build_fingerprint(request)
        reason = error.reason if error is not None else None
        self.loop_guard.after_tool_call(fingerprint, reason)

    def result(
        self,
        *,
        task_id: str,
        trace_id: str,
        status: RuntimeStatus,
        final_answer: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        warnings: list[str] | None = None,
    ) -> RuntimeExecutionResult:
        return RuntimeExecutionResult(
            task_id=task_id,
            trace_id=trace_id,
            agent_id=self.agent_spec.agent_id,
            status=status,
            final_answer=final_answer,
            failure_code=failure_code,
            failure_message=failure_message,
            usage=self.tracker.usage(),
            warnings=warnings or [],
        )

    def _can_emit_final_result(self, node_id: str) -> bool:
        node_spec = self.agent_spec.node_specs.get(node_id)
        return node_id in self.agent_spec.terminal_nodes or bool(
            node_spec and node_spec.can_emit_final_result
        )
