# Agent 能力层总体设计 v0.1

## 1. 文档目的

本文档沉淀当前阶段 `backend-agent` 的 Agent 能力层方案，用于后续继续拆解 `context`、`memory`、`prompt`、`tool_calling`、`guardrails`、`checkpoint`、`lifecycle`、`registry` 等具体模块。

本文档只定义方案和边界，不要求当前立即完成全部代码实现。

## 2. 总体结论

当前项目采用：

```text
agent_runtime 通用运行时
+
data_analysis_agent 业务 Agent
```

`agent_runtime` 是所有 Agent 复用的执行框架和通用能力接口。它不直接处理具体业务分析，而是负责上下文、记忆、Prompt、工具调用、安全约束、运行恢复、观测、评测、生命周期和 Agent 注册。

`data_analysis_agent` 是首个业务 Agent，负责自然语言数据分析主链路：根据用户问题生成只读 SQL，执行查询，解释结果，并生成通用图表描述。

后续如果演进为多 Agent 架构，不要求每个 Agent 继承一个庞大的 runtime 父类。推荐做法是每个具体 Agent 注册自己的 `AgentSpec`，由 `agent_runtime` 统一调度。

## 3. 分层关系

```text
foundation
  底层契约、数据源适配、Redis、MongoDB、MySQL、文件数据源 Adapter

agent_runtime
  Agent 通用执行框架和通用能力接口

data_analysis_agent
  自然语言转 SQL、查询执行、结果解释、图表生成

Java Backend
  认证鉴权、数据集管理、任务入口、SSE 转发、审计边界
```

边界原则：

1. Java 负责认证、授权、任务入口和浏览器侧流式推送。
2. Python Agent 负责分析执行、SQL 生成、SQL 执行和结果生成。
3. Agent 只能使用 Java 下发的最小权限上下文，不允许自行扩大数据集范围。
4. Python Agent 可以直接连接数据源读取 schema 和执行只读 SQL。
5. 最终浏览器展示协议由 Java 和前端承接，Python MVP 阶段输出结构化事件后由 Java 原样转发。

## 4. agent_runtime 模块职责

### 4.1 context

负责上下文裁剪、压缩、注入和追问上下文构造。

核心信息：

1. `task_id`、`trace_id`、`tenant_id`、`user_id`、`session_id`
2. 用户本轮问题
3. 当前 session 可用数据集
4. 当前选中的数据集
5. 数据源 schema 摘要
6. 多轮对话摘要
7. 上一轮 SQL、结果摘要和图表摘要
8. SQL 修复所需的失败经验
9. 当前 Agent 的上下文策略版本

多 Agent 场景下，具体 Agent 不能直接读取全量上下文。Agent 需要声明自己的 `ContextPolicy`，由 `context` 模块裁剪生成 `ContextBundle` 后再注入。

### 4.2 memory

负责热上下文、长期记忆、结果摘要和分析过程事件沉淀。

核心信息：

1. Redis 热上下文
2. Redis 待落库队列
3. MongoDB 长期对话历史
4. MongoDB 结构化分析事件
5. 用户问题、生成 SQL、SQL 错误、修复经验
6. 查询结果摘要和必要引用
7. 图表 spec 摘要
8. 最终回答

MVP 阶段上下文按 `session` 隔离。切换新的对话窗口后，应视为新的 session。

长期历史需要沉淀到 MongoDB，为后续用户画像、偏好学习、常用指标和常用图表类型做铺垫。

`memory` 不负责节点级 checkpoint 和运行恢复。checkpoint 属于 `agent_runtime` 的独立恢复能力，可以与 memory 复用相同的 scope、存储适配器和序列化规范，但不应与对话记忆、分析事件混在同一职责里。

### 4.3 prompt

负责 Prompt 模板、版本、变量渲染和 Prompt 选择。

核心信息：

