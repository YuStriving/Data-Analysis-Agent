from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from agent_backend.foundation.contracts.memory import MemoryTurn, NodeCheckpointSnapshot, PendingMemoryItem


def build_scope_key(tenant_id: str, user_id: str, session_id: str) -> str:
    return ":".join((tenant_id, user_id, session_id))


@runtime_checkable
class PendingMemoryStore(Protocol):
    def enqueue_turn(self, item: PendingMemoryItem) -> None: ...

    def list_pending(self, scope_key: str) -> list[PendingMemoryItem]: ...

    def clear_pending(self, scope_key: str) -> None: ...

    def load_hot_context(self, scope_key: str) -> dict[str, Any]: ...

    def save_hot_context(self, scope_key: str, hot_context: dict[str, Any]) -> None: ...


@runtime_checkable
class DurableMemoryStore(Protocol):
    def save_turns(self, turns: Sequence[MemoryTurn]) -> None: ...

    def save_checkpoint(self, snapshot: NodeCheckpointSnapshot) -> None: ...
