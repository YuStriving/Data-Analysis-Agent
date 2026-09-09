from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class MemoryScope(BaseModel):
    tenant_id: str = "default"
    user_id: str
    session_id: str

    @field_validator("tenant_id", "user_id", "session_id")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("memory scope fields must not be blank")
        return value

    def to_key(self) -> str:
        from agent_backend.capabilities.agent_runtime.memory.protocols import build_scope_key

        return build_scope_key(self.tenant_id, self.user_id, self.session_id)


class RecentTurn(BaseModel):
    task_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChartSummary(BaseModel):
    chart_type: Literal["bar", "line", "pie", "table"]
    title: str
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None
    chart_ref: str | None = None


class HotContext(BaseModel):
    scope: MemoryScope
    selected_dataset_id: str | None = None
    recent_dataset_ids: list[str] = Field(default_factory=list)
    last_task_id: str | None = None
    last_question: str | None = None
    last_sql: str | None = None
    last_result_summary: str | None = None
    last_chart_summary: ChartSummary | None = None
    repair_lessons: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
    updated_at: datetime


class MemoryTurn(BaseModel):
    turn_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    task_id: str
    trace_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    @property
    def scope(self) -> MemoryScope:
        return MemoryScope(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )


class QuestionReceivedPayload(BaseModel):
    type: Literal["question_received"] = "question_received"
    question: str
    dataset_ids: list[str] = Field(default_factory=list)
    selected_dataset_id: str | None = None
    user_intent_hint: str | None = None


class DatasetResolvedPayload(BaseModel):
    type: Literal["dataset_resolved"] = "dataset_resolved"
    available_dataset_ids: list[str]
    selected_dataset_id: str | None = None
    selection_source: Literal[
        "explicit_user_selection",
        "session_recent_dataset",
        "single_available_dataset",
        "unresolved",
    ]
    selection_reason: str


class SchemaLoadedPayload(BaseModel):
    type: Literal["schema_loaded"] = "schema_loaded"
    dataset_id: str
    datasource_type: Literal["mysql", "csv", "xls", "xlsx"]
    schema_summary: str
    table_count: int | None = None
    field_count: int | None = None
    truncated: bool = False
    schema_ref: str | None = None


class SqlGeneratedPayload(BaseModel):
    type: Literal["sql_generated"] = "sql_generated"
    sql: str
    sql_dialect: Literal["mysql", "duckdb"] = "mysql"
    dataset_ids: list[str]
    selected_dataset_id: str
    prompt_version: str
    model: str


class SqlValidatedPayload(BaseModel):
    type: Literal["sql_validated"] = "sql_validated"
    sql: str
    passed: bool
    readonly: bool
    risk_reasons: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class SqlRepairedPayload(BaseModel):
    type: Literal["sql_repaired"] = "sql_repaired"
    failed_sql: str
    error_message: str
    failure_stage: Literal["validate_sql", "execute_sql"]
    repaired_sql: str
    retry_count: int
    max_retry_count: int
    lesson: str | None = None


class QueryExecutedPayload(BaseModel):
    type: Literal["query_executed"] = "query_executed"
    sql: str
    status: Literal["success", "failed", "timeout"]
    row_count: int | None = None
    elapsed_ms: int
    truncated: bool = False
    max_rows: int
    result_ref: str | None = None
    error_message: str | None = None


class KeyMetric(BaseModel):
    name: str
    value: str | int | float | bool | None
    unit: str | None = None


class ResultSummarizedPayload(BaseModel):
    type: Literal["result_summarized"] = "result_summarized"
    summary: str
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    row_count: int | None = None
    truncated: bool = False
    result_ref: str | None = None


class ChartBuiltPayload(BaseModel):
    type: Literal["chart_built"] = "chart_built"
    chart_type: Literal["bar", "line", "pie", "table"]
    title: str
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None
    chart_ref: str | None = None


class AnswerGeneratedPayload(BaseModel):
    type: Literal["answer_generated"] = "answer_generated"
    answer: str
    has_table_preview: bool = False
    has_chart: bool = False
    result_ref: str | None = None
    chart_ref: str | None = None


