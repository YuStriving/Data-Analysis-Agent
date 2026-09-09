from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ContextSectionName = Literal[
    "identity",
    "request",
    "dataset",
    "schema",
    "conversation",
    "previous_turn",
    "repair",
    "execution_result",
    "chart",
    "runtime",
    "meta",
]


class ContextIdentity(BaseModel):
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str


class RequestContext(BaseModel):
    question: str
    task_type: str = "unknown"
    intent: str | None = None


class DatasetContext(BaseModel):
    available_dataset_ids: list[str] = Field(default_factory=list)
    selected_dataset_id: str | None = None
    last_used_dataset_id: str | None = None


class SchemaContext(BaseModel):
    schema_summary: str = ""
    semantic_schema_summary: str = ""
    metric_mapping: dict[str, str] = Field(default_factory=dict)
    time_field_hints: dict[str, str] = Field(default_factory=dict)
    field_summary: dict[str, Any] = Field(default_factory=dict)
    truncated: bool = False


class ConversationContext(BaseModel):
    conversation_summary: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class PreviousTurnContext(BaseModel):
    last_question: str | None = None
    last_sql: str | None = None
    last_result_summary: str | None = None
    last_chart_summary: str | None = None
    last_selected_dataset_id: str | None = None


class RepairContext(BaseModel):
    failed_sql: str | None = None
    error_message: str | None = None
    failure_stage: str | None = None
    retry_count: int = 0
    max_retry_count: int = 3
    avoid_errors: list[str] = Field(default_factory=list)


class ExecutionResultContext(BaseModel):
    executed_sql: str | None = None
    result_summary: str = ""
    table_preview: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False
    max_rows: int = 0


class ChartContext(BaseModel):
    chart_summary: str = ""
    last_chart_spec: dict[str, Any] | None = None
    target_chart_types: list[str] = Field(default_factory=lambda: ["bar", "line", "pie", "table"])


class RuntimeContext(BaseModel):
    agent_name: str
    agent_version: str = "v1"
    node_name: str
    node_id: str | None = None
    policy_name: str
    policy_version: str
    bundle_version: str = "v2"


class ContextMeta(BaseModel):
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    included_sections: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    truncated_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ContextBundle(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identity: ContextIdentity | None = None
    request: RequestContext | None = None
    dataset: DatasetContext | None = None
    schema_context: SchemaContext | None = Field(default=None, alias="schema")
    conversation: ConversationContext | None = None
    previous_turn: PreviousTurnContext | None = None
    repair: RepairContext | None = None
    execution_result: ExecutionResultContext | None = None
    chart: ChartContext | None = None
    runtime: RuntimeContext | None = None
    meta: ContextMeta | None = None


class ContextSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identity: ContextIdentity
    request: RequestContext
    dataset: DatasetContext | None = None
    schema_context: SchemaContext | None = Field(default=None, alias="schema")
    conversation: ConversationContext | None = None
    previous_turn: PreviousTurnContext | None = None
    repair: RepairContext | None = None
    execution_result: ExecutionResultContext | None = None
    chart: ChartContext | None = None
    runtime: RuntimeContext | None = None


class ContextPolicy(BaseModel):
    policy_name: str
    policy_version: str = "v2"
    agent_name: str
    node_name: str
    allowed_sections: list[ContextSectionName]
    required_sections: list[ContextSectionName]
    max_schema_chars: int | None = None
    max_conversation_chars: int | None = None
    max_previous_turns: int = 1
    max_repair_items: int = 3
    include_raw_rows: bool = False


class ContextBuildResult(BaseModel):
    status: Literal["ok", "missing_required_context"]
    bundle: ContextBundle | None = None
    missing_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ContextInjectionBundle(BaseModel):
    task_type: str
    injection_strategy: str
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str
    dataset_ids: list[str] = Field(default_factory=list)
    hot_context: dict[str, str] = Field(default_factory=dict)
    confirmed_facts: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
    injected_context_version: str = "v1"
