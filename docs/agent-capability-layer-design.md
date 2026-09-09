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

负责工具注册、工具参数校验、工具调用分发和工具结果规范化。

核心信息：

1. 工具名称和描述
2. 输入参数 schema
3. 输出结果 schema
4. 工具所属 Agent
5. 所需权限和数据源类型
6. 超时配置
7. 重试配置
8. 是否需要人工审核

首期工具需要覆盖：

1. MySQL schema reader
2. MySQL query executor
3. CSV schema reader
4. CSV query executor
5. Excel schema reader
6. Excel query executor
7. chart spec builder

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
