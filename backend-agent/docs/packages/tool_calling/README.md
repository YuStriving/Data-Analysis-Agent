# Tool Calling README

## 1. 这个模块解决什么问题

`tool_calling` 负责给 Agent 和 workflow node 提供统一的工具调用入口。

在数据分析 Agent 里，工具调用会覆盖这些能力：

```text
读取 MySQL schema
执行 MySQL 只读 SQL
把 CSV / XLS / XLSX 归一化成关系表
基于 DuckDB 查询归一化后的文件 relation
生成通用 chart spec
```

如果每个节点直接调用具体工具，会有几个问题：

1. 参数校验、权限校验、超时和错误包装容易分散。
2. 工具结果格式不统一，Agent 难以稳定处理失败。
3. 工具调用日志缺少统一 trace，后续排障、审计和 evals 不好做。
4. 后续从 Graph Workflow 演进到 Model Tool Calling 时，工具 schema 缺少统一来源。

一句话理解：

```text
tool_calling 是 Agent 调用工具的统一运行时入口。
```

## 2. 它不做什么

`tool_calling` 不负责：

1. 不决定业务流程。何时调用工具由 graph、lifecycle 或 Agent 节点决定。
2. 不生成 SQL。SQL 生成属于 Prompt、模型节点和业务 Agent。
3. 不实现完整 SQL 安全策略。只读校验、危险语句拦截等由 `guardrails` 承接。
4. 不直接管理对话记忆、checkpoint 或 evals，只产出可记录的调用结果和事件。
5. 不把文件数据永久导入 MySQL。

Tool Adapter 本身也要保持纯粹：

```text
definition()
execute(args)
```

工具只接收明确参数，执行明确动作，返回明确结果。它不接收完整
`ToolCallRequest`，也不反向依赖 `context`、`memory`、`prompt` 或
`lifecycle`。

## 3. 基本使用方式

调用方通过 `ToolCallingRuntime.call()` 调用工具：

```python
from agent_backend.capabilities.agent_runtime.tool_calling import (
    DatasetScope,
    ToolCallRequest,
    ToolCallingRuntime,
)
from agent_backend.capabilities.data_analysis.tools import build_data_analysis_tool_runtime


runtime = build_data_analysis_tool_runtime(
    engine_resolver=lambda dataset_id: engine,
    file_resolver=lambda file_ref: file_ref,
)

result = await runtime.call(
    ToolCallRequest(
        tool_call_id="call-1",
        tool_name="mysql.query_executor",
        tool_version="v1",
        agent_name="data_analysis_agent",
        agent_version="v1",
        node_id="execute_sql",
        task_id="task-1",
        trace_id="trace-1",
        session_id="session-1",
        tenant_id="tenant-1",
        user_id="user-1",
        dataset_scope=DatasetScope(
            selected_dataset_id="dataset-sales",
            allowed_dataset_ids=["dataset-sales"],
            dataset_types={"dataset-sales": "mysql"},
            permissions=["dataset:read", "query:execute"],
        ),
        args={
            "dataset_id": "dataset-sales",
            "sql": "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
            "max_rows": 1000,
        },
        timeout_ms=10000,
    )
)
```

成功时：

```text
result.success = true
result.status = succeeded
result.data = 工具业务结果
result.error = null
```

失败时：

```text
result.success = false
result.status = validation_failed / permission_denied / guardrail_rejected / timeout / failed
result.data = null
result.error = 结构化错误
```

数据分析 Agent 也提供从 Java 下发的 dataset metadata 构造工具 runtime 的
MVP 装配入口：

```python
from agent_backend.capabilities.data_analysis.tools import (
    build_data_analysis_tool_runtime,
    build_engine_resolver_from_dataset_metadata,
    build_file_resolver_from_dataset_metadata,
)


dataset_metadata_by_id = {
    "dataset-sales": {
        "dataset_id": "dataset-sales",
        "dataset_type": "mysql",
        "display_name": "Sales",
        "mysql": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "sales",
            "username": "readonly_user",
            "password": "readonly_password",
            "driver": "mysql+pymysql",
        },
    },
    "dataset-upload-1": {
        "dataset_id": "dataset-upload-1",
        "dataset_type": "xlsx",
        "display_name": "sales.xlsx",
        "file_ref": "oss://bucket/path/sales.xlsx",
        "local_path": "runtime/files/sales.xlsx",
        "sheet_names": ["Sheet1"],
        "header_row": 1,
    }
}

tool_runtime = build_data_analysis_tool_runtime(
    engine_resolver=build_engine_resolver_from_dataset_metadata(dataset_metadata_by_id),
    file_resolver=build_file_resolver_from_dataset_metadata(dataset_metadata_by_id),
)
```

