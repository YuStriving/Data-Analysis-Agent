# Python Memory 模块开发设计

## 1. 设计目标

`memory` 是 `agent_runtime` 的状态沉淀能力，负责保存一个 `session`
内可复用的对话和分析事实。它不负责具体业务分析，也不负责 graph
节点恢复。

本模块需要支撑：

1. 同一 `session` 内多轮追问连续。
2. 最近对话、最近 SQL、结果摘要和图表摘要可被下一轮上下文复用。
3. SQL 失败和修复经验可沉淀，供后续修复节点使用。
4. 对话结果和 Agent 分析过程可长期落库、复盘和审计。
5. Redis 刷写 MongoDB 时允许重复执行，但不能丢数据。

`checkpoint` 是 `agent_runtime` 的独立恢复能力，不属于 memory 的业务职责。
它可以复用 scope、Redis/Mongo 适配器和序列化规范，但应使用独立模块和
独立集合承载。

## 2. 分层结构

Memory 模块拆成三层：

```text
Scope
  定义 memory 归属和隔离边界

Hot Memory
  Redis 中的活跃 session 热上下文、最近对话和待落库队列

Durable Memory
  MongoDB 中的长期对话结果和强类型分析事件
```

## 3. Scope 层

Scope 层回答的问题是：

```text
这条 memory 属于谁、属于哪个对话窗口、是否允许被当前任务读取？
```

MVP 面向 C 端，`tenant_id` 不作为主要业务维度，但字段仍然保留，默认值为
`default`，便于后续多租户或团队空间演进。

推荐结构：

```python
class MemoryScope(BaseModel):
    tenant_id: str = "default"
    user_id: str
    session_id: str

    def to_key(self) -> str:
        return build_scope_key(self.tenant_id, self.user_id, self.session_id)
```

业务规则：

1. `tenant_id` 允许默认 `default`，但最终写入和查询都必须携带。
2. `user_id` 必须非空。
3. `session_id` 必须非空。
4. `session_id` 由 Java 后端生成或透传，Python Agent 只消费。
5. Python 不使用 `task_id` 兜底生成业务 session。
6. `task_id` 和 `trace_id` 只用于追踪，不进入 scope 主键。
7. `dataset_id` 不进入 scope 主键，数据集权限由 context 和 guardrails 负责。

推荐 key 格式：

```text
v1:{tenant_id}:{user_id}:{session_id}
```

如果 Java 侧不能保证 ID 不含 `:`，则需要对三段 ID 做 URL encoding 或改用
结构化 key 编码。

## 4. Hot Memory 层

Hot Memory 存储一个活跃 session 最近最可能被下一轮任务使用的上下文。它
不是长期事实源，也不保存完整大查询结果。

Redis key 建议：

```text
backend-agent:memory:hot:{scope_key}
backend-agent:memory:recent_turns:{scope_key}
backend-agent:memory:pending:{scope_key}
backend-agent:memory:seq:{scope_key}
backend-agent:memory:flush_lock:{scope_key}
backend-agent:memory:dead:{scope_key}
```

建议将 hot context 拆成 Redis Hash，将最近对话和待落库项拆成 Redis List，
避免多个 task 并发时整包 JSON 覆盖。

推荐结构：

```python
class RecentTurn(BaseModel):
    task_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class HotContext(BaseModel):
    scope: MemoryScope
    selected_dataset_id: str | None = None
    recent_dataset_ids: list[str] = Field(default_factory=list)
    last_task_id: str | None = None
    last_question: str | None = None
    last_sql: str | None = None
    last_result_summary: str | None = None
    last_chart_summary: ChartSummary | None = None
    repair_lessons: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
    updated_at: datetime
```

参数约定：

1. `recent_turns` 保留最近 6 轮。
2. Redis hot context TTL 为 2 小时。
3. session 空闲 1 小时后触发刷写和摘要整理。
4. task 结束后主动尝试 flush pending。
5. 下一次 task 进入时可顺手补偿 flush。

上下文污染控制策略：

1. 只读取当前 `MemoryScope`，不跨 session 自动复用。
2. Redis 中存在的字段不等于一定注入 prompt，必须经过 `ContextPolicy` 裁剪。
3. 本轮显式选择新数据集时，弱化上一轮 SQL 和结果摘要。
4. 本轮问题包含“上一个、刚才、继续、那、这个、它”等指代词时，加强最近
   问题、SQL 和结果摘要。
