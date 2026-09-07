from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from shared_models.memory import PendingMemoryItem


class RedisMemoryStore:
    def __init__(
        self,
        client: Any,
        *,
        namespace: str = "backend-agent:memory",
        hot_context_ttl_seconds: int = 86_400,
    ) -> None:
        self.client = client
        self.namespace = namespace
        self.hot_context_ttl_seconds = hot_context_ttl_seconds

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "RedisMemoryStore":
        from redis import Redis

        return cls(Redis.from_url(url, **kwargs))

    def _pending_key(self, scope_key: str) -> str:
        return f"{self.namespace}:pending:{scope_key}"

    def _hot_key(self, scope_key: str) -> str:
        return f"{self.namespace}:hot:{scope_key}"

    def enqueue_turn(self, item: PendingMemoryItem) -> None:
        payload = item.model_dump(mode="json")
        self.client.rpush(self._pending_key(item.scope_key), json.dumps(payload, ensure_ascii=False))

    def list_pending(self, scope_key: str) -> list[PendingMemoryItem]:
        raw_items = self.client.lrange(self._pending_key(scope_key), 0, -1)
        pending_items: list[PendingMemoryItem] = []
        for raw_item in raw_items:
            if isinstance(raw_item, bytes):
                raw_item = raw_item.decode("utf-8")
            pending_items.append(PendingMemoryItem.model_validate(json.loads(raw_item)))
        return pending_items

    def clear_pending(self, scope_key: str) -> None:
        self.client.delete(self._pending_key(scope_key))

    def load_hot_context(self, scope_key: str) -> dict[str, Any]:
        raw_value = self.client.get(self._hot_key(scope_key))
        if raw_value is None:
            return {}
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)

    def save_hot_context(self, scope_key: str, hot_context: dict[str, Any]) -> None:
        self.client.set(
            self._hot_key(scope_key),
            json.dumps(hot_context, ensure_ascii=False, sort_keys=True),
            ex=self.hot_context_ttl_seconds,
        )