1. system prompt
2. SQL 生成 prompt
3. SQL 修复 prompt
4. 结果解释 prompt
5. 图表生成 prompt
6. prompt version
7. prompt variables
8. prompt 渲染结果 hash

Prompt 不应硬编码在业务节点里。每次执行应记录实际使用的模板版本，便于回放和评测。

### 4.4 tool_calling

负责工具注册、工具参数校验、基础权限校验、工具调用分发、超时控制、
错误包装、工具结果规范化和工具调用观测。

`tool_calling` 当前只面向 Agent 和 workflow node 提供工具调用能力，不作为
面向终端用户或外部系统的开放接口。它的核心目标不是维护一个“工具大全”，
而是提供一套统一、可校验、可追踪、可演进的工具调用协议。

#### 4.4.1 职责边界

Tool 本身应保持纯工具能力：只接收明确参数、执行明确动作、返回明确结果。
具体 Tool Adapter 不应反向依赖 `context`、`memory`、`prompt`、
`lifecycle` 等 Agent runtime 模块，也不应感知完整 Agent 编排过程。

`tool_calling` 负责：

1. 注册当前系统允许被 Agent 或 workflow node 调用的工具。
2. 暴露工具定义，供 workflow 调度或后续 Model Tool Calling 注入工具
   schema。
3. 校验工具调用参数是否符合工具声明的 `input_schema`。
4. 在统一入口完成基础权限校验，包括 Agent、node、租户、用户、数据集范围
   和数据源类型。
5. 将工具调用分发给具体 Tool Adapter。
6. 统一处理超时、异常捕获和错误码包装。
7. 将工具原始返回规范化为统一的 `ToolCallResult`。
8. 记录工具调用观测事件，包括 trace、耗时、成功状态、错误码和结果摘要。

`tool_calling` 不负责：

1. 不负责决定业务流程。何时调用哪个工具由 `lifecycle`、graph 或具体
   Agent 节点决定。
2. 不负责生成 SQL。SQL 生成属于 Prompt、模型节点和业务 Agent 的职责。
3. 不负责完整 SQL 安全策略。SQL 只读校验、表字段范围、危险语句拦截等
   属于 `guardrails`，`tool_calling` 只负责在执行前接入安全校验。
4. 不负责底层数据源连接细节。MySQL、文件读取、DuckDB relation 注册等
   底层能力由 `foundation` 或具体 Tool Adapter 封装。
5. 不负责对话记忆、checkpoint 或 evals 数据沉淀，只向这些模块提供可记录
   的调用事件和结果摘要。

推荐关系：

```text
Agent / workflow node
-> ToolCallingRuntime.call(ToolCallRequest)
   -> ToolRegistry
   -> parameter validator
   -> permission checker
   -> guardrails hook
   -> Tool Adapter
   -> result normalizer
   -> observability event
```

核心信息：

1. 工具名称和描述
2. 输入参数 schema
3. 输出结果 schema
4. 工具版本
5. 工具所属 Agent
6. 允许调用的节点
7. 所需权限和数据源类型
8. 超时配置
9. 重试配置
10. 是否需要人工审核
11. 观测日志脱敏策略

#### 4.4.2 ToolDefinition v1

`ToolDefinition` 描述工具的稳定元数据。参数 schema 建议参考 OpenAI
tool/function calling 的 JSON Schema 风格，便于后续向 Model Tool Calling
演进；内部调用请求和执行结果仍使用项目自定义的 `ToolCallRequest` 和
`ToolCallResult`。

MVP 字段：

```text
name
version
description
input_schema
output_schema
allowed_agents
allowed_nodes
supported_dataset_types
required_permissions
timeout_ms
retry_policy
log_policy
```

可选字段：

```text
requires_review
tags
risk_level
```

字段说明：