5. 如果 dataset 不同，不注入上一轮 SQL/result，只保留必要对话摘要。
6. 优先注入结构化事实，少注入大段自然语言历史。

## 5. Durable Memory 层

Durable Memory 只保存两类长期数据：

```text
memory_turns
memory_events
```

`memory_turns` 保存用户和助手最终可见的对话结果。它用于历史记录、会话
回放和对话摘要生成。

```python
class MemoryTurn(BaseModel):
    turn_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    task_id: str
    trace_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
```

`memory_events` 保存 Agent 分析过程中的强类型结构化事件。它用于复盘、
审计、上下文复用、SQL 修复和评测回放。

```python
class MemoryEvent(BaseModel):
    event_id: str
    tenant_id: str = "default"
    user_id: str
    session_id: str
    task_id: str
    trace_id: str
    event_type: MemoryEventType
    event_seq: int
    payload: MemoryEventPayload
    created_at: datetime
```

`event_seq` 表示同一个 task 内事件顺序。session 内全局刷写顺序由 Redis
`pending_seq` 表示，建议通过 Redis `INCR` 生成。

## 6. 强类型 Payload

为了规范化 Agent 输出结果，`MemoryEvent.payload` 使用强类型 payload，而
不是 `dict[str, Any]`。每个 payload 必须包含 `type` 字段，并与外层
`event_type` 保持一致。

```python
MemoryEventPayload = Annotated[
    QuestionReceivedPayload
    | DatasetResolvedPayload
    | SchemaLoadedPayload
    | SqlGeneratedPayload
    | SqlValidatedPayload
    | SqlRepairedPayload
    | QueryExecutedPayload
    | ResultSummarizedPayload
    | ChartBuiltPayload
    | AnswerGeneratedPayload
    | TaskFailedPayload,
    Field(discriminator="type"),
]
```

事件类型：

```python
MemoryEventType = Literal[
    "question_received",
    "dataset_resolved",
    "schema_loaded",
    "sql_generated",
    "sql_validated",
    "sql_repaired",
    "query_executed",
    "result_summarized",
    "chart_built",
    "answer_generated",
    "task_failed",
]
```

### 6.1 question_received

```python
class QuestionReceivedPayload(BaseModel):
    type: Literal["question_received"] = "question_received"
    question: str
    dataset_ids: list[str] = Field(default_factory=list)
    selected_dataset_id: str | None = None
    user_intent_hint: str | None = None
```

### 6.2 dataset_resolved

```python
class DatasetResolvedPayload(BaseModel):
    type: Literal["dataset_resolved"] = "dataset_resolved"
    available_dataset_ids: list[str]
    selected_dataset_id: str | None = None
    selection_source: Literal[
        "explicit_user_selection",
        "session_recent_dataset",
        "single_available_dataset",
        "unresolved",
    ]
    selection_reason: str
```

### 6.3 schema_loaded

```python
class SchemaLoadedPayload(BaseModel):
    type: Literal["schema_loaded"] = "schema_loaded"
    dataset_id: str
    datasource_type: Literal["mysql", "csv", "xls", "xlsx"]
    schema_summary: str
    table_count: int | None = None
    field_count: int | None = None
    truncated: bool = False
    schema_ref: str | None = None
```

`schema_loaded` 建议保留，因为 SQL 生成、SQL 修复和问题复盘都需要知道
模型当时看到了什么 schema。大 schema 不直接完整写入事件，只存摘要和
引用。

### 6.4 sql_generated

```python
class SqlGeneratedPayload(BaseModel):
    type: Literal["sql_generated"] = "sql_generated"
    sql: str
    sql_dialect: Literal["mysql", "duckdb"] = "mysql"
    dataset_ids: list[str]
    selected_dataset_id: str
    prompt_version: str
    model: str
```

### 6.5 sql_validated

```python
class SqlValidatedPayload(BaseModel):
    type: Literal["sql_validated"] = "sql_validated"
    sql: str
    passed: bool
    readonly: bool
    risk_reasons: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
```

### 6.6 sql_repaired

```python
class SqlRepairedPayload(BaseModel):
    type: Literal["sql_repaired"] = "sql_repaired"
    failed_sql: str
    error_message: str
    failure_stage: Literal["validate_sql", "execute_sql"]
    repaired_sql: str
    retry_count: int
    max_retry_count: int
    lesson: str | None = None
```

