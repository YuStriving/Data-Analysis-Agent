from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agent_backend.capabilities.agent_runtime.context.contracts import SchemaContext


RuntimeTurnStatus = Literal[
    "completed",
    "failed",
    "missing_required_context",
    "context_budget_exceeded",
    "prompt_render_failed",
    "model_output_invalid",
]

RuntimeTurnEventType = Literal[
    "task_started",
    "context_building",
    "context_built",
    "context_missing_required",
    "prompt_rendering",
    "prompt_rendered",
    "prompt_render_failed",
    "context_budget_exceeded",
    "model_call_started",
    "model_call_finished",
    "model_output_invalid",
    "memory_recorded",
    "task_completed",
    "task_failed",
]


class RuntimeTurnEvent(BaseModel):
    task_id: str
    trace_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    event_type: RuntimeTurnEventType
    event_seq: int
    message: str = ""
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeTurnResult(BaseModel):
    task_id: str
    trace_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    status: RuntimeTurnStatus
    final_answer: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    prompt_version: str | None = None
    rendered_prompt_hash: str | None = None
    memory_event_ids: list[str] = Field(default_factory=list)
    runtime_event_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class RuntimeEventSink(Protocol):
    def publish(self, event: RuntimeTurnEvent) -> None: ...


class RuntimeModelClient(Protocol):
    model_name: str

    def complete(self, prompt: str) -> str: ...


class RuntimeSchemaProvider(Protocol):
    def load_schema(self, dataset_id: str) -> SchemaContext: ...


class InMemoryRuntimeEventSink:
    def __init__(self) -> None:
        self.events: list[RuntimeTurnEvent] = []

    def publish(self, event: RuntimeTurnEvent) -> None:
        self.events.append(event)

    def list_events(self, task_id: str, after_seq: int = 0) -> Sequence[RuntimeTurnEvent]:
        return [
            event
            for event in self.events
            if event.task_id == task_id and event.event_seq > after_seq
        ]
