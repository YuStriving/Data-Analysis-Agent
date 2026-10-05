# Java Job 模块 API 文档

## 当前路由

核对 `JobController`，当前只实现：

### `GET /api/jobs/demo`

返回 `ApiResponse<AnalysisTaskEvent>`，包含固定的演示任务 ID、租户 ID、用户 ID、
追踪 ID 和问题文本。它不创建任务、不持久化数据，也不启动 Agent。

## 尚未实现

当前没有 `POST /api/tasks`、任务详情查询、任务事件回放、SSE 订阅或 Java 到 Python
的执行请求接口。相关目标需求见本目录 [需求文档](requirements.md)；后续接口只有在
相应 Spec 确认并实现后才加入本 API 文档。
