# Agent Runtime Execution Control 模块需求

## 阅读状态与当前实现

本文后续章节记录设计目标和建议验收项，不表示这些策略已自动套用到每张图。
当前已有 `AgentSpec`、`RuntimeExecutionController`、循环/预算/工具守卫、数据分析 preset
和 `ToolAuthorizationGate`，源码分别位于同目录 `execution_control/`；
单元用例见 `tests/unit/test_execution_control.py` 与
`tests/unit/test_tool_authorization_gate.py`。

`RuntimeExecutionController` 是显式创建和调用的能力；当前
`build_data_analysis_graph` 没有把它接入节点调度。因此本模块用例通过不能证明生产图已
执行步数、预算或循环拦截。工具授权 Gate 则由数据分析工具运行时装配。

## 1. 模块定位

`execution_control` 是 `agent_runtime` 中负责 Agent 执行边界的守门模块。

它不实现具体业务分析逻辑，也不替代 LangGraph / workflow 编排。它负责在
workflow 节点调度、模型调用和工具调用前后统一判断：

1. 当前 Agent 是否采用受控执行模式
2. 当前执行是否还能继续
3. 是否触发循环保护
4. 是否触发运行预算保护
5. 是否满足终止条件
6. 当前节点是否允许调用指定工具

本模块目标是让具体 Agent 不需要在各节点内重复实现步数限制、修复次数限制、
工具重复失败限制、运行耗时限制和终止状态判断。

## 2. 当前架构适配

当前 Python Agent Backend 分层如下：

```text
api
orchestration
capabilities
foundation
```

`execution_control` 应落在：

```text
backend-agent/src/agent_backend/capabilities/agent_runtime/execution_control/
```

它与现有模块的关系如下：

```text
orchestration / LangGraph
-> execution_control
-> context / prompt / execution / tool_calling / guardrails / memory / checkpoint
```

职责边界：

1. `orchestration` 负责 workflow 图、节点函数和状态流转。
2. `execution_control` 负责执行模式、循环、预算、终止和工具调用守门。
3. `tool_calling` 负责单次工具调用的解析、权限、schema、guardrails、timeout
   和结果包装。
4. `prompt` 和 `execution` 负责单次 prompt 渲染与 LLM 调用。
5. `checkpoint` 负责节点快照与恢复，后续需要包含 execution control 状态。
6. `memory` 不负责循环控制和预算控制，只记录会话与运行事件。

## 3. 设计原则

1. MVP 只支持 `workflow_mode`，不采用完整 ReAct 作为默认执行范式。
2. 模型只在具体节点内完成单步结构化生成，不允许自由决定全局流程。
3. 工具调用由 workflow 节点和 runtime policy 控制，不允许模型自由选择工具。
4. Runtime 的保护能力必须集中在 `execution_control`，不要散落到各业务节点。
5. 业务 Agent 通过 `AgentSpec` 声明节点、边、工具白名单和运行策略。
6. `execution_control` 只依赖稳定的结构化结果，不解析自然语言推理过程。

## 4. 核心概念

### 4.1 AgentSpec

`AgentSpec` 是具体 Agent 的运行声明。

MVP 字段：

```text
agent_id
execution_mode
entry_node
terminal_nodes
node_specs
edge_specs
runtime_policy
budget_policy
tool_policy
```

`data_analysis_agent` 的默认执行模式为：

```text
workflow_mode
```

### 4.2 NodeSpec

`NodeSpec` 描述 workflow 节点的运行约束。

MVP 字段：

```text
node_id
allowed_tools
max_visits
can_emit_final_result
```

### 4.3 EdgeSpec

`EdgeSpec` 描述 workflow 允许的节点跳转。

MVP 字段：

```text
from_node
to_node
max_traversals
loop_name
```

节点返回的 `next_node` 必须经过 `EdgeSpec` 校验。未声明的边不得执行。

### 4.4 NodeExecutionResult

节点完成后必须返回或映射为结构化结果。

MVP 字段：

```text
node_id
status
next_node
error_code
error_message
retryable
user_action_required
metadata
```

节点只能提出执行结果，不能绕过 runtime 直接决定全局调度。

## 5. 执行模式控制需求

MVP 阶段仅支持：

```text
workflow_mode
```

需求：

1. Agent 必须通过 `AgentSpec.execution_mode` 声明执行模式。
2. `workflow_mode` 下，Agent 必须按照预定义 workflow / DAG 执行。
3. LLM 只能在指定节点内完成单步结构化生成。
4. LLM 输出不得直接控制全局流程、自由选择工具或绕过 workflow 跳转节点。
5. Runtime 必须校验 `next_node` 是否位于允许边集合。
6. 当前不支持完整 ReAct、模型自由工具选择、动态生成 workflow 和无边界循环。

