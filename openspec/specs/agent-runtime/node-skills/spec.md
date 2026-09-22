# agent-runtime/node-skills Specification

## Purpose
Node Skills 为 Agent Runtime 提供节点级 LLM 操作手册，使 system prompt 与节点任务说明解耦，并让 workflow 能按显式节点绑定加载当前节点所需的 LLM 能力。

## Requirements

### Requirement: Node Skill Definition

系统 MUST 支持将节点级 LLM 内容定义为 Node Skill 文件，并记录稳定的 `skill_id`、`agent_id`、`nodes`、`version`、`status`、`required_context`、`optional_context`、`output_contract`、`response_format` 与正文内容。

#### Scenario: Load node skill definition
- **WHEN** workflow 需要执行一个已显式绑定的 Node Skill 文件
- **THEN** 系统 MUST 读取该 Skill 的元数据、版本、输出契约和正文内容用于本次 LLM 调用

#### Scenario: Reject incomplete node skill metadata
- **WHEN** Node Skill 缺少 `skill_id`、`agent_id`、`nodes`、`version`、`status`、`output_contract` 或 `response_format`
- **THEN** 系统 MUST 拒绝加载该 Skill，并返回可定位到具体 Skill 文件的工程错误

### Requirement: Explicit Node Skill Binding

系统 MUST 使用显式节点绑定或临时静态映射确定当前节点使用的 Node Skill。本变更不要求实现 Skill 注册、发现、搜索或模型自主选择能力。

#### Scenario: Use explicitly bound skill
- **WHEN** workflow 进入 `data_analysis_agent.generate_sql` 节点
- **THEN** 系统 MUST 使用该节点显式绑定的 `generate_sql` Node Skill

#### Scenario: Reject missing node skill
- **WHEN** 需要 LLM 调用的节点没有显式绑定 Node Skill
- **THEN** 系统 MUST 在模型调用前失败，并返回缺失 Skill 的工程错误

### Requirement: Context Requirements

系统 MUST 使用 Node Skill 声明的 `required_context` 与 `optional_context` 校验当前 `ContextBundle`。缺少必需上下文时 MUST 在模型调用前失败，缺少可选上下文时 MUST 允许继续并以明确空值表达缺失。

#### Scenario: Required context is available
- **WHEN** Node Skill 要求 `request`、`dataset`、`schema` 与 `access`，且当前 `ContextBundle` 均已提供
- **THEN** 系统 MUST 允许继续组装 LLM 消息

#### Scenario: Required context is missing
- **WHEN** Node Skill 要求 `schema`，但当前 `ContextBundle` 不包含 schema section
- **THEN** 系统 MUST 不调用模型，并返回缺失上下文的工程错误

#### Scenario: Optional context is missing
- **WHEN** Node Skill 声明 `conversation` 为可选上下文但当前任务未提供该 section
- **THEN** 系统 MUST 允许继续，并在发给模型的节点消息中明确表达该上下文为空或不可用

### Requirement: Output Contract Binding

Node Skill MUST 通过稳定的 `output_contract` 标识声明模型输出格式。系统 MUST 使用该标识选择对应的运行时输出校验器，并在模型输出不符合契约时拒绝写入业务状态。

#### Scenario: Validate model output by contract id
- **WHEN** `generate_sql` Skill 声明 `output_contract: generate_sql_result_v1`
- **THEN** 系统 MUST 使用 `generate_sql_result_v1` 对应的运行时校验逻辑验证模型输出

#### Scenario: Reject invalid model output
- **WHEN** 模型输出无法通过 Node Skill 声明的 `output_contract` 校验
- **THEN** 系统 MUST 将本次节点执行标记为模型输出无效，并不得把该输出写入后续节点依赖的业务字段

### Requirement: Skill Reasoning and Few-shot Guidance

Node Skill 正文 MUST 提供节点级内部推理流程，并 SHOULD 提供 few-shot 示例。内部推理流程 MUST 明确不输出完整推理链，最终响应 MUST 只输出符合 `output_contract` 的 JSON。

#### Scenario: Skill defines internal reasoning checklist
- **WHEN** Node Skill 被加载用于 LLM 调用
- **THEN** Skill 正文 MUST 包含节点内检查顺序，指导模型依次完成意图识别、上下文证据匹配、权限或结果约束检查、失败分支判断和最终 JSON 输出

#### Scenario: Skill suppresses full chain-of-thought output
- **WHEN** 模型根据 Node Skill 生成响应
- **THEN** 模型 MUST NOT 输出完整逐步推理链，只能在 contract 允许的字段中输出简短依据、假设、限制或警告

#### Scenario: Skill examples match output contract
- **WHEN** Node Skill 提供 few-shot 示例
- **THEN** 示例的期望输出 SHOULD 使用与 `output_contract` 一致的字段、状态枚举和失败分支表达

### Requirement: System Prompt Separation

系统 MUST 将 system prompt 与 Node Skill 分离管理。system prompt MUST 进入 LLM 的 `system` message，Node Skill 正文与当前结构化上下文 MUST 进入当前节点的任务消息。

#### Scenario: Compose messages for skill execution
- **WHEN** workflow 执行一个需要 LLM 的节点
- **THEN** 系统 MUST 组装至少一条 `system` message 和一条包含 Node Skill 与当前上下文的节点任务 message

#### Scenario: Preserve replay metadata
- **WHEN** 系统完成一次 Node Skill LLM 调用
- **THEN** 系统 MUST 记录 system prompt 版本或 hash，以及 Node Skill 的 `skill_id`、版本和渲染 hash，以支持回放、审计和评测

### Requirement: Data Analysis Skill Migration

系统 MUST 将 `generate_sql`、`repair_sql`、`interpret_result` 与 `build_chart` 的节点级 LLM 内容表达为 Node Skill。迁移后这些 Skill MUST 保留原有节点边界、安全规则、输入上下文和 JSON 输出契约。

#### Scenario: Generate SQL skill preserves SQL boundaries
- **WHEN** `generate_sql` Skill 被加载
- **THEN** 该 Skill MUST 明确只负责生成候选只读 SQL，并保留不得执行 SQL、不得解释结果、不得生成图表、不得扩大权限的规则

#### Scenario: Repair SQL skill preserves repair boundaries
- **WHEN** `repair_sql` Skill 被加载
- **THEN** 该 Skill MUST 明确只负责修复候选 SQL，并保留不得绕过校验、不得改变原始分析意图、不得扩大权限的规则

#### Scenario: Interpret result skill preserves interpretation boundaries
- **WHEN** `interpret_result` Skill 被加载
- **THEN** 该 Skill MUST 明确只负责基于已执行 SQL 与查询结果解释用户问题，并保留不得编造结果、不得输出新 SQL 的规则

#### Scenario: Build chart skill preserves chart boundaries
- **WHEN** `build_chart` Skill 被加载
- **THEN** 该 Skill MUST 明确只负责生成前端无关 chart spec，并保留不得生成具体前端库配置、不得编造不存在字段的规则
