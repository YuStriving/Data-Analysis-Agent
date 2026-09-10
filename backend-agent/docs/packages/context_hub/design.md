# Python Context Hub 设计文档

## 1. 背景

`context_hub` 是 `agent_runtime` 中负责上下文构造的模块。

本模块沉淀当前阶段围绕 `context` 的设计讨论，用于指导后续编码。本文档只描述设计、职责边界、MVP 策略和后续演进方向，不要求一次性完成所有扩展能力。

当前产品优先面向 C 端用户，不按复杂 B 端多租户模型设计。因此 MVP 阶段保留 `tenant_id` 作为底层兼容字段，但不围绕租户做复杂策略。上下文隔离重点按以下顺序处理：

```text
user_id
session_id
dataset_id
```

## 2. 核心定位

`context_hub` 不负责存储所有记忆，也不负责渲染 Prompt，更不负责执行 SQL。

它只回答一个问题：

```text
当前 Agent 的当前节点，
在当前用户、当前 session、当前 dataset 的边界内，
应该看到哪些信息？
```

可以把 `context_hub` 理解成 Agent 的资料包生成器：

```text
ContextSource + ContextPolicy -> ContextBundle
```

其中：

1. `ContextSource` 是原始资料来源。
2. `ContextPolicy` 是当前节点能看什么、看多少的规则。
3. `ContextBundle` 是最终整理出来的小抄。
4. `ContextBuilder` 是负责组装小抄的执行器。

## 3. 设计目标

MVP 阶段目标：

1. 明确 session 级上下文隔离。
2. 明确当前可用数据集和当前选中数据集。
3. 为 SQL 生成、SQL 修复、结果解释、图表生成提供结构化上下文。
4. 通过 policy 白名单控制不同节点可见的上下文 section。
5. 避免将完整聊天历史、完整查询结果、未授权数据集、跨 session 文件注入给 Agent。
6. 记录 context policy version 和 bundle version，便于后续回放、评估和排查。

非目标：

1. 不在 MVP 实现复杂租户级策略。
2. 不在 MVP 实现 embedding 召回。
3. 不在 MVP 实现复杂 token 级智能压缩。
4. 不在 MVP 实现跨 session 自动复用临时文件。
5. 不在 MVP 实现多 Agent 动态策略选择。

## 4. ContextBundle

`ContextBundle` 是最终交给 prompt 层、graph node 或 tool node 使用的结构化上下文包。

它不是一段 Prompt 字符串。Prompt 层应该基于 `ContextBundle` 渲染具体模板。

MVP 推荐一级结构：

```text
identity
request
dataset
schema
conversation
previous_turn
repair
execution_result
chart
runtime
meta
```

### 4.1 identity

描述本次任务的身份边界。

字段建议：

```text
task_id
trace_id
tenant_id
user_id
session_id
```

说明：

1. `tenant_id` MVP 保留但不做复杂策略。
2. `session_id` 必须代表对话窗口，不能用 `task_id` 代替。
3. 一个 `session_id` 下可以有多个 `task_id`。

### 4.2 request

描述用户本轮输入和任务识别结果。

字段建议：

```text
question
task_type
intent
```

其中 `task_type` 可以来自轻量分类器，例如：

```text
trend_analysis
comparison_analysis
distribution_analysis
unknown
resume_recovery
```

### 4.3 dataset

描述当前 session 下的数据集边界。

字段建议：

```text
available_dataset_ids
selected_dataset_id
last_used_dataset_id
```

数据集选择规则：

```text
本轮显式选择的数据集
-> 当前 session 最近一次使用的数据集
-> 缺少数据集，要求用户选择或上传
```

约束：

1. Python Agent 只能使用 Java 或 dataset resolver 下发的可用数据集。
2. Agent 不允许自行扩大 dataset 范围。
3. 不允许跨 session 自动复用文件暂存区中的数据。

### 4.4 schema

描述当前选中数据集的 schema 摘要。

字段建议：

```text
schema_summary
semantic_schema_summary
metric_mapping
time_field_hints
field_summary
truncated
```