### 6.7 query_executed

```python
class QueryExecutedPayload(BaseModel):
    type: Literal["query_executed"] = "query_executed"
    sql: str
    status: Literal["success", "failed", "timeout"]
    row_count: int | None = None
    elapsed_ms: int
    truncated: bool = False
    max_rows: int
    result_ref: str | None = None
    error_message: str | None = None
```

### 6.8 result_summarized

```python
class KeyMetric(BaseModel):
    name: str
    value: str | int | float | bool | None
    unit: str | None = None


class ResultSummarizedPayload(BaseModel):
    type: Literal["result_summarized"] = "result_summarized"
    summary: str
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    row_count: int | None = None
    truncated: bool = False
    result_ref: str | None = None
```

### 6.9 chart_built

```python
class ChartBuiltPayload(BaseModel):
    type: Literal["chart_built"] = "chart_built"
    chart_type: Literal["bar", "line", "pie", "table"]
    title: str
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None
    chart_ref: str | None = None
```

`chart_built` 建议保留，因为图表是 Agent 输出的一部分，后续图表追问、
历史回放和图表质量评估都需要结构化记录。事件中不保存完整图表数据，只保存
摘要字段和引用。

### 6.10 answer_generated

```python
class AnswerGeneratedPayload(BaseModel):
    type: Literal["answer_generated"] = "answer_generated"
    answer: str
    has_table_preview: bool = False
    has_chart: bool = False
    result_ref: str | None = None
    chart_ref: str | None = None
```

`answer_generated` 和 assistant `MemoryTurn` 会有内容重复。二者职责不同：
`MemoryTurn` 面向历史对话展示，`answer_generated` 面向结构化过程复盘和
引用关联。

### 6.11 task_failed

```python
class TaskFailedPayload(BaseModel):
    type: Literal["task_failed"] = "task_failed"
    failure_stage: str
    error_message: str
    retry_count: int = 0
    final: bool = True
```

## 7. Pending 队列 Envelope

Redis pending queue 同时承载 turn 和 event，使用统一 envelope：

```python
class PendingMemoryItem(BaseModel):
    item_id: str
    item_type: Literal["turn", "event"]
    scope: MemoryScope
    scope_key: str
    pending_seq: int
    payload: MemoryTurn | MemoryEvent
    created_at: datetime
```

写入 pending 前通过 Redis `INCR backend-agent:memory:seq:{scope_key}` 获取
`pending_seq`，再 `RPUSH` 到 pending list。

## 8. 刷写落库策略

刷写原则：

```text
允许重复，不允许丢失。
允许短暂延迟，不允许误删 Redis pending。
```

MVP 不使用 Kafka，不依赖 MongoDB 跨集合事务，不实现 Redisson 风格看门狗。
采用：

```text
Redis List pending queue
Redis SET NX EX 轻量锁
MongoDB upsert 幂等写入
成功后 LTRIM 已读取片段
失败则保留 Redis pending 等待重试
```

默认参数：

```text
flush_lock_ttl_seconds = 60
flush_batch_size = 500
hot_context_ttl_seconds = 7200
idle_flush_after_seconds = 3600
recent_turn_limit = 6
dead_letter_ttl_seconds = None
```

`flush_pending(scope)` 流程：

```text
1. 根据 scope 构造 scope_key。
2. 尝试 SET NX EX 获取 flush lock。
3. 获取锁失败则直接返回 locked/skipped。
4. 读取 pending list 当前长度 pending_len。
5. 若 pending_len 为 0，释放锁并返回 empty。
6. 读取 0 到 min(pending_len, batch_size) - 1 的 item。
7. 反序列化并校验 PendingMemoryItem。
8. 坏 JSON 或校验失败的 item 移入 dead letter queue。
9. 合法 item 按 pending_seq 排序。
10. 按 item_type 分为 turns 和 events。
11. MongoDB 分别按 turn_id/event_id upsert。
12. 两类写入都成功后，LTRIM 删除本批已读取片段。
13. 释放 lock。
```

注意第 12 步只能删除本批读取到的片段，不能 `DEL pending key`，否则 flush
期间新写入的 item 可能被误删。

## 9. 异常处理策略

