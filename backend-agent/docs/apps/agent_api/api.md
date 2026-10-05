# Python Agent API 接口文档

> 当前实现范围（核对 `src/agent_backend/api/http/main.py`）：仅有 `GET /health`
> 和 `POST /internal/tasks`。任务接口校验请求并返回 `accepted`，不会在此处启动
> LangGraph。本文不定义尚未实现的流式执行或状态查询 API。

## 1. 基础信息

1. 服务名称：`agent-api`
2. 基础路径：`/`
3. 框架：`FastAPI`

## 2. 健康检查

### `GET /health`

当前响应：

```json
{
  "status": "ok",
  "service": "agent-api"
}
```

## 3. 创建内部任务

### `POST /internal/tasks`

请求体：

```json
{
  "task_id": "task-demo-001",
  "trace_id": "trace-demo-001",
  "tenant_id": "tenant-demo",
  "user_id": "user-demo",
  "session_id": "session-demo-001",
  "question": "Compare monthly revenue for the last 6 months",
  "dataset_ids": ["dataset-sales"],
  "access_context": {
    "tenant_id": "tenant-demo",
    "user_id": "user-demo",
    "allowed_dataset_ids": ["dataset-sales"],
    "readonly": true
  }
}
```

当前骨架响应：

```json
{
  "task_id": "task-demo-001",
  "trace_id": "trace-demo-001",
  "status": "accepted"
}
```

## 4. 错误约定

1. 请求体与 `AnalysisTaskRequest` 不匹配时由 FastAPI 返回参数校验错误。
2. 该入口当前没有任务查询或图执行，因此不定义任务不存在、运行失败等响应。

执行图仍由 [数据分析图构建入口](../../../src/agent_backend/orchestration/data_analysis/README.md)
描述；Java Job 和浏览器 SSE 主链尚未接通。
