# Java Gateway 模块 API 文档

当前仅实现 `GET /api/gateway/health`。工作台初始化接口及任务接口为未实现的旧目标，
不能作为当前服务契约。

## 1. 模块基础信息

1. 基础路径：`/api/gateway`
2. 返回包装：`ApiResponse<T>`

## 2. 健康检查

### `GET /api/gateway/health`

当前骨架响应：

```json
{
  "success": true,
  "message": "ok",
  "data": "backend-java-monolith"
}
```

## 3. 当前路由

`GET /api/gateway/health` 返回 `ApiResponse<String>`，数据为 `backend-java-monolith`。
当前没有 bootstrap 或任务路由；任务能力状态见 [Job API](../job/api.md)。
