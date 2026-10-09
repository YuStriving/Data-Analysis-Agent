from __future__ import annotations

from agent_backend.agent_runtime.execution_control.contracts import (
    AgentSpec,
    NodeExecutionResult,
    TerminationDecision,
    ToolCallFingerprint,
)
from agent_backend.agent_runtime.execution_control.tracker import (
    RuntimeExecutionTracker,
)


class LoopGuard:
    def __init__(self, agent_spec: AgentSpec, tracker: RuntimeExecutionTracker) -> None:
        self.agent_spec = agent_spec
        self.tracker = tracker

    def before_node(self, node_id: str) -> TerminationDecision:
        node_spec = self.agent_spec.node_specs.get(node_id)
        if node_spec is None:
            return TerminationDecision.stop(
                "failed",
                failure_code="unknown_node",
                failure_message=f"Node is not declared in AgentSpec: {node_id}",
            )

        max_visits = node_spec.max_visits or self.agent_spec.runtime_policy.default_max_node_visits
        if self.tracker.state.node_visit_counts.get(node_id, 0) >= max_visits:
            return TerminationDecision.stop(
                "loop_limit_exceeded",
                failure_code="node_visit_limit_exceeded",
                failure_message=f"Node visit limit exceeded: {node_id}",
            )
        return TerminationDecision.continue_to(node_id)

    def after_transition(
        self,
        from_node: str,
        to_node: str,
        result: NodeExecutionResult,
    ) -> TerminationDecision:
        edge = self.agent_spec.edge_from(from_node, to_node)
        if edge is None:
            return TerminationDecision.stop(
                "failed",
                failure_code="undeclared_edge",
                failure_message=f"Edge is not declared in AgentSpec: {from_node}->{to_node}",
            )

        edge_key = self.tracker.edge_key(from_node, to_node)
        if edge.max_traversals is not None:
            next_count = self.tracker.state.edge_traversal_counts.get(edge_key, 0) + 1
            if next_count > edge.max_traversals:
                return TerminationDecision.stop(
                    "loop_limit_exceeded",
                    failure_code="edge_traversal_limit_exceeded",
                    failure_message=f"Edge traversal limit exceeded: {from_node}->{to_node}",
                )

        if edge.loop_name:
            max_attempts = self.agent_spec.runtime_policy.loop_attempt_limits.get(edge.loop_name)
            next_count = self.tracker.state.loop_attempt_counts.get(edge.loop_name, 0) + 1
            if max_attempts is not None and next_count > max_attempts:
                return TerminationDecision.stop(
                    "loop_limit_exceeded",
                    failure_code="loop_attempt_limit_exceeded",
                    failure_message=f"Loop attempt limit exceeded: {edge.loop_name}",
                )

        repeated_error_decision = self._check_repeated_error(result)
        if repeated_error_decision.should_stop:
            return repeated_error_decision

        no_progress_decision = self._check_no_progress(result)
        if no_progress_decision.should_stop:
            return no_progress_decision

        if self.tracker.state.step_count >= self.agent_spec.runtime_policy.max_steps:
            return TerminationDecision.stop(
                "loop_limit_exceeded",
                failure_code="max_steps_exceeded",
                failure_message="Workflow step limit exceeded.",
            )

        self.tracker.record_transition(from_node, to_node, edge.loop_name)
        return TerminationDecision.continue_to(to_node)

    def before_tool_call(self, fingerprint: ToolCallFingerprint) -> TerminationDecision:
        failure_counts = self.tracker.consecutive_same_tool_failures(fingerprint)
        for count in failure_counts.values():
            if count >= self.agent_spec.tool_policy.same_tool_failure_limit:
                return TerminationDecision.stop(
                    "loop_limit_exceeded",
                    failure_code="repeated_tool_failure",
                    failure_message="Repeated tool failure limit exceeded.",
                )

        same_call_count = self.tracker.consecutive_same_tool_calls(fingerprint)
        if same_call_count >= self.agent_spec.tool_policy.same_tool_call_limit:
            return TerminationDecision.stop(
                "loop_limit_exceeded",
                failure_code="repeated_tool_call",
                failure_message="Repeated tool call limit exceeded.",
            )
        return TerminationDecision.continue_to()

    def after_tool_call(
        self,
        fingerprint: ToolCallFingerprint,
        error_code: str | None,
    ) -> None:
        self.tracker.record_tool_call(fingerprint, error_code)

    def _check_repeated_error(self, result: NodeExecutionResult) -> TerminationDecision:
        if not result.error_code:
            return TerminationDecision.continue_to()

        error_key = (result.node_id, result.error_code)
        if self.tracker.state.last_error_key == error_key:
            self.tracker.state.repeated_error_count += 1
        else:
            self.tracker.state.last_error_key = error_key
            self.tracker.state.repeated_error_count = 1

        if self.tracker.state.repeated_error_count >= self.agent_spec.runtime_policy.repeated_error_limit:
            return TerminationDecision.stop(
                "loop_limit_exceeded",
                failure_code="repeated_error_limit_exceeded",
                failure_message=f"Repeated node error limit exceeded: {result.node_id}:{result.error_code}",
            )
        return TerminationDecision.continue_to()

    def _check_no_progress(self, result: NodeExecutionResult) -> TerminationDecision:
        candidate_hash = result.metadata.get("candidate_sql_hash")
        if result.node_id != "repair_sql" or not isinstance(candidate_hash, str):
            return TerminationDecision.continue_to()

        if self.tracker.state.last_candidate_sql_hash == candidate_hash:
            self.tracker.state.no_progress_count += 1
        else:
            self.tracker.state.last_candidate_sql_hash = candidate_hash
            self.tracker.state.no_progress_count = 1

        if self.tracker.state.no_progress_count >= self.agent_spec.runtime_policy.no_progress_limit:
            return TerminationDecision.stop(
                "loop_limit_exceeded",
                failure_code="no_progress_limit_exceeded",
                failure_message="SQL repair did not make progress.",
            )
        return TerminationDecision.continue_to()