| 异常场景 | 处理策略 |
| --- | --- |
| 获取锁失败 | 不等待，返回 locked，由其他 flush 或下次 flush 兜底 |
| Redis 读取失败 | 不写 Mongo，不清 pending，记录告警 |
| JSON 损坏 | 移入 dead letter queue，继续处理合法 item |
| payload 校验失败 | 移入 dead letter queue，记录 validation error |
| Mongo 写入失败 | 不执行 LTRIM，保留 pending，下次重试 |
| Mongo 部分写入成功 | 不执行 LTRIM，下次整批重试，依赖 upsert 去重 |
| LTRIM 失败 | 记录告警，下次重复刷写，依赖 upsert 去重 |
| 锁过期 | 允许重复 flush，依赖 upsert 和 batch 控制降低影响 |
| flush 期间新增 item | LTRIM 只删除本批长度，新 item 保留在队列 |

MongoDB 写入方式：

```python
turns.update_one(
    {"turn_id": turn.turn_id},
    {"$setOnInsert": turn.model_dump(mode="json")},
    upsert=True,
)

events.update_one(
    {"event_id": event.event_id},
    {"$setOnInsert": event.model_dump(mode="json")},
    upsert=True,
)
```

## 10. 索引设计

`memory_turns`：

```text
unique(turn_id)
index(tenant_id, user_id, session_id, created_at)
index(tenant_id, user_id, session_id, task_id, created_at)
```

`memory_events`：

```text
unique(event_id)
index(tenant_id, user_id, session_id, created_at)
index(tenant_id, user_id, session_id, event_type, created_at)
index(tenant_id, user_id, session_id, task_id, event_seq)
```

虽然 MVP 中 `tenant_id` 默认为 `default`，索引中仍保留该字段，避免后续
多租户化时重建模型。

## 11. 编码落点

建议按最小改动落地：

1. `capabilities/agent_runtime/memory/contracts.py`
   - 新增 `MemoryScope`
   - 扩展 `MemoryTurn`
   - 新增 `MemoryEvent`
   - 新增强类型 payload models
   - 改造 `PendingMemoryItem`

2. `foundation/contracts/task.py`
   - `AnalysisTaskRequest` 增加 `session_id`
   - `tenant_id` 可保持必填，也可默认 `default`

3. `capabilities/agent_runtime/memory/protocols.py`
   - `build_scope_key` 统一使用 v1 key 格式
   - `PendingMemoryStore` 增加 seq、lock、trim、dead letter 能力
   - `DurableMemoryStore` 增加 `save_events`

4. `capabilities/agent_runtime/memory/redis_store.py`
   - pending list 使用 `RPUSH/LRANGE/LTRIM`
   - hot context 使用 hash 或兼容 JSON 后逐步迁移
   - recent turns 使用 list 并限制 6 轮
   - flush lock 使用 `SET NX EX`

5. `capabilities/agent_runtime/memory/mongo_store.py`
   - `save_turns` 使用 `turn_id` upsert
   - `save_events` 使用 `event_id` upsert
   - checkpoint 写入迁出 memory 语义，后续归入 checkpoint 模块

6. `capabilities/agent_runtime/memory/service.py`
   - 新增 `record_turn`
   - 新增 `record_event`
   - 新增 `update_hot_context`
   - 改造 `flush_pending`
   - 返回结构化 `FlushResult`

7. `foundation/contracts/*` 与 `foundation/datasource/*`
   - 只保留兼容转发或跨模块通用契约
   - 不再承载 memory 专属实现

## 12. MVP 验收标准

1. 相同 `user_id + session_id` 的多 task 写入相同 scope。
2. 不同 session 的 memory 不互相读取。
3. `recent_turns` 最多保留 6 轮。
4. hot context TTL 为 2 小时。
5. pending item 使用 Redis `INCR` 生成递增 `pending_seq`。
6. 同 scope flush 同一时间只有一个执行者。
7. Mongo 写入成功后只 trim 本批已读取 item。
8. Mongo 写入失败时 Redis pending 不丢失。
9. 重复 flush 不产生重复 turn/event。
10. 坏 JSON 和 payload 校验失败进入 dead letter queue。
11. `memory_events.payload.type` 与 `event_type` 不一致时校验失败。
12. memory 模块不再保存 checkpoint，checkpoint 由独立恢复模块负责。
