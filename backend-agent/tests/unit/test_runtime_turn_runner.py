from __future__ import annotations

import json

from agent_backend.capabilities.agent_runtime.context.contracts import SchemaContext
from agent_backend.capabilities.agent_runtime.memory.service import MemoryService
from agent_backend.capabilities.agent_runtime.memory.contracts import PendingMemoryItem
from agent_backend.capabilities.agent_runtime.prompt import PromptBudgetGuard, PromptBudgetPolicy
from agent_backend.capabilities.agent_runtime.runtime_turn import (
    InMemoryRuntimeEventSink,
    RuntimeTurnDependencies,
    RuntimeTurnRunner,
)
from agent_backend.foundation.access import AccessContext
from agent_backend.foundation.contracts.task import AnalysisTaskRequest


class FakeRedisStore:
    def __init__(self) -> None:
        self.pending: dict[str, list[str]] = {}
        self.hot_context: dict[str, dict[str, object]] = {}
        self.seq: dict[str, int] = {}
        self.dead: dict[str, list[dict[str, str]]] = {}

    def next_pending_seq(self, scope_key: str) -> int:
        self.seq[scope_key] = self.seq.get(scope_key, 0) + 1
        return self.seq[scope_key]

    def enqueue_item(self, item: PendingMemoryItem) -> None:
        self.pending.setdefault(item.scope_key, []).append(json.dumps(item.model_dump(mode="json")))

    def list_pending_raw(self, scope_key: str, limit: int) -> list[str]:
        return self.pending.get(scope_key, [])[:limit]

    def list_pending(self, scope_key: str, limit: int) -> list[PendingMemoryItem]:
        return [
            PendingMemoryItem.model_validate(json.loads(raw))
            for raw in self.list_pending_raw(scope_key, limit)
        ]

    def trim_pending(self, scope_key: str, count: int) -> None:
        self.pending[scope_key] = self.pending.get(scope_key, [])[count:]

    def move_to_dead_letter(self, scope_key: str, raw_item: str, reason: str) -> None:
        self.dead.setdefault(scope_key, []).append({"raw_item": raw_item, "reason": reason})

    def acquire_flush_lock(self, scope_key: str, ttl_seconds: int) -> bool:
        return True

    def release_flush_lock(self, scope_key: str) -> None:
        return None

    def load_hot_context(self, scope_key: str) -> dict[str, object]:
        return dict(self.hot_context.get(scope_key, {}))

    def save_hot_context(self, scope_key: str, hot_context: dict[str, object]) -> None:
        self.hot_context[scope_key] = dict(hot_context)


class FakeMongoStore:
    def save_turns(self, turns) -> None:
        return None

    def save_events(self, events) -> None:
        return None


class FakeSchemaProvider:
    def __init__(self, schema_summary: str = "orders.order_date date, orders.amount decimal") -> None:
        self.schema_summary = schema_summary
        self.loaded_dataset_ids: list[str] = []

    def load_schema(self, dataset_id: str) -> SchemaContext:
        self.loaded_dataset_ids.append(dataset_id)
        return SchemaContext(
            schema_summary=self.schema_summary,
            metric_mapping={"revenue": "sum(orders.amount)"},
            time_field_hints={"orders": "order_date"},
        )


class FakeModelClient:
    model_name = "fake-model"

    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.output


def make_request(
    *,
    dataset_ids: list[str] | None = None,
    allowed_dataset_ids: list[str] | None = None,
) -> AnalysisTaskRequest:
    return AnalysisTaskRequest(
        task_id="task-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        question="Show monthly revenue trend",
        dataset_ids=dataset_ids or ["dataset-sales"],
        access_context=AccessContext(
            tenant_id="tenant-1",
            user_id="user-1",
            allowed_dataset_ids=allowed_dataset_ids or ["dataset-sales"],
            readonly=True,
        ),
    )


