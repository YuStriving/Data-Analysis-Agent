# Python Memory 模块需求

## 1. 模块定位

`memory` 负责对话记忆、热上下文和结构化分析事件的基础读写，核心目标是保证热上下文可快速取用、长期历史可持久化、刷盘不丢数据且不产生重复写入。

节点级 checkpoint 和运行恢复属于 `agent_runtime.checkpoint` 的独立职责，不属于 memory 模块。memory 可以与 checkpoint 复用 scope、存储适配器和序列化规范，但不直接负责 checkpoint 的保存和恢复。

## 2. 数据边界

1. Redis 只存放待落库队列和热上下文，不作为唯一事实源。
2. MongoDB 是长期对话历史与结构化分析事件的唯一事实源。
3. 记忆按 `tenant_id + user_id + session_id` 组合隔离，任务维度写入 `task_id` 与 `trace_id`。
4. 面向 C 端 MVP 时 `tenant_id` 默认值为 `default`，但字段和索引仍然保留。
5. `session_id` 由 Java 后端生成或透传，Python Agent 只消费，不使用 `task_id` 兜底生成业务 session。
6. 默认 Redis key 前缀为 `backend-agent:memory`，MongoDB 集合为 `memory_turns` 与 `memory_events`。

## 3. 一致性规则

1. 新对话先写入 Redis 待落库队列，并同步更新 Redis 热上下文。
2. 刷盘时先向 MongoDB 幂等保存 `MemoryTurn` 与 `MemoryEvent`，写入成功后才裁剪 Redis 待落库队列。
3. MongoDB 使用 `turn_id` 和 `event_id` 做 `upsert`，保证重复执行不会生成重复记录。
4. MongoDB 写入失败时保留 Redis 待落库队列，由调用方异步重试并触发告警日志。
5. Redis 热上下文 TTL 为 2 小时，session 空闲 1 小时后触发刷写和摘要整理。
6. 刷盘只能删除本批已读取的 pending item，不能直接删除整个 pending key。

## 4. 核心职责

1. 入队对话和结构化分析事件，并保存热上下文。
2. 读取指定 scope 的热上下文。
3. 将待落库对话安全刷入 MongoDB。
4. 将待落库结构化分析事件安全刷入 MongoDB。
5. 维护最近 6 轮对话、最近 SQL、结果摘要、图表摘要和修复经验。
6. 提供 repository 协议，便于本地 fake 与真实 Redis/Mongo 适配器替换。

## 5. MVP 验收标准

1. Mongo 写入成功后 Redis 队列只裁剪本批已读取 item。
2. Mongo 写入失败时 Redis 队列不丢失。
3. 重复刷盘不会新增重复 turn 或 event。
4. 坏 JSON 与 payload 校验失败的 pending item 进入 dead letter queue。
5. scope key 必须包含租户、用户和会话，不允许跨用户、跨 session 混写。
6. `MemoryEvent.payload` 使用强类型结构，`payload.type` 必须与 `event_type` 一致。