当前 MVP 每次 `engine_resolver(dataset_id)` 被调用时都会创建新的
SQLAlchemy `Engine`。后续需要按 dataset/连接指纹增加 Engine 缓存，并在连接
轮换或 worker 关闭时释放。当前简单方案允许 Java 把只读连接信息下发给
Python；生产化前需要替换成 Java 下发的 secret ref 或短 TTL 只读连接凭证。

文件型数据集通过 `file_resolver(file_ref) -> local_path` 进入
`file.relation_normalizer`。MVP resolver 支持本地路径和 `file://` URI，也支持
Java 在 dataset metadata 里把 `file_ref` 映射到本地暂存路径 `local_path`。
裸 `oss://` 当前会被拒绝。生产化前应由 Java 校验文件权限，并下发 signed URL、
短 TTL 文件 token 或 Java 暂存后的本地路径；Python 不应持有长期 OSS 凭证。

## 4. 当前工具清单

MVP 暴露 5 个 Agent 可见工具：

```text
mysql.schema_reader
mysql.query_executor
file.relation_normalizer
relation.query_executor
chart.spec_builder
```

### mysql.schema_reader

读取授权 MySQL 数据集的 schema，并输出统一 RelationSchema 风格结构。

MySQL 映射规则：

```text
relation_name = 原始表名
column_name = 原始字段名
display_name = 表或字段备注；没有备注时使用原名
original_name = 原始表名或字段名
```

### mysql.query_executor

执行已校验的 MySQL 只读 SQL，并输出统一 QueryResult。

`max_rows` 策略：

```text
如果 SQL 已经有 LIMIT，执行时仍不能超过 max_rows。
如果 SQL 没有 LIMIT，通过 fetch 限制最多返回 max_rows。
```

### file.relation_normalizer

把 CSV、XLS、XLSX 文件型数据源转换为统一关系表模型。

文件归一化策略：

```text
relation_name = relation_1
column_name = col_1
display_name = 原始可读名
original_name = 原始名
```

MVP 使用进程内 `InMemoryRelationStore` 保存归一化结果，后续可替换为
checkpoint/cache。

### relation.query_executor

基于 `normalized_relation_id`，使用 DuckDB 查询归一化后的文件 relation。

它不读取原始文件，也不做文件归一化，只执行已经准备好的 relation SQL。

### chart.spec_builder

基于 QueryResult 生成前端无关的通用 chart spec。MVP 支持：

```text
bar
line
pie
table
```

MVP 只使用一个默认图表生成策略，不做多模型路由，也不生成图片。

## 5. 错误处理

`status` 表示结果大类，`error.code` 表示失败细类。

MVP status：

```text
succeeded
validation_failed
permission_denied
guardrail_rejected
timeout
failed
```

常见错误码：

```text
TOOL_NOT_FOUND
TOOL_VERSION_NOT_FOUND
TOOL_ARGUMENT_INVALID
TOOL_RESULT_INVALID
TOOL_PERMISSION_DENIED
TOOL_AGENT_NOT_ALLOWED
TOOL_NODE_NOT_ALLOWED
TOOL_DATASET_NOT_ALLOWED
TOOL_DATASET_TYPE_UNSUPPORTED
GUARDRAIL_REJECTED
TOOL_TIMEOUT
TOOL_EXECUTION_FAILED
```

`error.retryable` 只表示同一工具、同一参数原样重试是否可能成功。它不表示
workflow 可恢复。SQL 修复、重新构造参数、追问用户等恢复策略由 workflow
基于 `error.code` 和 `error.detail` 决定。

## 6. 相关文件

代码：

```text
src/agent_backend/capabilities/agent_runtime/tool_calling/contracts.py
src/agent_backend/capabilities/agent_runtime/tool_calling/registry.py
src/agent_backend/capabilities/agent_runtime/tool_calling/runtime.py
src/agent_backend/capabilities/agent_runtime/tool_calling/logging.py
src/agent_backend/capabilities/data_analysis/tools/registry.py
src/agent_backend/capabilities/data_analysis/tools/runtime.py
src/agent_backend/capabilities/data_analysis/tools/mysql/service.py
src/agent_backend/capabilities/data_analysis/tools/relation/service.py
src/agent_backend/capabilities/data_analysis/tools/chart/service.py
```

测试：

```text
tests/unit/test_tool_calling_runtime.py
tests/unit/test_data_analysis_tools.py
tests/unit/test_data_analysis_tool_runtime.py
```
