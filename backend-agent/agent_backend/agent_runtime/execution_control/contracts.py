from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from agent_backend.agent_runtime.execution_control.policies import (
    BudgetPolicy,
    RuntimePolicy,
    RuntimeUsage,
    ToolPolicy,
)

AgentExecutionMode = Literal["workflow_mode"]

RuntimeStatus = Literal[
    "running",
    "completed",
    "user_action_required",
    "cannot_continue",
    "failed",
    "loop_limit_exceeded",
    "budget_exceeded",
    "timeout",
    "guardrail_rejected",
]


TERMINAL_STATUSES: set[str] = {
    "completed",
    "user_action_required",
    "cannot_continue",
    "failed",
    "loop_limit_exceeded",
    "budget_exceeded",
    "timeout",
    "guardrail_rejected",
}


class NodeSpec(BaseModel):
    node_id: str
    allowed_tools: set[str] = Field(default_factory=set)
    max_visits: int | None = Field(default=None, ge=1)
    can_emit_final_result: bool = False


class EdgeSpec(BaseModel):
    from_node: str
    to_node: str
    max_traversals: int | None = Field(default=None, ge=1)
    loop_name: str | None = None


class AgentSpec(BaseModel):
    agent_id: str
    execution_mode: AgentExecutionMode = "workflow_mode"
    entry_node: str
    terminal_nodes: set[str]
    node_specs: dict[str, NodeSpec]
    edge_specs: list[EdgeSpec]
    runtime_policy: RuntimePolicy = Field(default_factory=RuntimePolicy)
    budget_policy: BudgetPolicy = Field(default_factory=BudgetPolicy)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)

    @model_validator(mode="after")
    def validate_graph_references(self) -> AgentSpec:
        if self.entry_node not in self.node_specs:
            raise ValueError("entry_node must exist in node_specs")
        unknown_terminal_nodes = self.terminal_nodes - set(self.node_specs)
        if unknown_terminal_nodes:
            raise ValueError(f"terminal_nodes contain unknown nodes: {sorted(unknown_terminal_nodes)}")
        for node_id, node_spec in self.node_specs.items():
            if node_spec.node_id != node_id:
                raise ValueError(f"node_specs key must match node_id: {node_id}")
        for edge in self.edge_specs:
            if edge.from_node not in self.node_specs:
                raise ValueError(f"edge from_node is unknown: {edge.from_node}")
            if edge.to_node not in self.node_specs:
                raise ValueError(f"edge to_node is unknown: {edge.to_node}")
        return self

    def edge_from(self, from_node: str, to_node: str) -> EdgeSpec | None:
        for edge in self.edge_specs:
            if edge.from_node == from_node and edge.to_node == to_node:
                return edge
        return None


class NodeExecutionResult(BaseModel):
    node_id: str
    status: RuntimeStatus
    next_node: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    user_action_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TerminationDecision(BaseModel):
    should_stop: bool
    status: RuntimeStatus
    failure_code: str | None = None
    failure_message: str | None = None
    next_node: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def continue_to(
        cls,
        next_node: str | None = None,
        *,
        warnings: list[str] | None = None,
    ) -> TerminationDecision:
        return cls(
            should_stop=False,
            status="running",
            next_node=next_node,
            warnings=warnings or [],
        )

    @classmethod
    def stop(
        cls,
        status: RuntimeStatus,
        *,
        failure_code: str | None = None,
        failure_message: str | None = None,
        warnings: list[str] | None = None,
    ) -> TerminationDecision:
        return cls(
            should_stop=True,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
            warnings=warnings or [],
        )


class RuntimeExecutionResult(BaseModel):
    task_id: str
    trace_id: str
    agent_id: str
    status: RuntimeStatus
    final_answer: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    usage: RuntimeUsage
    warnings: list[str] = Field(default_factory=list)


class ToolCallFingerprint(BaseModel):
    node_id: str | None = None
    tool_name: str
    tool_version: str
    normalized_args_hash: str

    @property
    def call_key(self) -> tuple[str | None, str, str, str]:
        return (
            self.node_id,
            self.tool_name,
            self.tool_version,
            self.normalized_args_hash,
        )

    def failure_key(self, error_code: str) -> tuple[str | None, str, str, str, str]:
        return (*self.call_key, error_code)
