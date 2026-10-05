# Java Job 模块需求

## 1. 模块定位

`job` 模块负责分析任务生命周期管理，是工作台任务中心。

以下任务创建和 SSE 转发均为目标需求，尚未实现。

## 2. 当前代码现状

当前仅存在 `GET /api/jobs/demo` 固定演示接口。真实任务创建、持久化、详情查询和事件流尚未实现。

## 3. 初版架构角色

初版 `job` 模块不是“纯 Kafka 调度器”，而是“控制面 + 流转发器”。

核心职责：

1. 校验当前用户是否可访问所选数据集。
2. 生成 `taskId`、`traceId`。
3. 创建任务记录与初始状态。
4. 向 Python Agent 发起内部执行请求。
5. 持续消费 Python 的 NDJSON 事件流。
6. 更新任务状态和事件表。
7. 向前端 SSE 订阅方推送实时事件。
8. 提供任务详情查询和历史恢复。

## 4. 初版通信方式

### 4.1 外部

1. `POST /api/tasks`
2. `GET /api/tasks/{id}`
3. `GET /api/tasks/{id}/stream`

### 4.2 内部

1. Java -> Python：`HTTP POST`
2. Python -> Java：`NDJSON` 流

## 5. 初版功能需求

1. 支持按问题、数据集和图表偏好创建任务。
2. 支持任务状态流转。
3. 支持持久化阶段事件。
4. 支持 SQL 和回答的增量更新。
5. 支持保存最终 SQL、图表结果、结论摘要和失败原因。
6. 支持为 SSE 新连接回放历史事件。

## 6. 状态流转

1. `queued`
2. `running`
3. `needs_review`
4. `succeeded`
5. `failed`

## 7. 事件要求

初版至少支持：

1. `task_started`
2. `context_built`
3. `sql_delta`
4. `sql_ready`
5. `query_executed`
6. `answer_delta`
7. `chart_ready`
8. `human_review_required`
9. `task_finished`
10. `task_failed`

## 8. 数据持久化建议

至少拆分：

1. `analysis_task`
2. `analysis_task_event`
3. `analysis_task_result`

## 9. 第二阶段演进

当初版稳定后，再将“Java -> Python 直接 HTTP 执行”演进为：

1. Java -> Kafka
2. Worker 消费 Kafka
3. Worker -> Java callback 或结果主题

初版不要求先实现这一步。

## 10. 验收标准

1. 成功创建任务后 MySQL 中有任务记录。
2. Java 能持续接收 Python 增量事件流。
3. 前端能通过 Java SSE 看到增量 SQL 和增量回答。
4. 终态后任务详情可完整恢复。
