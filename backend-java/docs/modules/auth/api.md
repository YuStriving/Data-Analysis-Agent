# Java Auth 模块 API 文档

## 1. 基础信息

1. 基础路径：`/api/auth`
2. 返回包装：`ApiResponse<T>`
3. 当前采用双令牌方案：
   - `accessToken` 返回给前端，由前端本地存储并在后续请求中放入 `Authorization` 请求头
   - `refreshToken` 返回给前端，同时在后端 Redis 中按用户维度保存
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
    "refreshToken": "jwt-refresh-token",
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

请求体：

```json
{
  "refreshToken": "jwt-refresh-token"
}
```

刷新策略说明：

1. 后端校验 refresh token 的签名、过期时间与 `token_type=refresh`
2. 后端校验 Redis 中保存的 refresh token 是否与请求值一致
3. 校验通过后签发新的一对 token，并覆盖 Redis 中该用户原有的 refresh token

## 5. 登出

### `POST /api/auth/logout`

请求头：

1. `Authorization: Bearer <accessToken>`

请求体：

```json
{
  "refreshToken": "jwt-refresh-token"
}
```

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

1. 后端删除 Redis 中该用户保存的 refresh token
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