1. `name`：工具唯一名称，例如 `mysql.query_executor`。
2. `version`：工具协议版本，例如 `v1`，用于历史回放、checkpoint 和 evals。
3. `description`：工具说明，同时服务开发者和后续模型工具描述。
4. `input_schema`：输入参数 schema，用于执行前参数校验。
5. `output_schema`：成功结果 schema，用于结果规范化前后的校验。
6. `allowed_agents`：允许调用该工具的 Agent 列表。
7. `allowed_nodes`：允许调用该工具的 workflow node 列表。工具既可由 node
   调用，也可由 Agent 直接调用；Agent 直接调用时 `node_id` 可为空。
8. `supported_dataset_types`：工具支持的数据源类型。
9. `required_permissions`：调用该工具所需的基础权限。
10. `timeout_ms`：单次调用默认超时时间。
11. `retry_policy`：工具层原样重试策略。SQL 查询类工具 MVP 默认不在工具层
    自动重试，SQL 修复重试由 workflow 控制。
12. `log_policy`：日志脱敏和采样策略。

#### 4.4.3 ToolCallRequest v1

`ToolCallRequest` 描述某一次工具调用如何发起。它应携带足够的运行时身份、
链路和权限范围，但不携带完整 Prompt、Memory、Checkpoint 或底层连接配置。

字段：

```text
tool_call_id
tool_name
tool_version
agent_name
agent_version
node_id
task_id
trace_id
session_id
tenant_id
user_id
dataset_scope
args
timeout_ms
```

字段分组：

1. 调用标识：`tool_call_id`、`tool_name`、`tool_version`。
2. 调用来源：`agent_name`、`agent_version`、`node_id`。
3. 链路追踪：`task_id`、`trace_id`、`session_id`。
4. 权限上下文：`tenant_id`、`user_id`、`dataset_scope`。
5. 工具入参：`args`。
6. 执行控制：`timeout_ms`。

`node_id` 为可选字段。workflow node 调用时填入具体节点，例如
`execute_sql`；Agent 自主调用工具时可为空。

#### 4.4.4 ToolCallResult v1

`ToolCallResult` 描述某一次工具调用如何结束。

字段：

```text
tool_call_id
tool_name
tool_version
success
status
data
error
metadata
```

成功和失败约束：

```text
success = true:
data != null
error = null

success = false:
data = null
error != null
```

`metadata` 保存轻量执行信息，例如 `latency_ms`、`attempt`、`max_attempts`、
`dataset_id`、`dataset_type`、`row_count`、`truncated`、`input_hash` 和
`output_summary`。业务结果只放入 `data`，失败原因只放入 `error`。

#### 4.4.5 Tool 接口

具体工具实现只暴露最小接口：

```text
definition()
execute(args)
```

`execute(args)` 只接收工具参数，不接收完整 `ToolCallRequest`。权限、超时、
日志、错误包装和结果规范化由 `ToolCallingRuntime` 统一处理。

`ToolCallingRuntime` 面向 Agent 和 workflow node 暴露：

```text
list_tools(agent_name=None)
get_tool(tool_name, tool_version=None)
call(request)
```

`ToolRegistry` 面向 `tool_calling` 内部使用：

```text
register(tool)
get(name, version=None)
list()
```

Agent 不应绕过 `ToolCallingRuntime.call()` 直接执行 Tool Adapter，否则会
绕过参数校验、基础权限校验、超时、错误包装和观测日志。

#### 4.4.6 调用流程

`ToolCallingRuntime.call()` 的 MVP 流程：

```text
1. 接收 ToolCallRequest
2. 记录 tool_call_started 事件
3. 根据 tool_name + tool_version 解析 Tool
4. 校验 tool 是否存在
5. 校验 agent / node 是否允许调用
6. 校验 dataset_scope 和 dataset_type
7. 按 input_schema 校验 args
8. 如有需要，调用 guardrails hook
9. 按 timeout_ms 执行 Tool Adapter
10. 校验工具原始结果是否符合 output_schema
11. 包装成功 ToolCallResult
12. 记录 tool_call_finished 事件
13. 返回 ToolCallResult
```

