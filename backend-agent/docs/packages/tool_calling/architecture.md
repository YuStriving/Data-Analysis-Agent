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
JSON Schema 参数校验（tool.input_args）
显式注入的业务权限与 SQL 检查
timeout
Tool Adapter 分发
输出 schema 校验
成功时包装 ToolCallResult
失败时抛出 ToolCallError
```

这样做的好处是：后续新增工具、调整权限规则、演进 Model Tool Calling 或接入
外部工具时，Agent 节点不需要到处复制校验和错误处理逻辑。

## 2. 模块结构

```text
capabilities/agent_runtime/tool_calling/
  __init__.py
  contracts.py
  errors.py
  executor.py
  registry.py
  runtime.py
  validation.py
```

### contracts.py

定义工具调用协议。

主要模型：

```text
BusinessTool
InputArgsDefinition
ToolExecutionContext
ToolExecutionOptions
ToolCallRequest
ToolCallResult
```

### BusinessTool 与独立配置

定义 Tool Adapter 最小协议：

```python
class BusinessTool(Protocol):
    name: str
    description: str
    input_args: InputArgsDefinition

    def execute(self, args: dict, context: ToolExecutionContext) -> Any:
        ...
```

Tool Adapter 不接收完整 `ToolCallRequest`，避免工具实现反向依赖 Agent runtime。
`input_args` 只描述输入 schema；工具对象直接提供名称、描述和输入定义，不再维护
重复的定义模型。输出 schema、版本和超时通过 `ToolExecutionOptions` 注入。
访问与审批条件属于独立策略，不要求工具对象声明这些配置。

### registry.py

保存工具实例，按 `name + version` 查询。

主要 Interface：

```text
register(tool, options=None)
get(name, version=None)
get_options(name, version=None)
list()
```

`get()` 和 `list()` 直接返回 `BusinessTool` 对象；执行配置独立保存在注册表中。

### runtime.py

提供 Agent 和 workflow node 的统一调用入口。

主要 Interface：

```text
list_tools(agent_name=None)
get_tool(tool_name, tool_version=None)
get_tool_policy(tool_name, tool_version=None)
call(request)
```

`get_tool()` 和 `list_tools()` 直接返回业务工具对象；`call()` 成功返回
`ToolCallResult`，失败抛出 `ToolCallError`。

### errors.py

定义唯一工具调用异常 `ToolCallError(Exception)`，包含 `reason`、`message`、
`retryable` 和 `detail`。`to_payload()` 返回四字段字典，供调用方记录失败或构造事件。
成功结果只包含调用标识、工具名称、工具版本和业务数据。

### validation.py

封装 JSON Schema 校验，把 `jsonschema.ValidationError` 转换为统一
`ToolCallError`。

## 2.1 统一 Core 授权与具体业务上下文

ToolAuthorizationGate 位于 execution_control，复用 AgentSpec 声明和工具策略。
它检查能力、Agent/节点、权限、风险、审批，并调用注入的业务授权方法。
数据集与只读 SQL 检查仍由数据分析策略负责。Tool 不决定调用资格。

ToolExecutionContext 携带 goal、purpose、permissions，通用契约不包含 DatasetScope。
DataAnalysisToolExecutionContext 与 DatasetScope 位于业务 tools/contracts.py。
ToolCallRequest 组合 tool_name、args、context；tool_version 读取 context。

Runtime 解析工具与配置后构造 ToolExecutor(options=options, authorize=gate.check)。
执行器不依赖注册表，也不提供无授权默认路径；Runtime 不再提供共享 executor 属性。

## 3. 数据流

一次典型 MySQL 查询流程：

```text
execute_sql node
-> ToolCallRequest(mysql.query_executor)
-> ToolCallingRuntime.call
-> ToolRegistry.get(mysql.query_executor, v1)
-> ToolExecutor.execute(tool, raw_input, context)
-> validate tool.input_args
-> injected DataAnalysisToolPolicyChecker.check
-> check agent / node / dataset / permissions / readonly SQL
-> MySQLQueryExecutorTool.execute(args, context)
-> validate output_schema
-> ToolCallResult(tool_call_id, tool_name, tool_version, data)
```

危险 SQL 流程：

```text
mysql.query_executor request
-> validate tool.input_args
-> guardrails.validate_sql
-> raise ToolCallError(reason, message, retryable, detail)
-> caller catches the error and preserves its payload
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

数据分析工厂装配 Core Gate，并注入 `DataAnalysisToolPolicyChecker`。整条授权路径检查：

1. tool name / version 必须存在。
2. `agent_name` 必须在 `allowed_agents` 内。
3. `node_id` 必须有效，工具必须在 AgentSpec 节点声明中，并满足策略的 allowed_nodes。
4. 数据集必须位于 `dataset_scope.allowed_dataset_ids`。
5. 数据源类型必须位于 `supported_dataset_types`。
6. `context.permissions` 必须覆盖 `required_permissions`。

`guardrails` 负责 SQL 安全：

```text
只读 SQL
禁止 DDL / DML
禁止危险语句
后续扩展表字段范围校验
```

通用执行器只执行注入的检查方法。业务策略与通用执行流程的关系：

```text
业务策略声明工具访问、审批和数据集条件
业务检查实现调用 SQL 安全规则
tool_calling 执行输入校验、注入检查、业务方法与结果封装
```

## 5. 异常传播与事件边界

本模块不再提供专用生命周期日志、日志策略或调用日志 metadata，也不负责向前端
发送事件。后续展示链路可由外层通过 `emit` 消费工具调用信息和异常 payload。

已有 `ToolCallError` 原样传播；普通业务异常统一包装为该类型；超时异常允许调用方
考虑重试；任务取消继续向上传播。`retryable` 不触发执行器自动重试。

执行控制在成功后调用 `after_tool_call(request)`，失败后调用
`after_tool_call(request, error)`，以异常的 `reason` 保持重复失败检测。
`build_context` 捕获异常后将完整四字段 payload 保存在失败节点和任务结果的
`tool_error` 中，供后续集成读取。Python → Java → 前端 SSE 的工具异常展示链路
尚未实现。

外层构造展示事件时应避免泄露连接凭据、token 和完整本地文件路径；这一要求不会
通过删除异常细节或吞掉失败来实现。

## 6. 数据分析工具结构

```text
capabilities/data_analysis/tools/
  config.py
  policy.py
  registry.py
  runtime.py
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

`config.py` 声明独立的执行配置与访问策略；`runtime.py` 将业务策略注入
`ToolCallingRuntime`。通用运行时不导入数据分析模块、不读取 SQL 字段，也不按
工具名称选择业务检查。后续通用 Guard 与场景适配层可替换注入检查方法。

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
-> 过滤当前 agent / node 允许的 BusinessTool 对象
-> 转换成模型可用 tool schema
-> 模型返回 tool_call
-> 仍由 ToolCallingRuntime.call 执行
```

模型不能绕过 `ToolCallingRuntime` 直接执行工具。

### Workflow 恢复策略

MVP 只在 `ToolCallError.retryable` 表达工具层原样重试可能性，不自动重试。
后续 workflow 可根据失败原因和细节选择 SQL 修复、重建参数、追问用户、缩小查询
范围或终止任务。这些恢复决策属于业务编排，不放进 Tool Adapter，也不要求通用
工具模块定义错误码枚举和策略映射。

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

## 当前规格入口

需求与接口权威说明见 [spec](../../../../spec/tool-calling/spec.md) 和
[design](../../../../spec/tool-calling/design.md)，详细测试方案统一见
[tests](../../../../tests/tool-calling.md)。同步线程超时只停止等待，不强制终止线程。
