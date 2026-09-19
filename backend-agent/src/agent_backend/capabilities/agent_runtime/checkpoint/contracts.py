from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class NodeCheckpointSnapshot(BaseModel):
    snapshot_id: str
    tenant_id: str
    user_id: str
    session_id: str
    task_id: str
    trace_id: str
    node_id: str

    graph_name: str
    node_name: str
    node_status: str
    previous_node: str | None = None
    next_node: str | None = None
    resume_cursor: str | None = None

    task_type: str
    task_summary: str
    current_step: str
    current_goal: str

    hot_context: dict[str, str] = Field(default_factory=dict)
    conversation_summary: str
    confirmed_facts: list[str] = Field(default_factory=list)
    dataset_refs: list[str] = Field(default_factory=list)
    injected_context_version: str

    last_tool_name: str | None = None
    last_tool_input_hash: str | None = None
    last_tool_output_ref: str | None = None
    retry_count: int = 0
    tool_status: str | None = None

    llm_model: str
    prompt_version: str
    token_usage: int = 0
    elapsed_ms: int = 0

    interrupt_reason: str | None = None
    failure_stage: str | None = None
    manual_restore_required: bool = True
    last_stable_checkpoint: str | None = None

    created_at: datetime
    updated_at: datetime
    event_seq: int = 0

    @classmethod
    def demo(cls) -> "NodeCheckpointSnapshot":
        now = datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc)
        return cls(
            snapshot_id="snapshot-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            task_id="task-1",
            trace_id="trace-1",
            node_id="generate_sql",
            graph_name="analysis_graph",
            node_name="generate_sql",
            node_status="running",
            previous_node="plan_analysis",
            next_node="sql_guard",
            resume_cursor="cursor-1",
            task_type="trend_analysis",
            task_summary="Analyze monthly revenue trend",
            current_step="generate_sql",
            current_goal="Generate read-only SQL",
            hot_context={"question": "Show revenue trend"},
            conversation_summary="User wants monthly revenue trend analysis.",
            confirmed_facts=["dataset-sales is authorized"],
            dataset_refs=["dataset-sales"],
            injected_context_version="v1",
            last_tool_name="sql_guard",
            last_tool_input_hash="hash-1",
            last_tool_output_ref="output-1",
            retry_count=1,
            tool_status="passed",
            llm_model="gpt-5",
            prompt_version="v1",
            token_usage=128,
            elapsed_ms=42,
            interrupt_reason="manual_checkpoint",
            failure_stage="node_exit",
            manual_restore_required=True,
            last_stable_checkpoint="cursor-1",
            created_at=now,
            updated_at=now,
            event_seq=7,
        )


__all__ = ["NodeCheckpointSnapshot"]