所有可结构化表达的失败都应返回 `ToolCallResult(success=false)`，避免向
Agent 暴露零散异常。

#### 4.4.7 status 与错误码

`status` 表示结果状态大类，`error.code` 表示失败原因细类。

MVP `status`：

```text
succeeded
validation_failed
permission_denied
guardrail_rejected
timeout
failed
```

错误码映射：

```text
TOOL_NOT_FOUND -> validation_failed
TOOL_VERSION_NOT_FOUND -> validation_failed
TOOL_ARGUMENT_INVALID -> validation_failed
TOOL_RESULT_INVALID -> validation_failed

TOOL_PERMISSION_DENIED -> permission_denied
TOOL_AGENT_NOT_ALLOWED -> permission_denied
TOOL_NODE_NOT_ALLOWED -> permission_denied
TOOL_DATASET_NOT_ALLOWED -> permission_denied
TOOL_DATASET_TYPE_UNSUPPORTED -> permission_denied
TOOL_REVIEW_REQUIRED -> permission_denied

GUARDRAIL_REJECTED -> guardrail_rejected
TOOL_TIMEOUT -> timeout
TOOL_EXECUTION_FAILED -> failed
```

错误对象包含：

```text
code
message
detail
retryable
```

`retryable` 只表示同一工具、同一参数原样重试是否可能成功。它不同于
workflow recoverable。后续 workflow 可基于 `error.code` 和 `error.detail`
增加恢复策略映射，例如 SQL 修复、重建参数、追问用户或切换数据集。

#### 4.4.8 观测日志与脱敏

MVP 记录两个事件：

```text
tool_call_started
tool_call_finished
```

`tool_call_started` 建议字段：

```text
event_type
tool_call_id
tool_name
tool_version
agent_name
agent_version
node_id
task_id
trace_id
session_id
tenant_id
user_id
dataset_id
dataset_type
started_at
timeout_ms
args_hash
input_summary
```

`tool_call_finished` 建议字段：

```text
event_type
tool_call_id
tool_name
tool_version
agent_name
agent_version
node_id
task_id
trace_id
session_id
tenant_id
user_id
dataset_id
dataset_type
started_at
finished_at
latency_ms
success
status
error_code
error_message
error_detail
retryable
attempt
max_attempts
truncated
row_count
output_summary
```

`tool_call_finished` 表示调用已经结束，不表示调用成功。成功或失败由
`success` 表示；失败原因必须通过 `error_code`、`error_message`、
`error_detail` 和 `retryable` 记录。

日志策略：

1. SQL 原文可以记录，但应进入专门的 Agent event / audit 存储，不进入普通
   应用日志。
2. SQL 记录应绑定 `tenant_id`、`user_id`、`task_id` 和 `trace_id`。
3. 查询结果默认不完整记录，只记录 `columns`、`row_count`、`truncated`、
   `sample_rows` 和 `result_summary`。
4. `sample_rows` 默认最多 20 行。
5. 不默认记录 `full_rows`。
6. 不记录完整本地文件路径，只记录 `file_ref`、`dataset_id`、`file_name`、
   `file_ext`、`file_size` 和 `sheet_names` 等非敏感摘要。
7. 不记录数据库连接信息、连接字符串、账号、密码、token、host、port 等。

推荐 `log_policy`：

```json
{
  "record_sql": true,
  "record_sql_redacted": true,
  "record_args": false,
  "record_args_hash": true,
  "record_result_sample": true,
  "result_sample_limit": 20,
  "record_full_result": false,
  "record_output_summary": true,
  "record_file_path": false,
  "record_connection_info": false
}
```

首期工具需要覆盖：

1. `mysql.schema_reader`
2. `mysql.query_executor`
3. `file.relation_normalizer`
4. `relation.query_executor`
5. `chart.spec_builder`

