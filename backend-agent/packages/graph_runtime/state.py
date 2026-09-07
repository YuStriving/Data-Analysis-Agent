from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str
    question: str
    dataset_ids: list[str]
    task_type: str
    node_id: str
    node_name: str
    node_status: str
    previous_node: str | None
    next_node: str | None
    resume_cursor: str | None
    task_summary: str
    current_step: str
    current_goal: str
    hot_context: dict[str, str]
    conversation_summary: str
    confirmed_facts: list[str]
    injected_context_version: str
    last_tool_name: str | None
    last_tool_input_hash: str | None
    last_tool_output_ref: str | None
    retry_count: int
    tool_status: str | None
    llm_model: str
    prompt_version: str
    token_usage: int
    elapsed_ms: int
    interrupt_reason: str | None
    failure_stage: str | None
    manual_restore_required: bool
    last_stable_checkpoint: str | None
    event_seq: int
    snapshot_id: str
