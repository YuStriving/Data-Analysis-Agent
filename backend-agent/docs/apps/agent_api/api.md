# Python Agent API 接口文档

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

## 4. 流式执行任务

### `POST /internal/tasks/{taskId}/run-stream`

请求体建议：

```json
{
  "taskId": "task-20260829-0001",
  "traceId": "trace-20260829-0001",
  "tenantId": "tenant-enterprise",
  "userId": "user-001",
  "question": "分析过去12个月企业营收趋势，并输出区域排名与渠道占比",
  "datasetIds": ["dataset-enterprise-sales", "dataset-finance-mysql"],
  "chartPreferences": ["line", "bar", "pie"],
  "datasets": [
    {
      "datasetId": "dataset-finance-mysql",
      "datasetType": "mysql",
      "schemaSummary": ["order_month", "product_line", "net_revenue", "gross_margin", "region"],
      "permissionScope": "finance.revenue.readonly"
    }
  ],
  "accessContext": {
    "allowedTables": ["finance.revenue_fact"],
    "maskedColumns": [],
    "rowLimit": 1000,
    "queryTimeoutSeconds": 30
  }
}
```

返回类型：

1. `Content-Type: application/x-ndjson`

返回示例：

```json
{"seq":1,"taskId":"task-20260829-0001","traceId":"trace-20260829-0001","eventType":"task_started","level":"info","timestamp":"2026-08-29T18:00:01+08:00","payload":{"message":"任务已启动"}}
{"seq":2,"taskId":"task-20260829-0001","traceId":"trace-20260829-0001","eventType":"sql_delta","level":"info","timestamp":"2026-08-29T18:00:04+08:00","payload":{"text":"SELECT order_month,"}}
{"seq":3,"taskId":"task-20260829-0001","traceId":"trace-20260829-0001","eventType":"answer_delta","level":"info","timestamp":"2026-08-29T18:00:10+08:00","payload":{"text":"过去12个月营收整体呈上升趋势。"}}
{"seq":4,"taskId":"task-20260829-0001","traceId":"trace-20260829-0001","eventType":"task_finished","level":"success","timestamp":"2026-08-29T18:00:14+08:00","payload":{"resultKind":"normal"}}
```

## 5. 查询任务状态

### `GET /internal/tasks/{taskId}`

建议响应：

```json
{
  "task_id": "task-demo-001",
  "trace_id": "trace-demo-001",
  "status": "running",
  "current_step": "generate_sql"
}
```

## 6. 错误约定

1. `400`：请求结构错误。
2. `404`：任务不存在。
3. `422`：Pydantic 参数校验失败。
4. `500`：内部执行链路异常。