class TaskFailedPayload(BaseModel):
    type: Literal["task_failed"] = "task_failed"
    failure_stage: str
    error_message: str
    retry_count: int = 0
    final: bool = True


MemoryEventType = Literal[
    "question_received",
    "dataset_resolved",
    "schema_loaded",
    "sql_generated",
    "sql_validated",
    "sql_repaired",
    "query_executed",
    "result_summarized",
    "chart_built",
    "answer_generated",
    "task_failed",
]

MemoryEventPayload = Annotated[
    QuestionReceivedPayload
    | DatasetResolvedPayload
    | SchemaLoadedPayload
    | SqlGeneratedPayload
    | SqlValidatedPayload
    | SqlRepairedPayload
    | QueryExecutedPayload
    | ResultSummarizedPayload
    | ChartBuiltPayload
    | AnswerGeneratedPayload
    | TaskFailedPayload,
    Field(discriminator="type"),
]


class MemoryEvent(BaseModel):
    event_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    task_id: str
    trace_id: str
    event_type: MemoryEventType
    event_seq: int
    payload: MemoryEventPayload
    created_at: datetime

    @model_validator(mode="after")
    def validate_payload_type(self) -> "MemoryEvent":
        if self.event_type != self.payload.type:
            raise ValueError("event_type must match payload.type")
        return self

    @property
    def scope(self) -> MemoryScope:
        return MemoryScope(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
        )


class PendingMemoryItem(BaseModel):
    item_id: str
    item_type: Literal["turn", "event"]
    scope: MemoryScope
    scope_key: str
    pending_seq: int
    payload: MemoryTurn | MemoryEvent
    created_at: datetime

    @model_validator(mode="after")
    def validate_payload_type(self) -> "PendingMemoryItem":
        if self.item_type == "turn" and not isinstance(self.payload, MemoryTurn):
            raise ValueError("turn pending item must carry MemoryTurn payload")
        if self.item_type == "event" and not isinstance(self.payload, MemoryEvent):
            raise ValueError("event pending item must carry MemoryEvent payload")
        if self.scope_key != self.scope.to_key():
            raise ValueError("scope_key must match scope")
        return self

    @property
    def turn(self) -> MemoryTurn:
        if not isinstance(self.payload, MemoryTurn):
            raise TypeError("pending item does not carry a MemoryTurn")
        return self.payload

    @property
    def event(self) -> MemoryEvent:
        if not isinstance(self.payload, MemoryEvent):
            raise TypeError("pending item does not carry a MemoryEvent")
        return self.payload

    @classmethod
    def from_turn(cls, turn: MemoryTurn, *, pending_seq: int) -> "PendingMemoryItem":
        scope = turn.scope
        return cls(
            item_id=turn.turn_id,
            item_type="turn",
            scope=scope,
            scope_key=scope.to_key(),
            pending_seq=pending_seq,
            payload=turn,
            created_at=turn.created_at,
        )

    @classmethod
    def from_event(cls, event: MemoryEvent, *, pending_seq: int) -> "PendingMemoryItem":
        scope = event.scope
        return cls(
            item_id=event.event_id,
            item_type="event",
            scope=scope,
            scope_key=scope.to_key(),
            pending_seq=pending_seq,
            payload=event,
            created_at=event.created_at,
        )

    @classmethod
    def demo(cls) -> "PendingMemoryItem":
        turn = MemoryTurn(
            turn_id="turn-1",
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            task_id="task-1",
            trace_id="trace-1",
            role="assistant",
            content="monthly revenue trend",
            created_at=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        )
        return cls.from_turn(turn, pending_seq=1)


class FlushResult(BaseModel):
    scope_key: str
    status: Literal["flushed", "empty", "locked", "failed", "partial_invalid"]
    read_count: int = 0
    flushed_turn_count: int = 0
    flushed_event_count: int = 0
    dead_letter_count: int = 0
    error_message: str | None = None