MVP 采用 v2 上下文注入策略，默认比基础 schema 更丰富，应包含：

1. 表名。
2. 字段名。
3. 字段类型。
4. 字段业务含义或注释。
5. 常见指标映射，例如 `销售额 -> amount`。
6. 时间字段提示，例如 `趋势分析优先使用 order_time`。

示例：

```text
orders:
- order_time datetime，订单时间，适合趋势分析
- amount decimal，销售额字段
- region varchar，地区字段

指标映射：
- 销售额 -> orders.amount
- 地区 -> orders.region

时间字段：
- 订单时间 -> orders.order_time
```

### 4.5 conversation

描述当前 session 的多轮对话摘要。

字段建议：

```text
conversation_summary
confirmed_facts
unresolved_questions
```

约束：

1. MVP 不注入完整聊天历史。
2. 只注入摘要、已确认事实和必要的未决问题。
3. 摘要长度受 `ContextPolicy` 限制。

### 4.6 previous_turn

描述上一轮任务的关键上下文。

字段建议：

```text
last_question
last_sql
last_result_summary
last_chart_summary
last_selected_dataset_id
```

用途：

1. 支持用户说“继续”、“那华南呢”、“换成按月份”这类追问。
2. 帮助 SQL 生成节点承接上一轮意图。
3. 帮助图表节点复用或调整上一轮图表表达。

MVP 默认最多注入上一轮。后续可扩展为最近 N 轮或按相关性召回。

### 4.7 repair

描述 SQL 校验或执行失败后的修复上下文。

字段建议：

```text
failed_sql
error_message
failure_stage
retry_count
max_retry_count
avoid_errors
```

用途：

1. 告诉 SQL 修复节点上一条 SQL 为什么失败。
2. 防止模型重复使用不存在的表或字段。
3. 控制自动修复次数。

约束：

1. 最大自动修复次数 MVP 为 3。
2. 每次修复必须携带失败 SQL、错误信息、失败阶段、schema 和 retry count。

### 4.8 execution_result

描述 SQL 执行后的结果摘要。

字段建议：

```text
executed_sql
result_summary
table_preview
truncated
max_rows
```

约束：

1. 默认不把完整查询结果放入 context。
2. 只允许受限 preview、摘要和必要引用进入上下文。
3. 如果结果超过最大行数，需要标记 `truncated = true`。

### 4.9 chart

描述图表相关上下文。

字段建议：

```text
chart_summary
last_chart_spec
target_chart_types
```

MVP 支持图表类型：

```text
bar
line
pie
table
```

### 4.10 runtime

描述当前运行时和节点状态。

字段建议：

```text
agent_name
agent_version
node_name
node_id
policy_name
policy_version
bundle_version
```

### 4.11 meta

描述本次上下文构造的元信息。

字段建议：

```text
built_at
included_sections
missing_sections
truncated_sections
warnings
```

用途：

1. 方便 observability 记录 `context_built` 事件。
2. 方便后续复盘 SQL 生成质量。
3. 方便判断某次失败是否由上下文缺失或截断导致。

## 5. ContextSource

`ContextSource` 是构建 `ContextBundle` 的原材料集合。

MVP 推荐分为 7 类：

```text
TaskSource
DatasetSource
SchemaSource
ConversationSource
PreviousTurnSource
RepairSource
RuntimeSource
```

### 5.1 TaskSource

来源：Java 任务请求。

字段建议：

```text
task_id
trace_id
tenant_id
user_id
session_id
question
```

要求：

1. `session_id` 必须由 Java 明确传入。
2. Python 不应使用 `task_id` 推导 `session_id`。

### 5.2 DatasetSource

来源：Java 或 dataset resolver。

字段建议：

```text
available_dataset_ids
selected_dataset_id
last_used_dataset_id
```

要求：

1. 只包含当前用户、当前 session 可用的数据集。
2. 数据集选择逻辑应先于 context build 完成。
3. 如果没有可用数据集，builder 应返回缺少上下文状态。

