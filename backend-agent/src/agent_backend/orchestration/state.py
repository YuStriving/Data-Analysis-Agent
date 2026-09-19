from __future__ import annotations

from typing import Any, Literal, TypedDict


DatasetSelectionSource = Literal["explicit", "session", "none"]
RequestSource = Literal["http", "kafka", "resume", "unknown"]


class TaskState(TypedDict, total=False):
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str
    question: str
    dataset_ids: list[str]
    access_context: dict[str, Any]
    task_type: str | None
    request_source: RequestSource


class GraphRuntimeState(TypedDict, total=False):
    node_id: str
    node_name: str
    node_status: str
    previous_node: str | None
    next_node: str | None
    resume_cursor: str | None
    event_seq: int
    events: list[dict[str, Any]]


class ContextRuntimeState(TypedDict, total=False):
    selected_dataset_id: str | None
    inferred_dataset: bool
    dataset_selection_source: DatasetSelectionSource
    recent_dataset_id: str | None
    dataset_metadata: dict[str, Any]
    dataset_metadata_by_id: dict[str, dict[str, Any]]
    dataset_context: dict[str, Any]
    schema_context: dict[str, Any]
    context_bundle: dict[str, Any]
    injected_context_version: str
    warnings: list[dict[str, Any]]


class AnalysisRuntimeState(TypedDict, total=False):
    pass


class OutputState(TypedDict, total=False):
    final_answer: str
    chart_spec: dict[str, Any]
    warnings: list[dict[str, Any]]


class ErrorState(TypedDict, total=False):
    has_error: bool
    error_code: str | None
    error_message: str | None
    failure_stage: str | None
    user_action_required: bool
    recoverable: bool


class AgentState(TypedDict, total=False):
    task: TaskState
    graph: GraphRuntimeState
    context: ContextRuntimeState
    analysis: AnalysisRuntimeState
    output: OutputState
    error: ErrorState

    # Flat fields are kept during the migration to nested graph state because
    # checkpoint capture/restore and the scaffold graph still read them.
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
    rendered_prompt_hash: str
    token_usage: int
    elapsed_ms: int
    interrupt_reason: str | None
    failure_stage: str | None
    manual_restore_required: bool
    last_stable_checkpoint: str | None
    event_seq: int
    snapshot_id: str
