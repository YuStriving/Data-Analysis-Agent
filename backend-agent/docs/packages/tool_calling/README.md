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
3. 失败原因缺少统一异常契约，调用方难以保留细节并发送展示事件。
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
4. 不直接管理对话记忆、checkpoint 或 evals，只返回成功结果或抛出工具调用异常。
5. 不把文件数据永久导入 MySQL。

Tool Adapter 本身也要保持纯粹：

```text
name
description
input_args
execute(args, context)
```

工具接收明确参数和独立的 `ToolExecutionContext`，执行明确动作，返回业务数据。
它不接收完整 `ToolCallRequest`，也不反向依赖上下文工程、记忆、提示词或图编排
服务。执行上下文是工具调用的标识和权限范围，不是完整 Agent 状态。

## 3. 基本使用方式

### 3.1 独立执行器与 Core Gate

`BusinessTool` 只声明 name、description、input_args 与 execute(args, context)。
input_args 是 JSON Schema，实际参数独立传入。工具不判断调用者资格。
配置与 Gate 在装配位置注入：

```python
from agent_backend.capabilities.agent_runtime.tool_calling import (
    ToolExecutionContext, ToolExecutor,
)
from agent_backend.capabilities.data_analysis.tools.chart import ChartSpecBuilderTool
from agent_backend.capabilities.data_analysis.tools.config import build_data_analysis_tool_options
from agent_backend.capabilities.data_analysis.tools.runtime import build_data_analysis_tool_authorization_gate

tool = ChartSpecBuilderTool()
gate = build_data_analysis_tool_authorization_gate()
executor = ToolExecutor(
    options=build_data_analysis_tool_options()[(tool.name, "v1")],
    authorize=gate.check,
)
context = ToolExecutionContext(
    agent_name="data_analysis_agent", agent_version="v1", node_id="build_chart",
    task_id="task-1", trace_id="trace-1", session_id="session-1",
    tenant_id="tenant-1", user_id="user-1",
    goal="Analyze sales trends", purpose="Build a chart from the query result",
)
result = await executor.execute(tool, {"query_result": {"columns": [], "rows": []}}, context)
```

必须提供 authorize，即使独立调用执行器也要经过 Core Gate。执行器持有固定配置，
不查询注册表。顺序是输入解析、输入校验、Gate、业务执行、输出校验及结果包装。
goal 和 purpose 必须非空，仅用于执行背景，不能扩大参数或授权范围。
授权和业务检查必须同步返回 None 表示通过，拒绝时抛 ToolCallError；返回 False、True
或 awaitable 都会被明确拒绝。该约定与业务工具支持异步执行相互独立。

### 3.2 Runtime 与业务上下文

```python
from agent_backend.capabilities.agent_runtime.tool_calling import ToolCallRequest
from agent_backend.capabilities.data_analysis.tools.contracts import (
    DataAnalysisToolExecutionContext, DatasetScope,
)
from agent_backend.capabilities.data_analysis.tools.runtime import build_data_analysis_tool_runtime

runtime = build_data_analysis_tool_runtime(engine_resolver=engine_resolver)
context = DataAnalysisToolExecutionContext(
    tool_call_id="call-1", tool_version="v1",
    agent_name="data_analysis_agent", agent_version="v1", node_id="execute_sql",
    task_id="task-1", trace_id="trace-1", session_id="session-1",
    tenant_id="tenant-1", user_id="user-1",
    goal="Analyze sales by region", purpose="Execute the validated aggregation",
    permissions=granted_permissions,
    dataset_scope=DatasetScope(
        selected_dataset_id="dataset-sales",
        allowed_dataset_ids=java_access_context.allowed_dataset_ids,
        dataset_types={"dataset-sales": "mysql"},
    ),
)
result = await runtime.call(ToolCallRequest(
    tool_name="mysql.query_executor",
    args={"dataset_id": "dataset-sales", "sql": "SELECT region, SUM(amount) FROM sales GROUP BY region", "max_rows": 1000},
    context=context,
))
```

