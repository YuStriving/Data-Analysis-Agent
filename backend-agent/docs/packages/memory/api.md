# Python Memory 接口文档

## 1. 公开函数

### `MemoryScope`

```python
scope = MemoryScope(user_id="user-1", session_id="session-1")
scope_key = scope.to_key()
```

`tenant_id` 默认值为 `default`。`session_id` 由 Java 后端生成或透传，Python Agent 只消费。

### `build_scope_key(tenant_id: str, user_id: str, session_id: str) -> str`

生成 `v1:{tenant_id}:{user_id}:{session_id}` 格式的隔离 key。

### `MemoryService`

```python
service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
service.record_turn(turn)
service.record_event(event)
service.flush_pending(scope) -> FlushResult
service.load_hot_context(scope_key) -> dict
```

关键行为：

1. `record_turn` 追加对话到待落库队列并更新热上下文。
2. `record_event` 追加强类型分析事件到待落库队列并更新热上下文。
3. `flush_pending` 先写 MongoDB，成功后裁剪本批已读取 Redis 队列。
3. `load_hot_context` 只读取 Redis 热上下文。
4. checkpoint 由 `agent_runtime.checkpoint` 独立模块负责。

## 2. Store 协议

### `PendingMemoryStore`

```python
class PendingMemoryStore(Protocol):
    def next_pending_seq(self, scope_key: str) -> int: ...
    def enqueue_item(self, item: PendingMemoryItem) -> None: ...
    def list_pending(self, scope_key: str, limit: int) -> list[PendingMemoryItem]: ...
    def trim_pending(self, scope_key: str, count: int) -> None: ...
    def move_to_dead_letter(self, scope_key: str, raw_item: str, reason: str) -> None: ...
    def acquire_flush_lock(self, scope_key: str, ttl_seconds: int) -> bool: ...
    def release_flush_lock(self, scope_key: str) -> None: ...
    def load_hot_context(self, scope_key: str) -> dict[str, Any]: ...
    def save_hot_context(self, scope_key: str, hot_context: dict[str, Any]) -> None: ...
```

### `DurableMemoryStore`

```python
class DurableMemoryStore(Protocol):
    def save_turns(self, turns: Sequence[MemoryTurn]) -> None: ...
    def save_events(self, events: Sequence[MemoryEvent]) -> None: ...
```

## 3. Redis 适配器

`RedisMemoryStore.from_url(url, **kwargs)` 创建客户端。

默认 key：

1. `backend-agent:memory:pending:{scope_key}`
2. `backend-agent:memory:hot:{scope_key}`
3. `backend-agent:memory:recent_turns:{scope_key}`
4. `backend-agent:memory:seq:{scope_key}`
5. `backend-agent:memory:flush_lock:{scope_key}`
6. `backend-agent:memory:dead:{scope_key}`

热上下文默认 TTL 为 `7200` 秒，最近对话保留 6 轮。

## 4. MongoDB 适配器

`MongoMemoryStore.from_uri(uri, **kwargs)` 创建客户端。

默认配置：

1. database：`backend_agent`
2. turns collection：`memory_turns`
3. events collection：`memory_events`

`save_turns` 与 `save_events` 使用自然 id 做 `$setOnInsert` upsert。

## 5. 核心数据模型

`MemoryTurn` 包含 `turn_id`、scope 身份、`role`、`content` 和 `created_at`。

`MemoryEvent` 包含 `event_id`、scope 身份、`event_type`、`event_seq`、强类型 `payload` 和 `created_at`。

`PendingMemoryItem` 包含 `item_id`、`item_type`、`scope`、`scope_key`、`pending_seq`、`payload` 和 `created_at`。

`MemoryEvent.payload` 使用 discriminated union，支持：

1. `QuestionReceivedPayload`
2. `DatasetResolvedPayload`
3. `SchemaLoadedPayload`
4. `SqlGeneratedPayload`
5. `SqlValidatedPayload`
6. `SqlRepairedPayload`
7. `QueryExecutedPayload`
8. `ResultSummarizedPayload`
9. `ChartBuiltPayload`
10. `AnswerGeneratedPayload`
11. `TaskFailedPayload`
