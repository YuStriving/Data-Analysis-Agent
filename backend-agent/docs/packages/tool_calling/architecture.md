# Tool Calling 架构文档

## 1. 架构目标

`tool_calling` 的架构目标是把“Agent 调用工具”做成一个独立、可测试、可审计
的 Module。

它的外部 Interface 尽量小：

```python
ToolCallingRuntime.call(request) -> ToolCallResult
```

调用方只需要提供：

```text
ToolCallRequest
```

内部 Implementation 负责：

```text
工具解析
Agent / node 权限校验
dataset_scope 和 dataset_type 校验
JSON Schema 参数校验
guardrails hook
timeout
Tool Adapter 分发
输出 schema 校验
ToolCallResult 包装
tool_call_started / tool_call_finished 事件
```

这样做的好处是：后续新增工具、调整权限规则、演进 Model Tool Calling 或接入
外部工具时，Agent 节点不需要到处复制校验和错误处理逻辑。

## 2. 模块结构

```text
capabilities/agent_runtime/tool_calling/
  __init__.py
  contracts.py
  errors.py
  logging.py
  protocols.py
  registry.py
  runtime.py
  validation.py
```

### contracts.py

定义工具调用协议。

主要模型：

```text
ToolDefinition
RetryPolicy
ToolLogPolicy
DatasetScope
ToolCallRequest
ToolCallError
ToolCallMetadata
ToolCallResult
ToolStatus
ToolErrorCode
```

### protocols.py

定义 Tool Adapter 最小协议：

```python
class Tool:
    def definition(self) -> ToolDefinition:
        ...

    def execute(self, args: dict) -> Any:
        ...
```

Tool Adapter 不接收完整 `ToolCallRequest`，避免工具实现反向依赖 Agent runtime。

### registry.py

保存工具实例，按 `name + version` 查询。

主要 Interface：

```text
register(tool)
get(name, version=None)
list()
```

### runtime.py

提供 Agent 和 workflow node 的统一调用入口。

主要 Interface：

```text
list_tools(agent_name=None)
get_tool(tool_name, tool_version=None)
call(request)
```

### logging.py

构建工具调用观测事件，并按 `ToolLogPolicy` 做输入输出摘要。

日志只记录调用证据，不承载完整业务数据。

### validation.py

封装 JSON Schema 校验，把 `jsonschema.ValidationError` 转换为统一
`ToolCallingException`。

## 3. 数据流

一次典型 MySQL 查询流程：

```text
execute_sql node
-> ToolCallRequest(mysql.query_executor)
-> ToolCallingRuntime.call
-> ToolRegistry.get(mysql.query_executor, v1)
-> check allowed_agents / allowed_nodes
-> check dataset_scope / dataset_type / required_permissions
-> validate input_schema
-> guardrails.validate_sql
-> MySQLQueryExecutorTool.execute(args)
-> validate output_schema
-> ToolCallResult(success=true)
-> tool_call_finished event
```

危险 SQL 流程：

```text
mysql.query_executor request
-> validate input_schema
-> guardrails.validate_sql
-> GUARDRAIL_REJECTED
-> ToolCallResult(success=false, status=guardrail_rejected)
```

文件数据源流程：

```text
CSV / XLS / XLSX dataset
-> file.relation_normalizer
-> RelationSchema + normalized_relation_id
-> relation.query_executor
-> DuckDB SQL
-> QueryResult
```

文件数据源对 Agent 呈现为统一关系表：

```text
relation_name = relation_1
column_name = col_1
display_name = 原始可读名
original_name = 原始名
```

## 4. 权限与安全

`tool_calling` 负责基础权限入口：

1. tool name / version 必须存在。
2. `agent_name` 必须在 `allowed_agents` 内。
3. `node_id` 非空时必须在 `allowed_nodes` 内。
4. 数据集必须位于 `dataset_scope.allowed_dataset_ids`。
5. 数据源类型必须位于 `supported_dataset_types`。
6. `dataset_scope.permissions` 必须覆盖 `required_permissions`。

`guardrails` 负责 SQL 安全：

```text
只读 SQL
禁止 DDL / DML
禁止危险语句
后续扩展表字段范围校验
```

二者的关系：

```text
tool_calling 判断“谁能调用什么工具访问哪个数据集”
guardrails 判断“这次具体 SQL 动作是否安全”
```

## 5. 观测与脱敏

MVP 记录两个事件：

```text
tool_call_started
tool_call_finished
```

`tool_call_started` 在工具解析前记录，因此使用保守脱敏策略；未知工具不会记录
SQL 原文或完整文件路径。

`tool_call_finished` 记录：

```text
success
status
error_code
error_message
error_detail
retryable
latency_ms
row_count
truncated
output_summary
```

脱敏策略：

1. SQL 原文可进入专门 Agent event / audit 存储，不进入普通应用日志。
2. 查询结果默认只记录摘要和最多 20 行样例。
3. 不记录完整本地文件路径。
4. 不记录连接字符串、账号、密码、token、host、port。

## 6. 数据分析工具结构

```text
capabilities/data_analysis/tools/
  registry.py
  mysql/
    service.py
  relation/
    service.py
  chart/
    service.py
```

`build_data_analysis_tool_registry()` 负责组装 5 个 MVP 工具：

```text
mysql.schema_reader
mysql.query_executor
file.relation_normalizer
relation.query_executor
chart.spec_builder
```

MySQL 工具通过 `engine_resolver(dataset_id)` 获取 SQLAlchemy Engine。

文件工具通过 `file_resolver(file_ref)` 获取文件路径，`ToolCallRequest` 不传本地
绝对路径作为长期协议。

`normalized_relation_id` 当前由进程内 `InMemoryRelationStore` 管理。后续可以
替换为 Redis、MongoDB、对象存储或 checkpoint/cache。

## 7. 后续演进

### Model Tool Calling

后续从 Graph Workflow 演进到 Model Tool Calling 时：

```text
ToolRegistry
-> 过滤当前 agent / node 允许的 ToolDefinition
-> 转换成模型可用 tool schema
-> 模型返回 tool_call
-> 仍由 ToolCallingRuntime.call 执行
```

模型不能绕过 `ToolCallingRuntime` 直接执行工具。

### Workflow 恢复策略

MVP 只在 `error.retryable` 表达工具层原样重试可能性。

后续 workflow 可以增加恢复策略映射：

```text
GUARDRAIL_REJECTED -> repair_sql
TOOL_ARGUMENT_INVALID -> rebuild_tool_args
TOOL_DATASET_NOT_ALLOWED -> ask_user_select_dataset
TOOL_TIMEOUT -> retry_or_reduce_query_scope
TOOL_EXECUTION_FAILED -> repair_sql 或 fail_task
```

这个恢复策略不放进 Tool Adapter，避免工具理解业务编排。

### Relation 持久化

当前 `InMemoryRelationStore` 只适合 MVP 和单进程运行。

后续需要补：

```text
normalized_relation_id 生命周期
跨进程 relation 读取
临时数据清理
大文件分块或采样
checkpoint/cache 引用
```
