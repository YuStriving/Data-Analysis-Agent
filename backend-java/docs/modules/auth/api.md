# Java Auth 模块 API 文档

当前认证接口由 `AuthController` 实现。refresh token 仅写入服务端配置的 Cookie；
响应 JSON 的 `refreshToken` 字段为 `null`，前端只保存 access token。Cookie 的
HttpOnly、Secure、SameSite、Path 和有效期由服务端配置控制。

## 1. 基础信息

1. 基础路径：`/api/auth`
2. 返回包装：`ApiResponse<T>`
3. 当前采用双令牌方案：
   - `accessToken` 通过 JSON 返回给前端，前端后续请求使用 `Authorization` 请求头
   - `refreshToken` 通过 HttpOnly Cookie 写入，不由前端读取或保存；服务端会话状态负责校验
4. Token 算法：`RS256`

## 2. 注册

### `POST /api/auth/register`

请求体：

```json
{
  "username": "analyst01",
  "password": "Aa123456!",
  "nickname": "分析师一号",
  "email": "analyst01@example.com",
  "phone": "13800000001"
}
```

成功响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "accessToken": "jwt-access-token",
    "refreshToken": null,
    "accessTokenExpiresIn": 900,
    "refreshTokenExpiresIn": 604800,
    "userId": "1",
    "username": "analyst01",
    "nickname": "分析师一号",
    "avatarUrl": null,
    "status": "ACTIVE",
    "tenantId": "tenant-demo",
    "roles": ["ANALYST"]
  }
}
```

## 3. 登录

### `POST /api/auth/login`

请求体：

```json
{
  "username": "analyst01",
  "password": "Aa123456!"
}
```

成功响应与注册一致。

## 4. 刷新令牌

### `POST /api/auth/refresh`

浏览器携带登录/注册时设置的 refresh token Cookie（前端请求使用 `credentials: include`）；
请求体不包含 refresh token。成功时返回新的 access token，并轮换 Cookie。

刷新策略说明：

1. 后端校验 refresh token 的签名、过期时间与 `token_type=refresh`
2. 后端校验 Redis 中保存的 refresh token 是否与请求值一致
3. 校验通过后签发新的一对 token，并覆盖 Redis 中该用户原有的 refresh token

## 5. 登出

### `POST /api/auth/logout`

请求头：

1. `Authorization: Bearer <accessToken>`

请求使用 refresh token Cookie；不在 JSON body 中传递 refresh token。

成功响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "loggedOut": true
  }
}
```

登出策略说明：

1. 后端撤销该用户当前 refresh token
2. 后端将当前 access token 放入黑名单，直到该 token 自然过期
3. 前端清理本地保存的 access token 与 refresh token

## 6. 当前登录用户

### `GET /api/auth/me`

请求头：

1. `Authorization: Bearer <accessToken>`

成功响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "userId": "1",
    "username": "analyst01",
    "nickname": "分析师一号",
    "avatarUrl": null,
    "status": "ACTIVE",
    "tenantId": "tenant-demo",
    "roles": ["ANALYST"]
  }
}
```

## 7. 获取任务权限上下文

### `POST /api/auth/access-context`

请求体：

```json
{
  "datasetIds": ["dataset-sales"]
}
```

响应体：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "tenantId": "tenant-demo",
    "userId": "1",
    "roles": ["ANALYST"],
    "allowedDatasets": ["dataset-sales"],
    "maskedColumns": ["phone"],
    "readonly": true
  }
}
```

## 8. 调试接口

### `GET /api/auth/context-demo`

用途：开发期调试，返回 `TaskAccessContext` 示例。

## 9. 错误约定

1. `401`：用户名或密码错误
2. `401`：access token 已失效、已过期或已被登出拉黑
3. `401`：refresh token 无效、已过期或与 Redis 中保存值不匹配
4. `403`：请求了未授权数据集
