# Python Agent API 模块需求

## 1. 模块定位

`api/http` 是 Python Agent 对内 HTTP 服务入口，对应当前 `backend-agent/src/agent_backend/api/http/main.py`。

在初版方案中，它负责接收 Java 下发的执行请求，并以流的形式持续返回执行事件。

## 2. 当前代码现状

当前已实现：

1. `GET /health`
2. `POST /internal/tasks`

当前仍缺少真实执行入口、流式输出、事件模型和状态查询能力。

## 3. 核心职责

1. 接收 Java 发起的内部任务执行请求。
2. 校验任务请求结构和最小上下文。
3. 将任务交给 LangGraph 执行。
4. 通过流持续返回结构化事件。
5. 提供健康检查。
6. 提供内部任务状态查询。

## 4. MVP 功能需求

1. 支持接收扩展后的 `AnalysisTaskRequest`。
2. 支持 `POST /internal/tasks/{taskId}/run-stream`。
3. 支持以 `application/x-ndjson` 连续输出事件。
4. 支持按 `task_id` 查询当前状态。
5. 支持统一错误返回和参数校验。
6. 支持为日志和事件透传 `trace_id`。

## 5. 输入模型要求

在当前 `shared_models.task.AnalysisTaskRequest` 基础上，初版建议至少扩展：

1. `task_id`
2. `trace_id`
3. `tenant_id`
4. `user_id`
5. `question`
6. `dataset_ids`
7. `chart_preferences`
8. `datasets`
9. `access_context`

## 6. 边界约束

1. 不负责最终 UI 展示。
2. 不负责业务权限判定。
3. 不直接对前端开放。

## 7. 验收标准

1. Java 能成功调用内部任务流式执行接口。
2. Java 能消费到增量 SQL 和增量回答事件。
3. 参数缺失会被明确校验拒绝。
4. 内部状态查询能返回任务是否已进入执行链路。
