# Python Memory 模块需求

## 1. 模块定位

`memory` 负责对话记忆和运行快照的基础读写，核心目标是保证热上下文可快速取用、长期历史可持久化、刷盘不丢数据且不产生重复写入。

## 2. 数据边界

1. Redis 只存放待落库队列和热上下文，不作为唯一事实源。
2. MongoDB 是长期历史与快照的唯一事实源。
3. 记忆按 `tenant_id + user_id + session_id` 组合隔离，任务维度写入 `task_id` 与 `trace_id`。
4. 默认 Redis key 前缀为 `backend-agent:memory`，MongoDB 集合为 `memory_turns` 与 `memory_checkpoints`。

## 3. 一致性规则

1. 新对话先写入 Redis 待落库队列，并同步更新 Redis 热上下文。
2. 刷盘时先向 MongoDB 幂等保存 `MemoryTurn`，写入成功后才删除 Redis 待落库队列。
3. MongoDB 使用 `turn_id` 和 `snapshot_id` 做 `upsert`，保证重复执行不会生成重复记录。
4. MongoDB 写入失败时保留 Redis 待落库队列，由调用方异步重试并触发告警日志。
5. Redis 热上下文使用短 TTL，MongoDB 长期记录不做短时间清理。

## 4. 核心职责

1. 入队对话并保存热上下文。
2. 读取指定 scope 的热上下文。
3. 将待落库对话安全刷入 MongoDB。
4. 保存节点级 `NodeCheckpointSnapshot`。
5. 提供 repository 协议，便于本地 fake 与真实 Redis/Mongo 适配器替换。

## 5. MVP 验收标准

1. Mongo 写入成功后 Redis 队列被清空。
2. Mongo 写入失败时 Redis 队列不丢失。
3. 重复刷盘不会新增重复 turn。
4. 快照按 `snapshot_id` 幂等保存。
5. scope key 必须包含租户、用户和会话，不允许跨用户混写。
