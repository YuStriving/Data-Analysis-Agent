from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent_backend.capabilities.agent_runtime.memory.service import MemoryService
from agent_backend.capabilities.agent_runtime.memory.contracts import (
    AnswerGeneratedPayload,
    MemoryEvent,
    MemoryScope,
    MemoryTurn,
    PendingMemoryItem,
    QuestionReceivedPayload,
)


class FakeRedisStore:
    def __init__(self, *, locked: bool = False) -> None:
        self.locked = locked
        self.pending: dict[str, list[str]] = {}
        self.dead: dict[str, list[dict[str, str]]] = {}
        self.hot_context: dict[str, dict[str, object]] = {}
        self.seq: dict[str, int] = {}
        self.trimmed: list[tuple[str, int]] = []

    def next_pending_seq(self, scope_key: str) -> int:
        self.seq[scope_key] = self.seq.get(scope_key, 0) + 1
        return self.seq[scope_key]

    def enqueue_item(self, item: PendingMemoryItem) -> None:
        self.pending.setdefault(item.scope_key, []).append(json.dumps(item.model_dump(mode="json")))

    def list_pending_raw(self, scope_key: str, limit: int) -> list[str]:
        return list(self.pending.get(scope_key, [])[:limit])

    def list_pending(self, scope_key: str, limit: int) -> list[PendingMemoryItem]:
        return [PendingMemoryItem.model_validate(json.loads(raw)) for raw in self.list_pending_raw(scope_key, limit)]

    def trim_pending(self, scope_key: str, count: int) -> None:
        self.trimmed.append((scope_key, count))
        self.pending[scope_key] = self.pending.get(scope_key, [])[count:]

    def move_to_dead_letter(self, scope_key: str, raw_item: str, reason: str) -> None:
        self.dead.setdefault(scope_key, []).append({"raw_item": raw_item, "reason": reason})

    def acquire_flush_lock(self, scope_key: str, ttl_seconds: int) -> bool:
        return not self.locked

    def release_flush_lock(self, scope_key: str) -> None:
        return None

    def load_hot_context(self, scope_key: str) -> dict[str, object]:
        return dict(self.hot_context.get(scope_key, {}))

    def save_hot_context(self, scope_key: str, hot_context: dict[str, object]) -> None:
        self.hot_context[scope_key] = dict(hot_context)

    def pending_count(self, scope_key: str) -> int:
        return len(self.pending.get(scope_key, []))


class FakeMongoStore:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.saved_turn_ids: list[str] = []
        self.saved_event_ids: list[str] = []

    def save_turns(self, turns) -> None:
        if self.should_fail:
            raise RuntimeError("mongo write failed")
        for turn in turns:
            if turn.turn_id not in self.saved_turn_ids:
                self.saved_turn_ids.append(turn.turn_id)

    def save_events(self, events) -> None:
        if self.should_fail:
            raise RuntimeError("mongo write failed")
        for event in events:
            if event.event_id not in self.saved_event_ids:
                self.saved_event_ids.append(event.event_id)


def make_turn(turn_id: str = "turn-1", role: str = "assistant") -> MemoryTurn:
    return MemoryTurn(
        turn_id=turn_id,
        tenant_id="default",
        user_id="user-1",
        session_id="session-1",
        task_id="task-1",
        trace_id="trace-1",
        role=role,
        content="monthly revenue trend",
        created_at=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
    )


def make_event(event_id: str = "event-1") -> MemoryEvent:
    return MemoryEvent(
        event_id=event_id,
        tenant_id="default",
        user_id="user-1",
        session_id="session-1",
        task_id="task-1",
        trace_id="trace-1",
        event_type="answer_generated",
        event_seq=1,
        payload=AnswerGeneratedPayload(answer="The answer", has_chart=True),
        created_at=datetime(2026, 9, 7, 0, 0, 1, tzinfo=timezone.utc),
    )


