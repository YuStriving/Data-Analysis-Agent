from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from agent_backend.capabilities.agent_runtime.memory.contracts import (
    MemoryEvent,
    MemoryTurn,
    PendingMemoryItem,
)


def build_scope_key(tenant_id: str, user_id: str, session_id: str) -> str:
    return ":".join(("v1", tenant_id, user_id, session_id))


@runtime_checkable
class PendingMemoryStore(Protocol):
    def next_pending_seq(self, scope_key: str) -> int: ...

    def enqueue_item(self, item: PendingMemoryItem) -> None: ...

    def list_pending_raw(self, scope_key: str, limit: int) -> list[str]: ...

    def list_pending(self, scope_key: str, limit: int) -> list[PendingMemoryItem]: ...

    def trim_pending(self, scope_key: str, count: int) -> None: ...

    def move_to_dead_letter(self, scope_key: str, raw_item: str, reason: str) -> None: ...

    def acquire_flush_lock(self, scope_key: str, ttl_seconds: int) -> bool: ...

    def release_flush_lock(self, scope_key: str) -> None: ...

    def load_hot_context(self, scope_key: str) -> dict[str, Any]: ...

    def save_hot_context(self, scope_key: str, hot_context: dict[str, Any]) -> None: ...


@runtime_checkable
class DurableMemoryStore(Protocol):
    def save_turns(self, turns: Sequence[MemoryTurn]) -> None: ...

    def save_events(self, events: Sequence[MemoryEvent]) -> None: ...
