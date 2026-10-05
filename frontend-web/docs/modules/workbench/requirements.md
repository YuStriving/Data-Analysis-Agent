# 分析工作台首页需求文档

> 本文的工作台任务流是目标需求。当前工作台仍由本地 mock 数据和定时器驱动，
> 未连接任务创建、任务详情或 Java SSE 接口；后端现状见 Java 模块 API 文档。

## 1. 文档目的

本文档定义 `frontend-web` 工作台模块在“自然语言对话 + AI 分析”初版中的职责、边界和实现要求。

工作台只对接 Java，不直连 Python。

## 2. 初版实现定位

工作台不是通用聊天页，而是受控的数据分析工作台。

它的目标是承接这条主链：

1. 选择已授权数据集。
2. 输入自然语言问题。
3. 创建分析任务。
4. 订阅 Java SSE。
5. 增量展示 SQL、回答、图表和状态。

## 3. 前端技术栈建议

保留：

1. `Vue 3`
2. `TypeScript`
3. `Vite`
4. `Tailwind CSS`
5. `ECharts`

新增：

1. `@microsoft/fetch-event-source`

使用理由：

1. 当前鉴权依赖 `Authorization: Bearer`。
2. 原生 `EventSource` 不适合携带自定义认证头。
3. `fetch-event-source` 可以兼容 Bearer Token、断线重连和统一错误处理。

## 4. 模块职责

1. 读取工作台 bootstrap 数据。
2. 渲染最近任务、数据集和当前任务详情。
3. 通过 `POST /api/tasks` 创建任务。
4. 通过 `GET /api/tasks/{id}/stream` 订阅流式事件。
5. 维护本地增量状态，例如 SQL 预览缓冲区和回答缓冲区。
6. 在终态后补拉一次 `GET /api/tasks/{id}`，确保详情完整。

## 5. 边界约束

1. 不直接连接 `backend-agent`。
2. 不自行推导权限结果。
3. 不自行判定任务终态真值。
4. 不直接访问 Kafka、Redis、MySQL。
5. 所有 SQL 和结果都以 Java 返回为准。

## 6. 关键页面能力

### 6.1 数据集选择

首页必须支持：

1. 查看当前用户已授权的数据集。
2. 支持多选数据集。
3. 展示 `datasetType`、`schemaSummary`、`permissionScope` 等摘要信息。

### 6.2 任务提交

首页必须支持：

1. 输入自然语言分析问题。
2. 选择图表偏好 `auto / line / bar / pie`。
3. 未选择数据集时禁止提交。
4. 问题为空时禁止提交。
5. 提交后立即生成本地占位任务并进入 `queued` 或 `running` 展示态。

### 6.3 流式过程展示

首页必须支持增量消费以下事件：

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

展示要求：

1. 过程区展示阶段事件时间线。
2. SQL 区支持边生成边展示。
3. 回答区支持边生成边展示。
4. 图表区在收到 `chart_ready` 后刷新。
5. 收到终态事件后主动刷新详情。

### 6.4 异常态与审核态

必须显式区分：

1. `empty`
2. `blocked`
3. `review`
4. `failed`

## 7. 状态管理建议

建议把现有 `workspace-store` 从 mock 切换为以下结构：

1. `taskSummaries`
2. `taskDetailsById`
3. `taskEventsById`
4. `streamConnectionByTaskId`
5. `draftQuestion`
6. `draftDatasetIds`
7. `draftChartPreferences`
8. `sqlDraftByTaskId`
9. `answerDraftByTaskId`

## 8. 验收标准

1. 用户可以从工作台提交真实任务。
2. 前端可以实时看到 Java 转发的 SSE 事件。
3. SQL 和回答可以增量显示，而不是只在终态显示。
4. 图表、最终结论、告警和失败原因可以在终态完整恢复。
5. 页面在刷新或切换任务后仍能恢复既有任务详情。
