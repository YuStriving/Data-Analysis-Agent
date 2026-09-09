from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agent_backend.capabilities.agent_runtime.memory.contracts import MemoryEvent, MemoryTurn
from agent_backend.capabilities.agent_runtime.memory.protocols import build_scope_key


class MongoMemoryStore:
    def __init__(
        self,
        client: Any,
        *,
        database_name: str = "backend_agent",
        turns_collection: str = "memory_turns",
        events_collection: str = "memory_events",
    ) -> None:
        self.client = client
        self.database_name = database_name
        self.turns_collection = turns_collection
        self.events_collection = events_collection

    @classmethod
    def from_uri(cls, uri: str, **kwargs: Any) -> "MongoMemoryStore":
        from pymongo import MongoClient

        return cls(MongoClient(uri, **kwargs))

    def _turns(self):
        return self.client[self.database_name][self.turns_collection]

    def _events(self):
        return self.client[self.database_name][self.events_collection]

    def save_turns(self, turns: Sequence[MemoryTurn]) -> None:
        collection = self._turns()
        for turn in turns:
            payload = turn.model_dump(mode="json")
            payload["scope_key"] = build_scope_key(turn.tenant_id, turn.user_id, turn.session_id)
            collection.update_one(
                {"turn_id": turn.turn_id},
                {"$setOnInsert": payload},
                upsert=True,
            )

    def save_events(self, events: Sequence[MemoryEvent]) -> None:
        collection = self._events()
        for event in events:
            payload = event.model_dump(mode="json")
            payload["scope_key"] = build_scope_key(event.tenant_id, event.user_id, event.session_id)
            collection.update_one(
                {"event_id": event.event_id},
                {"$setOnInsert": payload},
                upsert=True,
            )