#### 4.4.9 MVP 工具职责

`mysql.schema_reader`：

1. 职责：读取授权 MySQL 数据集的 schema，并转换成统一 RelationSchema 风格。
2. 输入：`dataset_id`、`table_names`、`include_sample_values`、`max_tables`、
   `max_columns_per_table`、`sample_rows`。
3. 输出：`dataset_id`、`dataset_type`、`relations`。
4. 不负责：不生成 SQL、不执行 SQL、不判断用户问题意图、不做跨 dataset
   自动 join、不返回大量原始数据。

MySQL 的 RelationSchema 映射规则：

```text
relation_name = 原始表名
column_name = 原始字段名
display_name = 表或字段备注；没有备注时使用原名
original_name = 原始表名或字段名
```

`mysql.query_executor`：

1. 职责：在授权 MySQL 数据集上执行已校验的只读 SQL，并返回统一 QueryResult。
2. 输入：`dataset_id`、`sql`、`max_rows`、`relation_names`。
3. 输出：`dataset_id`、`dataset_type`、`columns`、`rows`、`row_count`、
   `truncated`、`execution_time_ms`。
4. 不负责：不生成 SQL、不修复 SQL、不解释查询结果、不生成图表、不决定业务
   指标口径。

`max_rows` 策略：

```text
如果 SQL 已经有 LIMIT，执行时仍不能超过 max_rows。
如果 SQL 没有 LIMIT，可以由执行层包装或 cursor / fetch 限制最多返回 max_rows。
```

`file.relation_normalizer`：

1. 职责：把 CSV、XLS、XLSX 文件型数据源转换为统一关系表模型。
2. 输入：`dataset_id`、`dataset_type`、`file_ref`、`sheet_names`、
   `header_row`、`sample_rows`、`max_rows_to_inspect`。
3. 输出：`dataset_id`、`dataset_type`、`normalized_relation_id`、
   `relations`、`warnings`。
4. 不负责：不生成 SQL、不执行分析查询、不解释结果、不生成图表、不修改源
   文件、不写回 Excel、不把文件数据永久导入 MySQL、不跨 dataset 自动 join。

文件型数据源归一化策略：

```text
relation_name = relation_1
column_name = col_1
display_name = 原始可读名
original_name = 原始名
```

`relation.query_executor`：

1. 职责：基于 `file.relation_normalizer` 生成的 `normalized_relation_id`，
   使用 DuckDB 查询归一化后的 relation，并返回统一 QueryResult。
2. 输入：`dataset_id`、`normalized_relation_id`、`sql`、`max_rows`、
   `relation_names`。
3. 输出：`normalized_relation_id`、`columns`、`rows`、`row_count`、
   `truncated`、`execution_time_ms`。
4. 不负责：不读取原始文件结构、不做文件归一化、不生成 SQL、不修复 SQL、
   不解释结果、不生成图表、不修改源文件、不把文件导入 MySQL。

文件型数据源查询统一使用 DuckDB 执行只读 SQL。Agent 面向统一
RelationSchema / QueryResult，不直接感知 pandas、openpyxl 或文件格式细节。

`chart.spec_builder`：

1. 职责：基于 QueryResult 生成通用 chart spec。
2. 输入：`query_result`、`chart_type`、`intent`、`field_mapping`、
   `max_points`。
3. 输出：`chart`、`warnings`。
4. 不负责：不直接渲染图表、不生成 ECharts option、不生成图片、不执行查询、
   不修改查询结果、不判断复杂业务指标口径。

MVP 阶段 `chart.spec_builder` 只使用一个默认图表生成策略，不做多模型路由；
后续可以增加 `chart_model`、`builder_version` 或专门的画图模型。首期
`chart.spec_builder` 输出前端无关的通用 chart spec，支持 `bar`、`line`、
`pie` 和 `table`。

### 4.5 guardrails

