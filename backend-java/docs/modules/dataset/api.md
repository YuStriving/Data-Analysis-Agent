# Java Dataset 模块 API 文档

本文按 `DatasetController` 当前路由整理。列表、详情、预览和授权接口尚未由该控制器提供。

## 1. 模块基础信息

1. 基础路径：`/api/datasets`
2. 返回包装：`ApiResponse<T>`

## 2. 上传文件

### `POST /api/datasets/upload`

请求类型：`multipart/form-data`

表单字段：

1. `file`
2. `datasetName`
3. `description`

当前成功响应的 `data` 字段包含 `datasetId`、`sourceType` 和 `status`；上传内容存入配置的对象存储。

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "datasetId": "dataset-file-001",
    "sourceType": "CSV",
    "status": "REGISTERING"
  }
}
```

## 3. 注册 MySQL 数据集

### `POST /api/datasets/mysql/register`

请求体：

```json
{
  "datasetName": "sales_mysql",
  "host": "127.0.0.1",
  "port": 3306,
  "database": "demo",
  "username": "readonly_user",
  "password": "<request-only secret>",
  "tableNames": ["sales"]
}
```

`datasetName`、`host`、`database`、`username`、`password` 非空；`port` 必填且须在
1–65535 范围内；请求至少应提供表名。服务端探测连接与表结构后写入元数据，密码以密文保存，
响应不包含密码或完整连接信息。

## 4. 演示接口

### `GET /api/datasets/demo`

用途：开发期返回固定演示数据集对象。

## 5. 当前路由与缺口

| 方法 | 路径 | 当前行为 |
| --- | --- | --- |
| `POST` | `/api/datasets/upload` | 上传 CSV/XLS/XLSX 文件并返回注册中状态 |
| `POST` | `/api/datasets/mysql/register` | 校验连接和所选表，保存数据集与加密后的连接密码 |
| `GET` | `/api/datasets/demo` | 返回固定演示对象 |

列表、详情、预览和授权管理接口目前没有对应路由，不能依赖旧示例调用。
