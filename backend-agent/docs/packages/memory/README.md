# Memory README

## 1. 这个模块解决什么问题

`memory` 负责保存一个 `session` 内可以复用的对话和分析事实。

用户连续追问时，Agent 需要记住一些东西：

```text
刚才用户问了什么
刚才用了哪个数据集
上一条 SQL 是什么
上一轮结果摘要是什么
SQL 为什么失败过
最终给用户的答案是什么
```

这些信息如果不保存，下一轮用户说“那按地区拆一下”时，Agent 就不知道
“那”指的是什么。

一句话理解：

```text
memory 是 Agent 的 session 记忆层。
```

## 2. 它不做什么

`memory` 不负责：

1. 不负责决定哪些记忆能注入 Prompt，这属于 `context_hub`。
2. 不负责渲染 Prompt，这属于 `prompt_hub`。
3. 不负责执行 SQL。
4. 不负责节点级恢复，节点级恢复属于 `checkpoint`。
5. 不负责保存完整大查询结果。

memory 可以保存“最近发生了什么”，但不能直接决定“模型应该看到什么”。

## 3. 三层结构

Memory 模块分三层：

```text
Scope
Hot Memory
Durable Memory
```

### 3.1 Scope

Scope 定义一条记忆属于谁。

当前主键由三部分组成：

```text
tenant_id + user_id + session_id
```

MVP 面向 C 端，`tenant_id` 默认可以是 `default`，但字段保留。

`session_id` 很关键。它代表一个对话窗口，不能用 `task_id` 替代。

### 3.2 Hot Memory

Hot Memory 是 Redis 中的活跃记忆。

它保存最近最可能被下一轮用到的信息：

```text
selected_dataset_id
recent_turns
last_question
last_sql
last_result_summary
last_chart_summary
repair_lessons
pending queue
```

Hot Memory 不是永久事实源，主要服务当前活跃 session。

### 3.3 Durable Memory

Durable Memory 是 MongoDB 中的长期记忆。

它保存两类集合：

```text
memory_turns
memory_events
```

`memory_turns` 用于保存用户和助手最终可见的对话。

`memory_events` 用于保存 Agent 内部分析过程，比如 SQL 生成、SQL 校验、
SQL 修复、查询执行、图表生成。

## 4. 为什么要同时用 Redis 和 MongoDB

Redis 适合保存热数据：

```text
读写快
适合最近上下文
适合 pending 队列
适合锁和序号
```

MongoDB 适合保存长期数据：

```text
可长期查询
适合审计和回放
适合保存结构化事件
```

所以当前设计是：

```text
先写 Redis pending
再异步或顺手 flush 到 MongoDB
```

这样即使 MongoDB 短暂失败，Redis pending 里仍保留数据，后续可以重试。

## 5. 基本使用方式

记录一条用户或助手最终可见消息：

```python
item = memory_service.record_turn(turn)
```

记录一条 Agent 过程事件：

```python
item = memory_service.record_event(event)
```

刷写 pending 到 MongoDB：

```python
result = memory_service.flush_pending(scope)
```

读取 hot context：

```python
hot_context = memory_service.load_hot_context(scope_key)
```

## 6. Pending 队列为什么重要

memory 的写入原则是：

```text
允许重复，不允许丢失。
```

如果直接写 MongoDB，失败时可能丢数据。

所以当前先把 turn/event 写入 Redis pending 队列。flush 成功后，再用
`LTRIM` 删除已经成功处理的部分。

MongoDB 侧使用 `turn_id` 和 `event_id` 做 upsert，所以重复 flush 不会生成
重复数据。

## 7. 什么信息不能直接保存

不建议直接保存：

```text
完整查询结果
完整 Prompt
敏感连接信息
未脱敏权限细节
跨 session 文件内容
```

大结果应该保存：

```text
摘要
有限 preview
result_ref
chart_ref
```

## 8. 和 context_hub 的关系

memory 是原材料来源之一。

例如 memory 中有：

```text
last_sql
last_result_summary
recent_turns
repair_lessons
```

但这些信息是否能进入模型上下文，必须由 `context_hub` 的 `ContextPolicy`
决定。

## 9. 常见问题

### 为什么 task_id 不进入 scope？

因为一个 session 会有多个 task。用户多轮追问时，多个 task 应该共享同一个
session 记忆。

### 为什么 checkpoint 不属于 memory？

memory 记录对话和分析事实；checkpoint 记录运行恢复状态。二者都和状态有关，
但职责不同。

### 为什么要有 memory_events？

因为最终回答不够排查问题。我们还需要知道过程里生成过什么 SQL、是否校验
通过、执行结果有多少行、是否触发修复。

## 10. 相关文件

代码：

```text
src/agent_backend/capabilities/agent_runtime/memory/contracts.py
src/agent_backend/capabilities/agent_runtime/memory/protocols.py
src/agent_backend/capabilities/agent_runtime/memory/redis_store.py
src/agent_backend/capabilities/agent_runtime/memory/mongo_store.py
src/agent_backend/capabilities/agent_runtime/memory/service.py
```

测试：

```text
tests/unit/test_memory_service.py
```

设计文档：

```text
docs/packages/memory/design.md
docs/packages/memory/architecture.md
```
