# Memory 架构文档

## 1. 架构目标

`memory` 的目标是提供一个可靠的 session 记忆 Module。

它的关键原则：

```text
按 scope 隔离
先写 Redis pending
再 flush 到 MongoDB
MongoDB upsert 保证幂等
Redis trim 只删除已成功处理的批次
```

外部调用方不需要知道 Redis key 怎么拼、MongoDB 怎么 upsert、锁怎么获取。

核心 Interface 是：

```python
record_turn(turn) -> PendingMemoryItem
record_event(event) -> PendingMemoryItem
flush_pending(scope) -> FlushResult
load_hot_context(scope_key) -> dict
```

## 2. 模块结构

```text
capabilities/agent_runtime/memory/
  __init__.py
  contracts.py
  protocols.py
  redis_store.py
  mongo_store.py
  service.py
```

### contracts.py

定义 memory 的数据模型。

主要模型：

```text
MemoryScope
MemoryTurn
MemoryEvent
PendingMemoryItem
FlushResult
HotContext
RecentTurn
各类 MemoryEvent payload
```

### protocols.py

定义存储 adapter 的 Interface。

主要 Interface：

```text
PendingMemoryStore
DurableMemoryStore
```

`MemoryService` 依赖这些 Interface，而不是直接依赖某个 Redis 或 MongoDB
实现。

### redis_store.py

Redis adapter。

负责：

```text
生成 pending_seq
写入 pending queue
读取 pending queue
LTRIM pending queue
保存 hot context
移动坏数据到 dead letter
获取和释放 flush lock
```

### mongo_store.py

MongoDB adapter。

负责：

```text
save_turns
save_events
```

写入使用自然 ID upsert。

### service.py

Memory 的主要编排层。

它把 contracts、Redis adapter、MongoDB adapter 串起来，提供给 workflow 调用。

## 3. Scope 设计

Scope 格式：

```text
v1:{tenant_id}:{user_id}:{session_id}
```

为什么需要这三个字段：

```text
tenant_id：后续多租户或团队空间预留，MVP 默认 default
user_id：隔离不同用户
session_id：隔离不同对话窗口
```

为什么不包含 `task_id`：

```text
task_id 表示一次任务；
session_id 表示一组连续对话。
```

多轮追问需要跨 task 复用记忆，所以 `task_id` 不能作为记忆 scope。

## 4. 写入流程

### 4.1 record_turn

```text
MemoryTurn
-> scope.to_key()
-> Redis INCR 获取 pending_seq
-> PendingMemoryItem.from_turn
-> enqueue_item 写入 Redis pending
-> 更新 hot context
-> 追加 recent_turns
```

`MemoryTurn` 只保存用户和助手最终可见消息。

### 4.2 record_event

```text
MemoryEvent
-> scope.to_key()
-> Redis INCR 获取 pending_seq
-> PendingMemoryItem.from_event
-> enqueue_item 写入 Redis pending
-> 根据 payload 更新 hot context
```

`MemoryEvent` 保存 Agent 内部过程。

典型事件：

```text
question_received
dataset_resolved
schema_loaded
sql_generated
sql_validated
sql_repaired
query_executed
result_summarized
chart_built
answer_generated
task_failed
```

## 5. Flush 流程

`flush_pending(scope)` 的目标是把 Redis pending 中的数据安全写入 MongoDB。

流程：

```text
1. 根据 scope 得到 scope_key。
2. 获取 Redis flush lock。
3. 获取失败则返回 locked。
4. 读取 pending queue 的前 N 条。
5. 如果没有数据，返回 empty。
6. 逐条反序列化 PendingMemoryItem。
7. 坏 JSON 或校验失败的数据移入 dead letter。
8. 合法数据按 pending_seq 排序。
9. 拆成 turns 和 events。
10. save_turns 写入 MongoDB。
11. save_events 写入 MongoDB。
12. 两类写入都成功后，LTRIM 删除本批读取长度。
13. 释放 lock。
```

重要约束：

```text
MongoDB 写入失败时不能 LTRIM。
LTRIM 只能删除本批读取数量，不能删除整个 pending key。
```

## 6. 幂等策略

Memory 的核心要求是：

```text
可以重复处理，不能丢数据。
```

MongoDB 写入使用：

```text
turn_id 唯一
event_id 唯一
```

重复 flush 时，同一条 turn 或 event 会 upsert 到同一个自然 ID，不会重复生成
多条记录。

## 7. Hot Context 更新

`MemoryService` 会根据事件类型更新 hot context。

例如：

```text
question_received -> last_question, selected_dataset_id
sql_generated -> last_sql, selected_dataset_id
sql_repaired -> last_sql, repair_lessons
result_summarized -> last_result_summary, last_result_ref
chart_built -> last_chart_summary
answer_generated -> last_answer, last_result_ref, last_chart_ref
```

这些 hot context 后续可以成为 `ContextSource` 的原材料。

## 8. Dead Letter

如果 pending 中某条数据无法解析：

```text
坏 JSON
payload 校验失败
event_type 和 payload.type 不一致
```

这条数据不应该阻塞整批 flush。它会被移动到 dead letter，合法数据继续处理。

## 9. 与其他模块的关系

### 与 context_hub

memory 提供上下文原材料，`context_hub` 决定是否注入模型。

### 与 prompt_hub

Prompt 渲染失败、prompt version、rendered_hash 等可以作为过程事件写入
memory_events，但不保存完整 Prompt。

### 与 checkpoint

checkpoint 是独立恢复能力。memory 不保存节点级恢复快照。

### 与 observability

memory_events 可用于审计和回放，但运行日志、指标、告警仍属于 observability。

## 10. 开发新事件的步骤

新增一个 MemoryEvent 时：

```text
1. 在 contracts.py 新增 payload model。
2. 将 payload 加入 MemoryEventPayload union。
3. 将事件名加入 MemoryEventType。
4. 如果它会影响多轮上下文，在 service.py 的 _hot_context_patch_for_event 中补更新逻辑。
5. 补充 record_event 和 flush 相关单元测试。
```

## 11. 当前风险与后续演进

当前风险：

1. Redis hot context 仍是 dict 形态，后续可进一步拆成 Hash/List。
2. 当前 flush 不依赖 MongoDB 事务，靠 upsert 保证幂等。
3. Scope key 如果包含 `:` 可能需要编码策略。
4. 大结果、完整 Prompt 和敏感权限信息仍需要严格避免直接写入。

后续演进：

1. 增加 Redis Hash/List 精细化 adapter。
2. 增加 MongoDB 索引初始化脚本。
3. 增加 session idle flush 调度。
4. 增加 memory summary 生成。
5. 增加 dead letter 可观测面板。