engine_resolver、granted_permissions 和 java_access_context 由可信业务装配层提供，
示例不负责授权来源。通用 ToolExecutionContext 不包含数据集字段，DatasetScope
属于数据分析业务契约。request.tool_version 读取 context.tool_version，不重复存储。
Runtime 保留具体上下文对象，取得工具与独立配置后创建执行器。

注册与查询沿用 ToolRegistry；get()/list() 返回业务工具对象。需要自定义 Runtime
时，显式提供 authorize 和 access_policy_resolver。工具列表只用于发现，实际执行仍检查。
Java 保持权限来源，Python 不扩大数据范围。上下文不包含完整图状态、历史消息或凭证。

### 3.3 结果、失败和超时

成功结果包含 tool_call_id、tool_name、tool_version、data。失败抛出 ToolCallError，
to_payload() 保留 reason、message、retryable、detail。已有异常原样传播，取消向上传播，
执行器不自动重试。输出必须非 None、符合 schema 并可 JSON 序列化。

同步工具在线程运行，异步或返回 awaitable 的工具被等待。上下文超时优先，否则采用
执行配置超时；同步线程超时只停止等待，不能保证底层线程已终止。

正式需求与设计集中在 [spec](../../../../spec/tool-calling/spec.md)；
详细测试方案及验证记录在 [tests](../../../../tests/tool-calling.md)。

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

`errors.ToolCallError` 是唯一的工具调用异常类型，包入口也导出它。
失败通过异常传播，不再定义工具状态码、错误码枚举或失败结果模型。

| 字段 | 含义 |
| --- | --- |
| `reason` | 错误原因，用于理解失败和识别重复失败 |
| `message` | 错误内容 |
| `retryable` | 是否允许考虑原样重试，默认 `False` |
| `detail` | 错误细节字典，默认空字典 |

异常的 `to_payload()` 返回上述四字段字典。已有 `ToolCallError` 原样传播；普通
业务异常统一转为该类型；超时异常的 `retryable` 为 `True`；任务取消继续向上传播。
`retryable` 表达重试可能性，执行器不会自动重试。SQL 修复、修改参数、追问用户等
恢复策略由调用方决定。

本模块已移除专用生命周期日志、日志策略和调用日志 metadata。后续可在外层通过
`emit` 发送事件展示进度和异常。当前 `build_context` 捕获工具异常，将
`to_payload()` 完整保存到失败节点及任务结果的 `tool_error` 字段；尚未接通
Python → Java → 前端 SSE 的工具异常展示链路。

## 6. 相关文件

代码：

```text
src/agent_backend/capabilities/agent_runtime/tool_calling/contracts.py
src/agent_backend/capabilities/agent_runtime/tool_calling/errors.py
src/agent_backend/capabilities/agent_runtime/tool_calling/registry.py
src/agent_backend/capabilities/agent_runtime/tool_calling/executor.py
src/agent_backend/capabilities/agent_runtime/tool_calling/runtime.py
src/agent_backend/capabilities/data_analysis/tools/registry.py
src/agent_backend/capabilities/data_analysis/tools/config.py
src/agent_backend/capabilities/data_analysis/tools/contracts.py
src/agent_backend/capabilities/data_analysis/tools/policy.py
src/agent_backend/capabilities/agent_runtime/execution_control/tool_authorization_gate.py
src/agent_backend/capabilities/data_analysis/tools/runtime.py
src/agent_backend/capabilities/data_analysis/tools/mysql/service.py
src/agent_backend/capabilities/data_analysis/tools/relation/service.py
src/agent_backend/capabilities/data_analysis/tools/chart/service.py
```

测试：

```text
tests/unit/test_tool_calling_runtime.py
tests/unit/test_tool_executor.py
tests/unit/test_tool_authorization_gate.py
tests/unit/test_data_analysis_tools.py
tests/unit/test_data_analysis_tool_runtime.py
```
