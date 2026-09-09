from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from agent_backend.capabilities.agent_runtime.memory.contracts import PendingMemoryItem


class RedisMemoryStore:
    def __init__(
        self,
        client: Any,
        *,
        namespace: str = "backend-agent:memory",
        hot_context_ttl_seconds: int = 7_200,
    ) -> None:
        self.client = client
        self.namespace = namespace
        self.hot_context_ttl_seconds = hot_context_ttl_seconds
        self._lock_tokens: dict[str, str] = {}

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "RedisMemoryStore":
        from redis import Redis

        return cls(Redis.from_url(url, **kwargs))

    def _pending_key(self, scope_key: str) -> str:
        return f"{self.namespace}:pending:{scope_key}"

    def _hot_key(self, scope_key: str) -> str:
        return f"{self.namespace}:hot:{scope_key}"

    def _seq_key(self, scope_key: str) -> str:
        return f"{self.namespace}:seq:{scope_key}"

    def _flush_lock_key(self, scope_key: str) -> str:
        return f"{self.namespace}:flush_lock:{scope_key}"

    def _dead_key(self, scope_key: str) -> str:
        return f"{self.namespace}:dead:{scope_key}"

    def next_pending_seq(self, scope_key: str) -> int:
        return int(self.client.incr(self._seq_key(scope_key)))

    def enqueue_item(self, item: PendingMemoryItem) -> None:
        payload = item.model_dump(mode="json")
        self.client.rpush(self._pending_key(item.scope_key), json.dumps(payload, ensure_ascii=False))

    def list_pending_raw(self, scope_key: str, limit: int) -> list[str]:
        if limit <= 0:
            return []
        raw_items = self.client.lrange(self._pending_key(scope_key), 0, limit - 1)
        normalized_items: list[str] = []
        for raw_item in raw_items:
            if isinstance(raw_item, bytes):
                raw_item = raw_item.decode("utf-8")
            normalized_items.append(raw_item)
        return normalized_items

    def list_pending(self, scope_key: str, limit: int) -> list[PendingMemoryItem]:
        raw_items = self.list_pending_raw(scope_key, limit)
        pending_items: list[PendingMemoryItem] = []
        for raw_item in raw_items:
            pending_items.append(PendingMemoryItem.model_validate(json.loads(raw_item)))
        return pending_items

    def trim_pending(self, scope_key: str, count: int) -> None:
        if count <= 0:
            return
        self.client.ltrim(self._pending_key(scope_key), count, -1)

    def move_to_dead_letter(self, scope_key: str, raw_item: str, reason: str) -> None:
        payload = {
            "raw_item": raw_item,
            "reason": reason,
        }
        self.client.rpush(self._dead_key(scope_key), json.dumps(payload, ensure_ascii=False))

    def acquire_flush_lock(self, scope_key: str, ttl_seconds: int) -> bool:
        token = uuid4().hex
        acquired = self.client.set(self._flush_lock_key(scope_key), token, nx=True, ex=ttl_seconds)
        if acquired:
            self._lock_tokens[scope_key] = token
        return bool(acquired)

    def release_flush_lock(self, scope_key: str) -> None:
        token = self._lock_tokens.pop(scope_key, None)
        if token is None:
            return

        lock_key = self._flush_lock_key(scope_key)
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """
        self.client.eval(script, 1, lock_key, token)

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
