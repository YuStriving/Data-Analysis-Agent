from __future__ import annotations

from typing import Any

from shared_models.memory import MemoryTurn, NodeCheckpointSnapshot, PendingMemoryItem

from memory.store import DurableMemoryStore, PendingMemoryStore, build_scope_key


class MemoryService:
    def __init__(
        self,
        *,
        redis_store: PendingMemoryStore,
        mongo_store: DurableMemoryStore,
    ) -> None:
        self.redis_store = redis_store
        self.mongo_store = mongo_store

    def enqueue_turn(self, item: PendingMemoryItem) -> None:
        self.redis_store.enqueue_turn(item)
        hot_context = {
            "last_turn_id": item.turn.turn_id,
            "last_role": item.turn.role,
            "last_content": item.turn.content,
            "pending_seq": str(item.pending_seq),
        }
        self.redis_store.save_hot_context(item.scope_key, hot_context)

    def load_hot_context(self, scope_key: str) -> dict[str, Any]:
        return self.redis_store.load_hot_context(scope_key)

    def save_checkpoint(self, snapshot: NodeCheckpointSnapshot) -> None:
        self.mongo_store.save_checkpoint(snapshot)

    def flush_pending(self, scope_key: str) -> int:
        pending_items = self.redis_store.list_pending(scope_key)
        if not pending_items:
            return 0

        turns = [item.turn for item in pending_items]
        self.mongo_store.save_turns(turns)
        self.redis_store.clear_pending(scope_key)
        return len(pending_items)

    @staticmethod
    def scope_key_for(turn: MemoryTurn) -> str:
        return build_scope_key(turn.tenant_id, turn.user_id, turn.session_id)

    @staticmethod
    def scope_key_from_parts(tenant_id: str, user_id: str, session_id: str) -> str:
        return build_scope_key(tenant_id, user_id, session_id)
