# Java Audit 模块 API 文档

当前只有固定演示路由 `GET /api/audit/demo`；本模块尚未提供任务审计查询、事件时间线或风险记录查询 API。

## 1. 模块基础信息

1. 基础路径：`/api/audit`
2. 返回包装：`ApiResponse<T>`

## 2. 当前演示接口

### `GET /api/audit/demo`

返回固定 `taskId` 与 `reviewStatus` 演示对象，不读取或写入审计记录。
