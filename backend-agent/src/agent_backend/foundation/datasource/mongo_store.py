from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agent_backend.foundation.contracts.memory import MemoryTurn, NodeCheckpointSnapshot

from agent_backend.foundation.datasource.memory_contracts import build_scope_key


class MongoMemoryStore:
    def __init__(
        self,
        client: Any,
        *,
        database_name: str = "backend_agent",
        turns_collection: str = "memory_turns",
        checkpoints_collection: str = "memory_checkpoints",
    ) -> None:
        self.client = client
        self.database_name = database_name
        self.turns_collection = turns_collection
        self.checkpoints_collection = checkpoints_collection

    @classmethod
    def from_uri(cls, uri: str, **kwargs: Any) -> "MongoMemoryStore":
        from pymongo import MongoClient

        return cls(MongoClient(uri, **kwargs))

    def _turns(self):
        return self.client[self.database_name][self.turns_collection]

    def _checkpoints(self):
        return self.client[self.database_name][self.checkpoints_collection]

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

    def save_checkpoint(self, snapshot: NodeCheckpointSnapshot) -> None:
        collection = self._checkpoints()
        payload = snapshot.model_dump(mode="json")
        collection.update_one(
            {"snapshot_id": snapshot.snapshot_id},
            {"$setOnInsert": payload},
            upsert=True,
        )
