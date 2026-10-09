from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel, Field

from agent_backend.agent_runtime.execution_control.contracts import (
    ToolCallFingerprint,
)
from agent_backend.agent_runtime.execution_control.policies import (
    RuntimeUsage,
    TokenUsage,
)


class ToolCallHistoryEntry(BaseModel):
    fingerprint: ToolCallFingerprint
    success: bool | None = None
    error_code: str | None = None


class RuntimeControlState(BaseModel):
    step_count: int = 0
    node_visit_counts: dict[str, int] = Field(default_factory=dict)
    edge_traversal_counts: dict[str, int] = Field(default_factory=dict)
    loop_attempt_counts: dict[str, int] = Field(default_factory=dict)
    model_call_count: int = 0
    tool_call_count: int = 0
    started_at_monotonic: float = Field(default_factory=time.monotonic)
    elapsed_ms: int = 0
    repeated_error_count: int = 0
    last_error_key: tuple[str, str] | None = None
    no_progress_count: int = 0
    last_candidate_sql_hash: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_call_history_summary: list[ToolCallHistoryEntry] = Field(default_factory=list)


class RuntimeExecutionTracker:
    def __init__(self, state: RuntimeControlState | None = None) -> None:
        self.state = state or RuntimeControlState()

    def elapsed_ms(self) -> int:
        self.state.elapsed_ms = int((time.monotonic() - self.state.started_at_monotonic) * 1000)
        return self.state.elapsed_ms

    def usage(self) -> RuntimeUsage:
        return RuntimeUsage(
            step_count=self.state.step_count,
            model_calls=self.state.model_call_count,
            tool_calls=self.state.tool_call_count,
            elapsed_ms=self.elapsed_ms(),
            token_usage=self.state.token_usage,
        )

    def enter_node(self, node_id: str) -> None:
        self.state.step_count += 1
        self.state.node_visit_counts[node_id] = self.state.node_visit_counts.get(node_id, 0) + 1

    def record_transition(self, from_node: str, to_node: str, loop_name: str | None = None) -> None:
        edge_key = self.edge_key(from_node, to_node)
        self.state.edge_traversal_counts[edge_key] = self.state.edge_traversal_counts.get(edge_key, 0) + 1
        if loop_name:
            self.state.loop_attempt_counts[loop_name] = self.state.loop_attempt_counts.get(loop_name, 0) + 1

    def record_model_call(self, token_usage: TokenUsage | None = None) -> None:
        self.state.model_call_count += 1
        if token_usage is not None:
            self.state.token_usage = self.state.token_usage.merged(token_usage)

    def record_tool_call(self, fingerprint: ToolCallFingerprint, error_code: str | None = None) -> None:
        self.state.tool_call_count += 1
        self.state.tool_call_history_summary.append(
            ToolCallHistoryEntry(
                fingerprint=fingerprint,
                success=error_code is None,
                error_code=error_code,
            )
        )

    def consecutive_same_tool_calls(self, fingerprint: ToolCallFingerprint) -> int:
        count = 0
        for entry in reversed(self.state.tool_call_history_summary):
            if entry.fingerprint.call_key != fingerprint.call_key:
                break
            count += 1
        return count

    def consecutive_same_tool_failures(self, fingerprint: ToolCallFingerprint) -> Counter[tuple[str | None, str, str, str, str]]:
        counts: Counter[tuple[str | None, str, str, str, str]] = Counter()
        for entry in reversed(self.state.tool_call_history_summary):
            if entry.fingerprint.call_key != fingerprint.call_key:
                break
            if entry.error_code is None:
                break
            counts[entry.fingerprint.failure_key(entry.error_code)] += 1
        return counts

    @staticmethod
    def edge_key(from_node: str, to_node: str) -> str:
        return f"{from_node}->{to_node}"
