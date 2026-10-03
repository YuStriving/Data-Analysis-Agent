from __future__ import annotations

from agent_backend.capabilities.agent_runtime.execution_control.contracts import (
    TerminationDecision,
)
from agent_backend.capabilities.agent_runtime.execution_control.policies import (
    BudgetPolicy,
    TokenUsage,
)
from agent_backend.capabilities.agent_runtime.execution_control.tracker import (
    RuntimeExecutionTracker,
)


class BudgetGuard:
    def __init__(self, policy: BudgetPolicy, tracker: RuntimeExecutionTracker) -> None:
        self.policy = policy
        self.tracker = tracker

    def before_model_call(self) -> TerminationDecision:
        elapsed_decision = self.check_elapsed()
        if elapsed_decision.should_stop:
            return elapsed_decision
        if self.tracker.state.model_call_count >= self.policy.max_model_calls:
            return TerminationDecision.stop(
                "budget_exceeded",
                failure_code="max_model_calls_exceeded",
                failure_message="Model call budget exceeded.",
            )
        return TerminationDecision.continue_to()

    def after_model_call(self, token_usage: TokenUsage | None = None) -> None:
        self.tracker.record_model_call(token_usage)

    def before_tool_call(self) -> TerminationDecision:
        elapsed_decision = self.check_elapsed()
        if elapsed_decision.should_stop:
            return elapsed_decision
        if self.tracker.state.tool_call_count >= self.policy.max_tool_calls:
            return TerminationDecision.stop(
                "budget_exceeded",
                failure_code="max_tool_calls_exceeded",
                failure_message="Tool call budget exceeded.",
            )
        return TerminationDecision.continue_to()

    def after_tool_call(self) -> None:
        return None

    def check_elapsed(self) -> TerminationDecision:
        if self.tracker.elapsed_ms() >= self.policy.max_elapsed_ms:
            return TerminationDecision.stop(
                "timeout",
                failure_code="max_elapsed_ms_exceeded",
                failure_message="Runtime elapsed time budget exceeded.",
            )
        return TerminationDecision.continue_to()
