# 分析工作台首页接口文档

> 本文记录目标接口与展示契约，不代表工作台已接通后端任务主链。当前
> `workspace-store.ts` 使用 `mock-data` 并通过定时器模拟事件；它没有请求任务 API 或订阅 SSE。
> Java 当前路由见 [Job API](../../../../backend-java/docs/modules/job/api.md) 和
> [Dataset API](../../../../backend-java/docs/modules/dataset/api.md)。

## 1. 文档目的

本文档定义首页工作台依赖的前后端接口契约，覆盖页面初始化、数据集查询、任务创建、任务详情查询、SSE 订阅和结果结构。

首页只与 `backend-java` 交互，不直接连接 `backend-agent`。

## 2. 接口范围

首页依赖的核心接口：

1. `GET /api/datasets`
2. `GET /api/datasets/{id}`
3. `POST /api/datasets/upload`
4. `POST /api/datasets/mysql/register`
5. `POST /api/tasks`
6. `GET /api/tasks/{id}`
7. `GET /api/tasks/{id}/stream`

## 3. 通用约定

### 3.1 认证

所有首页接口均要求用户已登录，由 Java 后端识别登录态。

由于当前前端请求使用 `Authorization: Bearer`，SSE 客户端建议使用基于 `fetch` 的实现，而不是原生 `EventSource`。

### 3.2 返回原则

建议所有普通 REST 接口统一返回：

```json
{
  "code": "OK",
  "message": "success",
  "data": {}
}
```

### 3.3 时间字段

所有时间字段建议使用 ISO 8601 字符串，前端只负责展示，不自行推导服务端事实时间。

## 4. 创建任务

### `POST /api/tasks`

请求体：

```json
{
  "question": "分析过去12个月企业营收趋势，并输出区域排名与渠道占比",
  "datasetIds": ["dataset-enterprise-sales", "dataset-finance-mysql"],
  "chartPreferences": ["line", "bar", "pie"]
}
```

响应体：

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "taskId": "task-20260829-0001",
    "traceId": "trace-20260829-0001",
    "status": "queued",
    "question": "分析过去12个月企业营收趋势，并输出区域排名与渠道占比",
    "datasetIds": ["dataset-enterprise-sales", "dataset-finance-mysql"],
    "startedAt": "2026-08-29T18:00:00+08:00"
  }
}
```

## 5. 任务详情

### `GET /api/tasks/{id}`

响应体：

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "taskId": "task-20260829-0001",
    "traceId": "trace-20260829-0001",
    "status": "succeeded",
    "question": "分析过去12个月企业营收趋势，并输出区域排名与渠道占比",
    "datasetIds": ["dataset-enterprise-sales", "dataset-finance-mysql"],
    "relatedDatasetNames": ["enterprise_sales_monthly", "finance_revenue_fact"],
    "startedAt": "2026-08-29T18:00:00+08:00",
    "finishedAt": "2026-08-29T18:00:14+08:00",
    "duration": "14s",
    "connectionStatus": "closed",
    "chartPreferences": ["line", "bar", "pie"],
    "sqlText": "SELECT ...",
    "sqlReasoning": "按月聚合营收并补充区域与渠道维度。",
    "finalConclusion": "营收整体呈上升趋势。",
    "warnings": [],
    "failureReason": null,
    "reviewMessage": null,
    "resultKind": "normal",
    "charts": []
  }
}
```

## 6. SSE 接口

### `GET /api/tasks/{id}/stream`

请求建议：

| Header | 说明 |
|---|---|
| `Accept: text/event-stream` | SSE 必需 |
| `Last-Event-ID` | 可选，用于断线续传 |
| `Authorization: Bearer <token>` | 建议通过 fetch 方式携带 |

服务端返回标准 SSE：

```text
event: message
id: evt-0001
data: {"taskId":"task-20260829-0001","traceId":"trace-20260829-0001","eventType":"task_started","level":"info","timestamp":"2026-08-29T18:00:01+08:00","payload":{"message":"任务已启动"}}
```

### `data` JSON 结构

```json
{
  "taskId": "task-20260829-0001",
  "traceId": "trace-20260829-0001",
  "eventType": "task_started",
  "level": "info",
  "timestamp": "2026-08-29T18:00:01+08:00",
  "payload": {
    "message": "任务已启动"
  }
}
```

## 7. 支持的事件类型

| 事件 | 说明 | 是否终态 |
|---|---|---|
| `task_started` | 任务已创建 | 否 |
| `context_built` | 权限上下文和 Schema 已准备 | 否 |
| `sql_delta` | SQL 增量片段 | 否 |
| `sql_ready` | SQL 最终版本与 reasoning 已生成 | 否 |
| `query_executed` | 查询执行完成 | 否 |
| `answer_delta` | 回答增量片段 | 否 |
| `chart_ready` | 图表配置已生成 | 否 |
| `human_review_required` | 命中高风险规则，需要人工确认说明 | 否 |
| `task_finished` | 任务成功完成 | 是 |
| `task_failed` | 任务失败或被阻断 | 是 |

## 8. 前端处理规则

1. `task_finished` 和 `task_failed` 视为终态事件。
2. 前端不可因为本地超时自行把任务改为失败。
3. 收到终态事件后，应主动刷新一次任务详情，确保结果完整。
4. 收到 `sql_delta` 时应追加到本地 SQL 草稿。
5. 收到 `answer_delta` 时应追加到本地回答草稿。
6. 收到 `sql_ready` 时应使用最终 SQL 覆盖 SQL 草稿。