负责 SQL 安全、数据集权限、字段范围、行数限制、输出格式和风险拦截。

核心信息：

1. 只允许 `SELECT`
2. 禁止 DDL 和 DML
3. 禁止多语句执行
4. 表范围必须属于当前数据集
5. 字段范围必须属于授权 schema
6. 最大返回行数来自配置
7. 查询超时来自配置
8. 高风险命中原因

SQL 失败允许自动修复，但最多重试 3 次。每次修复必须携带上一轮失败 SQL、错误信息、失败阶段和当前 retry count。

### 4.6 observability

负责 trace、节点事件、工具调用日志、耗时、错误和告警。

核心信息：

1. `trace_id`
2. `task_id`
3. `node_id`
4. `tool_call_id`
5. token usage
6. latency
7. SQL 校验结果
8. SQL 执行状态
9. recovery event
10. alert log

### 4.7 evals

负责 Agent 输出质量、安全性和回归样例评测。

核心信息：

1. 标准测试问题
2. 期望 SQL 特征
3. 非法 SQL 回归用例
4. 图表 spec 合法性检查
5. 多轮追问样例
6. SQL 修复样例
7. 回答质量评估

### 4.8 checkpoint

负责 Agent 运行状态快照、节点恢复和失败续跑。

核心信息：

1. `snapshot_id`
2. `task_id`
3. `trace_id`
4. `tenant_id`
5. `user_id`
6. `session_id`
7. 当前 graph、节点、节点状态和恢复游标
8. 当前任务摘要、步骤和目标
9. 已注入的上下文摘要
10. 最近工具调用状态
11. Prompt 版本、模型、token usage 和耗时
12. 失败阶段、恢复原因和最后稳定 checkpoint

`checkpoint` 面向系统恢复，不面向业务记忆。它可以持久化到 MongoDB 的独立集合，例如 `agent_checkpoints` 或 `runtime_checkpoints`，并使用 `snapshot_id` 做幂等写入。

### 4.9 lifecycle

负责统一调度 Agent 执行流程。

推荐生命周期：

```text
receive_task
-> resolve_dataset
-> load_schema
-> build_context
-> classify_intent
-> generate_sql
-> validate_sql
-> execute_sql
-> interpret_result
-> build_chart_spec
-> persist_context
-> emit_result
```

`lifecycle` 不实现具体业务分析逻辑，只负责把 runtime 能力和业务 Agent 节点串起来。

### 4.10 registry

负责 Agent 注册、能力声明和任务路由。

核心信息：

1. `agent_name`
2. `agent_version`
3. `supported_task_types`
4. `required_context_keys`
5. `required_tools`
6. `required_guardrails`
7. `entry_graph`
8. 输出结构版本

后续多 Agent 架构下，新增 Agent 应优先新增 `AgentSpec`，而不是复制 runtime 逻辑。

## 5. data_analysis_agent MVP

`data_analysis_agent` 首期支持数据源：

1. MySQL
2. CSV
3. XLS
4. XLSX

首期支持问题类型：

1. 指标查询
2. 分组统计
3. 趋势分析
4. 对比分析
5. 图表生成
6. 多轮追问

MVP 主链路：

```text
用户自然语言输入
-> 解析当前 session 可用数据集
-> Python 实时读取数据源 schema
-> 生成只读 SQL
-> SQL 安全校验
-> Python 执行 SQL
-> 查询失败时自动修复，最多重试 3 次
-> 生成文本回答
-> 可选生成 chart spec
-> 追加 session 上下文
-> 返回 Java
-> Java 原样流式转发给前端
```

## 6. 数据集选择规则

1. 用户本轮显式选择数据集时，使用本轮选择的数据集。
2. 用户未选择数据集时，使用当前 session 最近一次上传或使用的数据集。
3. 当前 session 没有可用数据集时，返回需要选择或上传数据集的提示。
4. 不允许跨 session 自动复用文件暂存区中的数据。
5. 不允许 Agent 自行扩大到未授权数据集。

