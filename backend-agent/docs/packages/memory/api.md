# Python Memory 接口文档

## 1. 公开函数

### `build_scope_key(tenant_id: str, user_id: str, session_id: str) -> str`

生成 `tenant_id:user_id:session_id` 格式的隔离 key。

### `MemoryService`

```python
service = MemoryService(redis_store=redis_store, mongo_store=mongo_store)
service.enqueue_turn(item)
service.flush_pending(scope_key) -> int
service.load_hot_context(scope_key) -> dict
service.save_checkpoint(snapshot)
```

关键行为：

1. `enqueue_turn` 追加待落库队列并保存热上下文。
2. `flush_pending` 先写 MongoDB，成功后清空 Redis 队列。
3. `load_hot_context` 只读取 Redis 热上下文。
4. `save_checkpoint` 将快照写入 MongoDB。

## 2. Store 协议

### `PendingMemoryStore`

```python
class PendingMemoryStore(Protocol):
    def enqueue_turn(self, item: PendingMemoryItem) -> None: ...
    def list_pending(self, scope_key: str) -> list[PendingMemoryItem]: ...
    def clear_pending(self, scope_key: str) -> None: ...
    def load_hot_context(self, scope_key: str) -> dict[str, Any]: ...
    def save_hot_context(self, scope_key: str, hot_context: dict[str, Any]) -> None: ...
```

### `DurableMemoryStore`

```python
class DurableMemoryStore(Protocol):
    def save_turns(self, turns: Sequence[MemoryTurn]) -> None: ...
    def save_checkpoint(self, snapshot: NodeCheckpointSnapshot) -> None: ...
```

## 3. Redis 适配器

`RedisMemoryStore.from_url(url, **kwargs)` 创建客户端。

默认 key：

1. `backend-agent:memory:pending:{scope_key}`
2. `backend-agent:memory:hot:{scope_key}`

热上下文默认 TTL 为 `86400` 秒。

## 4. MongoDB 适配器

`MongoMemoryStore.from_uri(uri, **kwargs)` 创建客户端。

默认配置：

1. database：`backend_agent`
2. turns collection：`memory_turns`
3. checkpoints collection：`memory_checkpoints`

`save_turns` 与 `save_checkpoint` 使用自然 id 做 `$setOnInsert` upsert。

## 5. 核心数据模型

`MemoryTurn` 包含 `turn_id`、scope 身份、`role`、`content` 和 `created_at`。

`PendingMemoryItem` 包含 `turn`、`scope_key`、`pending_seq`。

`NodeCheckpointSnapshot` 包含八个核心字段组：

1. identity
2. graph_state
3. task_state
4. context_state
5. tool_state
6. execution_state
7. recovery_state
8. audit_state
