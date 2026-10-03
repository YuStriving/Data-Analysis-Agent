from __future__ import annotations

from agent_backend.capabilities.agent_runtime.execution_control.contracts import (
    TERMINAL_STATUSES,
    NodeExecutionResult,
    TerminationDecision,
)


def decision_from_node_result(result: NodeExecutionResult) -> TerminationDecision | None:
    if result.status not in TERMINAL_STATUSES:
        return None
    return TerminationDecision.stop(
        result.status,
        failure_code=result.error_code,
        failure_message=result.error_message,
    )
