from __future__ import annotations

import pytest

from memory.service import MemoryService
from shared_models.memory import PendingMemoryItem


class FakeRedisStore:
    def __init__(self) -> None:
        self.pending: dict[str, list[PendingMemoryItem]] = {}
        self.hot_context: dict[str, dict[str, object]] = {}

    def enqueue_turn(self, item: PendingMemoryItem) -> None:
        self.pending.setdefault(item.scope_key, []).append(item)

    def list_pending(self, scope_key: str) -> list[PendingMemoryItem]:
        return list(self.pending.get(scope_key, []))

    def clear_pending(self, scope_key: str) -> None:
        self.pending.pop(scope_key, None)

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
        self.saved_checkpoints: list[str] = []

    def save_turns(self, turns) -> None:
        if self.should_fail:
            raise RuntimeError("mongo write failed")
        for turn in turns:
            if turn.turn_id not in self.saved_turn_ids:
                self.saved_turn_ids.append(turn.turn_id)

    def save_checkpoint(self, snapshot) -> None:
        if self.should_fail:
            raise RuntimeError("mongo write failed")
        self.saved_checkpoints.append(snapshot.snapshot_id)


def test_flush_clears_redis_only_after_mongo_commit() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore()
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)

    service.enqueue_turn(PendingMemoryItem.demo())
    count = service.flush_pending("tenant-1:user-1:session-1")

    assert count == 1
    assert redis_store.pending_count("tenant-1:user-1:session-1") == 0
    assert mongo_store.saved_turn_ids == ["turn-1"]


def test_flush_keeps_redis_when_mongo_write_fails() -> None:
    redis_store = FakeRedisStore()
    mongo_store = FakeMongoStore(should_fail=True)
    service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)

    service.enqueue_turn(PendingMemoryItem.demo())

    with pytest.raises(RuntimeError, match="mongo write failed"):
        service.flush_pending("tenant-1:user-1:session-1")

    assert redis_store.pending_count("tenant-1:user-1:session-1") == 1