### 5.3 SchemaSource

来源：schema reader。

字段建议：

```text
dataset_id
datasource_type
schema_summary
semantic_schema_summary
metric_mapping
time_field_hints
field_summary
```

MVP 由 Python 实时读取 MySQL、CSV、XLS、XLSX 的 schema。schema 缓存后续再做。

### 5.4 ConversationSource

来源：memory。

字段建议：

```text
conversation_summary
confirmed_facts
unresolved_questions
```

要求：

1. 当前阶段按 `session_id` 隔离。
2. 不自动读取其他 session 的历史。

### 5.5 PreviousTurnSource

来源：memory 或 checkpoint。

字段建议：

```text
last_question
last_sql
last_result_summary
last_chart_summary
last_selected_dataset_id
```

### 5.6 RepairSource

来源：SQL guardrails 或 SQL executor 的失败链路。

字段建议：

```text
failed_sql
error_message
failure_stage
retry_count
max_retry_count
avoid_errors
```

### 5.7 RuntimeSource

来源：lifecycle 或 graph runtime。

字段建议：

```text
agent_name
agent_version
node_name
node_id
task_type
policy_version
```

## 6. ContextPolicy

`ContextPolicy` 是当前 Agent 当前节点可见上下文的规则。

推荐设计颗粒度：

```text
agent_name + node_name
```

也就是说，不只定义 `data_analysis_agent` 能看什么，而是定义：

```text
data_analysis_agent.generate_sql 能看什么
data_analysis_agent.repair_sql 能看什么
data_analysis_agent.interpret_result 能看什么
data_analysis_agent.build_chart 能看什么
```

### 6.1 MVP 字段

字段建议：

```text
policy_name
policy_version
agent_name
node_name
allowed_sections
required_sections
max_schema_chars
max_conversation_chars
max_previous_turns
max_repair_items
include_raw_rows
```

### 6.2 policy_version

`policy_version` 用于记录本次上下文注入使用的规则版本。

它不是 SQL 质量判断器，而是用于：

1. 回放。
2. 灰度。
3. 质量对比。
4. 排查某次 SQL 失败是否与上下文策略有关。

MVP 决策：

```text
直接使用 v2 上下文注入策略。
```

后续 TODO：

```text
引入 PolicySelector 或策略选择 Agent，
根据 SQL 质量、任务类型、数据源类型、用户反馈等信息，
动态选择不同 ContextPolicy。
```

### 6.3 v2 策略含义

v2 相比基础策略，默认注入更丰富的 schema 和语义提示：

```text
字段名
字段类型
字段业务含义
指标映射
时间字段提示
上一轮 SQL 和结果摘要
必要的 SQL 修复上下文
```

典型目标：

```text
减少字段名猜错
减少表名猜错
提升趋势、对比、分组统计类问题的 SQL 语义命中率
提升多轮追问承接能力
```

## 7. MVP Policy 建议

### 7.1 generate_sql_v2

用途：生成只读 SQL。

允许 section：

```text
identity
request
dataset
schema
conversation
previous_turn
repair
runtime
meta
```

必需 section：

```text
request
dataset
schema
```

限制：

```text
max_schema_chars = 4000
max_conversation_chars = 2000
max_previous_turns = 1
max_repair_items = 3
include_raw_rows = false
```

### 7.2 repair_sql_v2

用途：修复 SQL。

允许 section：

```text
identity
request
dataset
schema
previous_turn
repair
runtime
meta
```

必需 section：

```text
request
dataset
schema
repair
```

限制：

```text
max_schema_chars = 4000
max_repair_items = 3
include_raw_rows = false
```

### 7.3 interpret_result_v2

用途：解释查询结果。

允许 section：

```text
identity
request
dataset
conversation
previous_turn
execution_result
runtime
meta
```

必需 section：

```text
request
execution_result
```

限制：

```text
max_conversation_chars = 2000
include_raw_rows = false
```

### 7.4 build_chart_v2

用途：生成通用 chart spec。