## 6. 循环控制需求

`execution_control` 必须提供 workflow 级循环控制。

### 6.1 最大总步数

字段：

```text
RuntimePolicy.max_steps
```

含义：一次 task 最多允许进入多少个 workflow 节点。

达到上限后，如果当前节点尚未产生终止结果，runtime 必须停止继续调度并返回：

```text
status = loop_limit_exceeded
failure_code = max_steps_exceeded
```

### 6.2 节点访问次数

字段：

```text
RuntimePolicy.default_max_node_visits
NodeSpec.max_visits
```

含义：限制同一节点在一次 task 中最多进入多少次。

推荐 MVP 配置：

```text
default_max_node_visits = 3
generate_sql.max_visits = 2
validate_sql.max_visits = 5
repair_sql.max_visits = 3
execute_sql.max_visits = 3
```

### 6.3 边经过次数

字段：

```text
EdgeSpec.max_traversals
```

用于限制 workflow 回边。

推荐 MVP 配置：

```text
validate_sql -> repair_sql: 3
repair_sql -> validate_sql: 3
execute_sql -> repair_sql: 2
```

### 6.4 命名循环次数

字段：

```text
LoopPolicy.loop_name
LoopPolicy.max_attempts
```

MVP 至少支持：

```text
sql_repair_loop.max_attempts = 3
```

该配置覆盖 SQL 校验失败、SQL 执行失败后的自动修复循环。

### 6.5 重复错误检测

字段：

```text
RuntimePolicy.repeated_error_limit
```

MVP 判断维度：

```text
node_id + error_code
```

连续相同错误达到阈值后，runtime 返回：

```text
status = loop_limit_exceeded
failure_code = repeated_error_limit_exceeded
```

### 6.6 无进展检测

字段：

```text
RuntimePolicy.no_progress_limit
```

MVP 只做轻量检测：

1. `repair_sql` 后 `candidate_sql_hash` 没变化。
2. 相同工具、相同关键参数连续重复调用。

后续可扩展为 state fingerprint。

### 6.7 工具重复失败控制

Runtime 必须记录 task 范围内的工具调用历史。

工具调用指纹：

```text
node_id + tool_name + tool_version + normalized_args_hash
```

工具失败指纹：

```text
node_id + tool_name + tool_version + normalized_args_hash + error.reason
```

推荐 MVP 配置：

```text
same_tool_call_limit = 3
same_tool_failure_limit = 2
```

当同一工具、同一关键参数连续失败达到阈值后，runtime 必须拒绝继续调用并返回：

```text
status = loop_limit_exceeded
failure_code = repeated_tool_failure
```

不同关键参数的同名工具调用不视为重复调用。

## 7. 运行预算控制需求

MVP 不对 token 使用量设置硬性终止限制。

Token usage 如可获得，仅作为观测字段记录并返回给前端展示，不触发暂停、失败
或预算超限。

MVP 的硬预算只包含：

```text
max_model_calls
max_tool_calls
max_elapsed_ms
```

推荐配置：

```text
BudgetPolicy.max_model_calls = 6
BudgetPolicy.max_tool_calls = 10
BudgetPolicy.max_elapsed_ms = 120000
BudgetPolicy.warn_at_ratio = 0.8
TokenUsage.record_only = true
```

预算超限状态：

```text
status = budget_exceeded
```

具体 failure code：

```text
max_model_calls_exceeded
max_tool_calls_exceeded
max_elapsed_ms_exceeded
```

`token_usage` 应随 `RuntimeExecutionResult` 返回，供前端渲染本次分析资源消耗。

## 8. 退出条件控制需求

Runtime 必须统一判断 workflow 是否继续调度。

终止状态：

```text
completed
user_action_required
cannot_continue
failed
loop_limit_exceeded
budget_exceeded
timeout
guardrail_rejected
```

状态语义：

1. `completed`：workflow 正常完成。
2. `user_action_required`：需要用户补充信息，本轮停止但不是失败。
3. `cannot_continue`：当前业务条件下无法继续。
4. `failed`：系统异常或不可预期失败。
5. `loop_limit_exceeded`：循环保护触发。
6. `budget_exceeded`：模型调用次数、工具调用次数或运行耗时超限。
7. `timeout`：运行耗时达到硬上限，可作为 `budget_exceeded` 的专门状态。
8. `guardrail_rejected`：安全规则拒绝继续执行。

判断原则：