def test_scope_key_uses_v1_prefix_and_default_tenant() -> None:
    scope = MemoryScope(user_id="user-1", session_id="session-1")

    assert scope.to_key() == "v1:default:user-1:session-1"


def test_record_turn_enqueues_pending_and_keeps_recent_six_turns() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()

    for index in range(7):
        service.record_turn(make_turn(turn_id=f"turn-{index}", role="user" if index % 2 == 0 else "assistant"))

    hot_context = redis_store.load_hot_context(scope_key)

    assert redis_store.pending_count(scope_key) == 7
    assert hot_context["last_turn_id"] == "turn-6"
    assert len(hot_context["recent_turns"]) == 6
    assert hot_context["recent_turns"][0]["task_id"] == "task-1"


def test_record_event_enqueues_pending_and_updates_hot_context() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()

    service.record_event(
        MemoryEvent(
            event_id="event-question",
            user_id="user-1",
            session_id="session-1",
            task_id="task-1",
            trace_id="trace-1",
            event_type="question_received",
            event_seq=1,
            payload=QuestionReceivedPayload(question="Show revenue", dataset_ids=["dataset-sales"]),
            created_at=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        )
    )

    hot_context = redis_store.load_hot_context(scope_key)

    assert redis_store.pending_count(scope_key) == 1
    assert hot_context["last_question"] == "Show revenue"
    assert hot_context["last_event_id"] == "event-question"


def test_memory_event_requires_event_type_to_match_payload_type() -> None:
    with pytest.raises(ValidationError, match="event_type must match payload.type"):
        MemoryEvent(
            event_id="event-bad",
            user_id="user-1",
            session_id="session-1",
            task_id="task-1",
            trace_id="trace-1",
            event_type="answer_generated",
            event_seq=1,
            payload=QuestionReceivedPayload(question="Show revenue"),
            created_at=datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc),
        )


def test_flush_trims_only_read_batch_after_mongo_commit() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store, flush_batch_size=1)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()

    service.record_turn(make_turn("turn-1"))
    service.record_turn(make_turn("turn-2"))
    result = service.flush_pending(scope_key)

    assert result.status == "flushed"
    assert result.read_count == 1
    assert result.flushed_turn_count == 1
    assert redis_store.pending_count(scope_key) == 1
    assert redis_store.trimmed == [(scope_key, 1)]
    assert mongo_store.saved_turn_ids == ["turn-1"]


def test_flush_keeps_redis_when_mongo_write_fails() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore(should_fail=True)
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()

    service.record_turn(make_turn())
    result = service.flush_pending(scope_key)

    assert result.status == "failed"
    assert result.error_message == "mongo write failed"
    assert redis_store.pending_count(scope_key) == 1
    assert redis_store.trimmed == []


def test_flush_writes_turns_and_events_to_separate_collections() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()

    service.record_turn(make_turn())
    service.record_event(make_event())
    result = service.flush_pending(MemoryScope(user_id="user-1", session_id="session-1"))

    assert result.status == "flushed"
    assert result.flushed_turn_count == 1
    assert result.flushed_event_count == 1
    assert mongo_store.saved_turn_ids == ["turn-1"]
    assert mongo_store.saved_event_ids == ["event-1"]
    assert redis_store.pending_count(scope_key) == 0


def test_flush_moves_invalid_item_to_dead_letter_and_trims_batch() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
    scope_key = MemoryScope(user_id="user-1", session_id="session-1").to_key()
    redis_store.pending[scope_key] = ["{bad-json"]

    result = service.flush_pending(scope_key)

    assert result.status == "partial_invalid"
    assert result.dead_letter_count == 1
    assert redis_store.pending_count(scope_key) == 0
    assert len(redis_store.dead[scope_key]) == 1


def test_flush_skips_when_lock_is_held() -> None:
    redis_store = FakeRedisStore(locked=True)
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)

    result = service.flush_pending(MemoryScope(user_id="user-1", session_id="session-1"))

    assert result.status == "locked"