## 7. Session 文件暂存区

MVP 可以设置 session 级文件暂存区，用于承载 CSV、XLS、XLSX 上传文件。

规则：

1. 每个对话窗口对应一个 `session_id`。
2. 每个 session 拥有独立文件暂存区。
3. 文件暂存区只对当前 session 可见。
4. 切换新对话窗口后，需要重新上传文件或显式选择已有数据集。
5. 最近一次上传或使用的数据集只在当前 session 内自动兜底。

这个设计用于保证多轮追问连续，同时避免不同窗口之间串上下文或串文件。

## 8. Schema 获取策略

MVP 阶段：

1. Python 实时读取 MySQL、CSV、XLS、XLSX 的 schema。
2. Schema 读取结果进入当前任务上下文。
3. 不做 schema 缓存作为首期阻塞项。

TODO：

1. 后续增加 schema 缓存。
2. 后续考虑优先使用 Java 已登记的 schema 元数据。
3. 后续为大文件或大表增加 schema inspect 成本控制。

## 9. 查询结果策略

查询最大返回数量由配置文件控制，例如：

```text
agent.query.max_rows = 1000
```

当结果超过最大数量时：

1. 只返回前 N 行。
2. 生成结果摘要。
3. 明确提示用户结果已截断。
4. 上下文只保存摘要和必要引用，不保存完整大结果。

推荐结果结构：

```json
{
  "answer": "查询结果较多，已返回前 1000 行，并附带摘要。",
  "table_preview": [],
  "result_summary": {},
  "truncated": true,
  "max_rows": 1000,
  "chart": {}
}
```

## 10. Chart Spec v1

首期只支持：

1. `bar`
2. `line`
3. `pie`
4. `table`

Python 返回通用 chart spec，不绑定 ECharts。

示例：

```json
{
  "type": "bar",
  "title": "各地区销售额",
  "xField": "region",
  "yField": "amount",
  "seriesField": null,
  "data": []
}
```

前端负责把 chart spec 转换为具体图表库配置。

## 11. 流式事件策略

MVP 阶段：

1. Python Agent 输出结构化事件。
2. Java 原样转发给前端。
3. 前端按事件类型展示状态、SQL、图表和最终回答。

建议事件类型：

1. `task_started`
2. `dataset_resolved`
3. `schema_loaded`
4. `context_built`
5. `sql_generated`
6. `sql_validated`
7. `sql_repaired`
8. `query_executed`
9. `chart_ready`
10. `task_finished`
11. `task_failed`

## 12. SQL 失败自动修复

SQL 失败允许自动修复，最大重试次数为 3。

流程：

```text
generate_sql
-> validate_sql
-> execute_sql
-> failed
-> collect_error_experience
-> repair_sql
-> validate_sql
-> execute_sql
```

每次修复必须包含：

1. 上一次 SQL
2. 错误信息
3. 失败阶段
4. 相关 schema
5. 禁止重复犯的错误
6. 当前重试次数
7. 最大重试次数

超过最大重试次数后停止自动修复，并返回明确失败原因。

## 13. MVP 暂不实现

1. 多数据集自动 join
2. 复杂归因分析
3. 预测分析
4. 多 Agent 协作
5. 大规模外部 MCP 工具调用
6. 完整人工审核工作台
7. 生产级 schema 缓存
8. 跨 session 自动复用临时文件

## 14. 后续模块设计顺序

推荐后续按以下顺序继续细化：

1. `context`
2. `memory`
3. `prompt`
4. `tool_calling`
5. `guardrails`
6. `checkpoint`
7. `lifecycle`
8. `observability`
9. `evals`
10. `registry`

优先设计 `context`，因为它决定每个节点和每个 Agent 能看到什么信息，也会影响 Prompt、工具调用和记忆结构。