允许 section：

```text
identity
request
dataset
previous_turn
execution_result
chart
runtime
meta
```

必需 section：

```text
request
execution_result
```

限制：

```text
include_raw_rows = false
```

## 8. ContextBuilder

`ContextBuilder` 是纯组装器。

职责：

```text
1. 接收 ContextSource 和 ContextPolicy。
2. 校验 required_sections 是否满足。
3. 按 allowed_sections 白名单选择内容。
4. 按 policy 限制裁剪 schema、conversation、previous_turn、repair 等内容。
5. 填充 runtime 和 meta 信息。
6. 输出 ContextBundle 或 missing_required_context 结果。
```

不负责：

```text
1. 不直接查 Redis。
2. 不直接查 MongoDB。
3. 不直接连 MySQL 或文件读取 schema。
4. 不判断用户真实权限。
5. 不执行 SQL。
6. 不渲染 Prompt。
7. 不调用大模型。
8. 不决定当前使用哪个 Agent。
```

### 8.1 推荐函数形态

```python
class ContextBuilder:
    def build(
        self,
        source: ContextSource,
        policy: ContextPolicy,
    ) -> ContextBuildResult:
        ...
```

### 8.2 推荐返回结构

```python
class ContextBuildResult(BaseModel):
    status: Literal["ok", "missing_required_context"]
    bundle: ContextBundle | None
    missing_sections: list[str] = []
    warnings: list[str] = []
```

当缺少必需上下文时，例如用户未上传或选择数据集：

```json
{
  "status": "missing_required_context",
  "bundle": null,
  "missing_sections": ["dataset", "schema"],
  "warnings": []
}
```

lifecycle 看到该状态后，不应继续进入 SQL 生成节点，而应返回明确的用户提示。

## 9. 构建流程

推荐流程：

```text
receive_task
-> resolve_dataset
-> load_schema
-> load_session_memory
-> load_previous_turn
-> collect_repair_context if needed
-> resolve_context_policy
-> build_context_bundle
-> emit context_built event
-> render_prompt
-> run_node
```

MVP 中 `resolve_context_policy` 默认返回对应节点的 v2 policy。

## 10. 缺上下文处理

`ContextBuilder` 必须显式处理缺失上下文，不能用空字段伪装可用上下文。

例如：

```text
用户问：帮我分析销售额
但当前 session 没有 selected_dataset_id，也没有 schema
```

此时应返回：

```text
status = missing_required_context
missing_sections = ["dataset", "schema"]
```

推荐由 lifecycle 转换为用户可理解的提示：

```text
请先上传或选择一个数据集。
```

这样可以减少模型胡编表名、字段名和 SQL 的风险。

## 11. 观测与评估

每次 context 构建完成后，应至少记录：

```text
task_id
trace_id
user_id
session_id
agent_name
node_name
policy_name
policy_version
bundle_version
included_sections
missing_sections
truncated_sections
```

这些信息用于后续分析：

```text
SQL 校验失败率
SQL 执行失败率
字段不存在错误率
表不存在错误率
多轮追问接续失败率
上下文缺失导致的中断次数
schema 截断后的 SQL 失败率
```

## 12. 后续 TODO

MVP 之后再考虑：

1. 引入 `PolicySelector` 或策略选择 Agent。
2. 根据 SQL 质量自动选择不同 context policy。
3. 根据任务类型选择更精细的 schema 注入策略。
4. 根据数据源类型选择不同 schema 摘要策略。
5. 支持最近 N 轮上下文或相关性召回。
6. 支持 token 级预算和压缩。
7. 支持字段级上下文裁剪。
8. 支持 schema 缓存。
9. 支持基于评测集对比不同 policy version 的效果。

其中策略选择可以后续设计为：

```text
SQL 执行结果 / 用户反馈 / 任务类型 / 数据源类型
-> PolicySelector 或策略选择 Agent
-> 选择 ContextPolicy
-> ContextBuilder 重新构造 ContextBundle
```

MVP 不实现该闭环，只保留扩展点。