1. 已产生明确终止结果时，优先返回该终止结果。
2. 如果最后一步已经完成，不应被 `max_steps` 覆盖为循环超限。
3. 只有在准备继续调度下一节点前，才应用循环和预算拦截。
4. Runtime 必须返回统一 `RuntimeExecutionResult`。

## 9. 工具调用控制需求

工具调用必须受 `execution_control` 与 `tool_calling` 双层控制。

### 9.1 节点级工具白名单

每个 `NodeSpec` 必须声明：

```text
allowed_tools
```

需求：

1. 当前节点只能调用白名单中的工具。
2. 未声明工具调用必须拒绝。
3. `generate_sql` 不得直接执行 SQL。
4. `build_chart` 不得访问底层数据库。

### 9.2 统一工具入口

所有工具调用必须经过：

```text
ToolCallingRuntime.call(request)
```

业务节点不得绕过 `ToolCallingRuntime` 直接访问数据库、文件、Python 执行器或
外部系统。

### 9.3 权限与数据范围

每次工具调用必须携带 dataset scope。

Runtime 必须校验：

```text
tenant_id
user_id
session_id
allowed_dataset_ids
required_permissions
supported_dataset_types
```

Python Agent 不得扩大 Java 传入的访问范围。

### 9.4 参数与结果 schema

业务工具声明输入 schema，装配位置注入输出 schema：

```text
BusinessTool.input_args
ToolExecutionOptions.output_schema
```

调用前校验输入，调用后校验输出。`ToolCallResult` 只表示成功，校验或执行失败
必须抛出结构化 `ToolCallError`。

### 9.5 超时与失败

每个工具调用必须有 timeout。

推荐默认值：

```text
default_tool_timeout_ms = 30000
```

工具调用失败通过唯一异常类型 `ToolCallError` 表达，包含：

```text
reason：错误原因
message：错误内容
retryable：是否允许考虑重试
detail：错误细节
```

不要求工具状态码或错误码枚举。调用方捕获异常后调用
`after_tool_call(request, error)`，用 `reason` 保持重复失败检测，继续保留完整异常
payload。超时可标记为允许重试，但工具执行器不自动重试。

### 9.6 高风险工具

工具必须声明风险等级。

MVP 自动允许：

```text
read_only
compute_only
```

MVP 默认拒绝：

```text
external_side_effect
write_operation
dangerous
```

`requires_review = true` 的工具不得自动执行。

## 10. 推荐调度判断顺序

节点执行完成后：

```text
1. 读取 NodeExecutionResult
2. 判断是否已经进入终止状态
3. 校验 next_node 是否位于 AgentSpec 允许边
4. 检查 max_steps
5. 检查 node visit limit
6. 检查 edge traversal limit
7. 检查 named loop attempts
8. 检查 repeated error
9. 检查 no progress
10. 检查 max_model_calls / max_tool_calls / max_elapsed_ms
11. 允许调度下一节点
```

工具调用前：

```text
1. 校验当前节点是否允许调用该工具
2. 检查重复工具调用 / 重复失败限制
3. 检查 max_tool_calls
4. 校验 dataset scope / permission
5. 校验 input_schema
6. 执行 guardrails
7. 调用 ToolCallingRuntime.call
8. 校验 output_schema
9. 记录工具调用结果、耗时和失败原因
```

## 11. Checkpoint 与恢复要求

后续 checkpoint 必须包含 execution control 状态：

```text
step_count
node_visit_counts
edge_traversal_counts
loop_attempt_counts
model_call_count
tool_call_count
started_at
elapsed_ms
tool_call_history_summary
token_usage
```

Resume 时不得重置上述计数，否则会绕过 runtime 保护。

## 12. MVP 验收标准

1. Agent 能声明 `workflow_mode`、入口节点、终止节点、节点集合和允许边。
2. Runtime 能阻止未声明边的节点跳转。
3. Runtime 能限制最大总步数、节点访问次数和 SQL repair 次数。
4. Runtime 能识别重复错误并返回 `loop_limit_exceeded`。
5. Runtime 能识别同一工具、同一关键参数的重复失败。
6. Runtime 能限制模型调用次数、工具调用次数和运行耗时。
7. Token usage 能作为结果字段返回，但不会触发 task 终止。
8. Runtime 能统一返回终止状态和具体 failure code。
9. 节点只能调用 `allowed_tools` 中声明的工具。
10. 高风险或需要审核的工具不会被自动执行。

## 13. 非目标

MVP 不实现：

1. 完整 ReAct 执行模式。
2. 模型自由选择工具。
3. 动态生成 workflow。
4. token 使用量硬拦截。
5. 成本金额硬拦截。
6. 完整 state diff 无进展检测。
7. 复杂人工审核工作台。