def make_runner(
    *,
    model_client: FakeModelClient | None = None,
    prompt_budget_guard: PromptBudgetGuard | None = None,
    schema_provider: FakeSchemaProvider | None = None,
) -> tuple[RuntimeTurnRunner, InMemoryRuntimeEventSink, FakeRedisStore, FakeModelClient]:
    event_sink = InMemoryRuntimeEventSink()
    redis_store = FakeRedisStore()
    memory_service = MemoryService(redis_store=redis_store, mongo_store=FakeMongoStore())
    active_model_client = model_client or FakeModelClient(
        json.dumps(
            {
                "status": "cannot_generate",
                "sql": "",
                "reason": "MVP mock model does not execute SQL.",
                "warnings": [],
            }
        )
    )
    runner = RuntimeTurnRunner(
        RuntimeTurnDependencies(
            event_sink=event_sink,
            memory_service=memory_service,
            model_client=active_model_client,
            schema_provider=schema_provider or FakeSchemaProvider(),
            prompt_budget_guard=prompt_budget_guard,
        )
    )
    return runner, event_sink, redis_store, active_model_client


def test_runtime_turn_runner_completes_generate_sql_prompt_flow() -> None:
    runner, event_sink, redis_store, model_client = make_runner()

    result = runner.run(make_request())

    assert result.status == "completed"
    assert result.prompt_version == "v1"
    assert result.rendered_prompt_hash is not None
    assert result.memory_event_ids == [
        "task-1:memory:question_received",
        "task-1:memory:answer_generated",
    ]
    assert result.runtime_event_count == len(event_sink.events)
    assert [event.event_type for event in event_sink.events] == [
        "task_started",
        "memory_recorded",
        "context_building",
        "context_built",
        "prompt_rendering",
        "prompt_rendered",
        "model_call_started",
        "model_call_finished",
        "memory_recorded",
        "task_completed",
    ]
    assert len(model_client.calls) == 1
    assert "权限约束" in model_client.calls[0]
    pending_payloads = [json.loads(raw)["payload"]["event_type"] for raw in next(iter(redis_store.pending.values()))]
    assert pending_payloads == ["question_received", "answer_generated"]


def test_runtime_turn_runner_stops_when_required_context_is_missing() -> None:
    runner, event_sink, redis_store, model_client = make_runner()

    result = runner.run(make_request(dataset_ids=["dataset-denied"]))

    assert result.status == "missing_required_context"
    assert result.failure_code == "missing_required_context"
    assert len(model_client.calls) == 0
    assert "context_missing_required" in [event.event_type for event in event_sink.events]
    pending_payloads = [json.loads(raw)["payload"]["event_type"] for raw in next(iter(redis_store.pending.values()))]
    assert pending_payloads == ["question_received", "task_failed"]


def test_runtime_turn_runner_stops_when_prompt_budget_is_exceeded() -> None:
    runner, event_sink, redis_store, model_client = make_runner(
        prompt_budget_guard=PromptBudgetGuard(
            PromptBudgetPolicy(max_rendered_prompt_chars=100, warn_at_ratio=0.8)
        )
    )

    result = runner.run(make_request())

    assert result.status == "context_budget_exceeded"
    assert result.rendered_prompt_hash is not None
    assert result.warnings == ["rendered_prompt_exceeded_budget"]
    assert len(model_client.calls) == 0
    assert "context_budget_exceeded" in [event.event_type for event in event_sink.events]
    pending_payloads = [json.loads(raw)["payload"]["event_type"] for raw in next(iter(redis_store.pending.values()))]
    assert pending_payloads == ["question_received", "task_failed"]


def test_runtime_turn_runner_reports_invalid_model_output() -> None:
    runner, event_sink, redis_store, model_client = make_runner(
        model_client=FakeModelClient("not-json")
    )

    result = runner.run(make_request())

    assert result.status == "model_output_invalid"
    assert len(model_client.calls) == 1
    assert "model_output_invalid" in [event.event_type for event in event_sink.events]
    pending_payloads = [json.loads(raw)["payload"]["event_type"] for raw in next(iter(redis_store.pending.values()))]
    assert pending_payloads == ["question_received", "task_failed"]
