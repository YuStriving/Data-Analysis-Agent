# data-analysis/sql-validation Specification

## Purpose

定义数据分析 Agent 在执行候选 SQL 前的业务校验能力，确保用户上传文件或授权数据源只在当前任务的数据边界内被只读、单语句、可控规模地分析，并为执行、修复、失败和审计提供结构化结果。

## Requirements

### Requirement: Validate SQL before execution
系统 SHALL 在执行候选 SQL 前完成显式 SQL 校验；校验输入 SHALL 来自当前任务的候选 SQL、数据集上下文、schema 上下文和访问边界，而不是依赖执行器失败后再发现问题。

#### Scenario: Valid SQL proceeds to execution
- **WHEN** 当前任务存在候选 SQL，且该 SQL 只读、单语句，并且只引用当前任务允许的数据 relation 和字段
- **THEN** 系统 SHALL 标记 SQL 校验通过，并允许流程进入 `execute_sql`

#### Scenario: Missing candidate SQL is rejected
- **WHEN** 当前任务没有候选 SQL 或候选 SQL 为空白
- **THEN** 系统 SHALL 标记 SQL 校验失败，并返回可审计的失败原因

### Requirement: Enforce read-only single-statement SQL
系统 SHALL 只允许用于分析的只读单语句 SQL。写入、变更结构、权限控制、事务控制、多语句或其他非只读语句 MUST 被拒绝。

#### Scenario: Write SQL is rejected
- **WHEN** 候选 SQL 包含 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE`、`CREATE` 或等价的非只读操作
- **THEN** 系统 SHALL 拒绝该 SQL，并将风险等级标记为 high

#### Scenario: Multiple statements are rejected
- **WHEN** 候选 SQL 包含多条可执行语句
- **THEN** 系统 SHALL 拒绝该 SQL，并返回多语句校验失败原因

#### Scenario: Select query is allowed
- **WHEN** 候选 SQL 是单条 `SELECT` 查询或安全的 `WITH ... SELECT` 查询
- **THEN** 系统 SHALL 继续执行数据边界和结果规模校验

### Requirement: Enforce task data boundary
系统 SHALL 校验候选 SQL 引用的 relation、table 和字段均来自当前任务上下文中允许的数据集 schema。用户上传的文件数据和数据库数据 MUST 统一按当前任务授权的逻辑 relation 边界处理。

#### Scenario: Current file relation is allowed
- **WHEN** 当前任务基于用户上传的 CSV、XLS 或 XLSX 文件构建了 `relation_1`，且候选 SQL 只引用该 relation 及其 schema 中的字段
- **THEN** 系统 SHALL 认为该 SQL 满足数据边界要求

#### Scenario: Unknown relation is rejected
- **WHEN** 候选 SQL 引用了当前任务 schema 上下文中不存在的 relation 或 table
- **THEN** 系统 SHALL 拒绝该 SQL，并返回未授权 relation 的校验失败原因

#### Scenario: Unknown field is rejected
- **WHEN** 候选 SQL 引用了当前任务 schema 上下文中不存在的字段
- **THEN** 系统 SHALL 拒绝该 SQL，并返回未授权字段的校验失败原因

### Requirement: Control result scale risk
系统 SHALL 在 SQL 校验阶段识别明显的结果规模风险。明细查询 MUST 有可控的返回规模；聚合查询可以不强制 `LIMIT`，但仍 MUST 受执行阶段最大行数约束保护。

#### Scenario: Detail query without limit is warned or constrained
- **WHEN** 候选 SQL 是明细查询且没有显式限制返回规模
- **THEN** 系统 SHALL 在校验结果中记录规模风险，或要求后续执行阶段应用最大行数约束

#### Scenario: Aggregate query is not rejected only for missing limit
- **WHEN** 候选 SQL 是聚合查询，且查询结果规模天然受聚合维度控制
- **THEN** 系统 MUST NOT 仅因为缺少 `LIMIT` 而拒绝该 SQL

### Requirement: Produce structured validation result
系统 SHALL 为每次 SQL 校验输出结构化结果，至少包含是否通过、规则代码、可读消息、风险等级、是否可修复、引用的 relation/table、引用的字段和校验版本。

#### Scenario: Rejected SQL provides repair context
- **WHEN** 候选 SQL 因可修复问题被拒绝
- **THEN** 系统 SHALL 在校验结果中标记可修复，并提供足够的失败原因供后续 SQL 修复流程使用

#### Scenario: Forbidden access is not repairable
- **WHEN** 候选 SQL 访问当前任务未授权的数据集、relation、table 或字段
- **THEN** 系统 SHALL 将该失败标记为不可通过自动修复绕过的数据边界错误

#### Scenario: Passed SQL is retained for execution
- **WHEN** SQL 校验通过
- **THEN** 系统 SHALL 保留已校验 SQL，供 `execute_sql` 使用

### Requirement: Preserve extension points for enterprise policies
系统 SHALL 为字段隐藏、敏感字段、人工审核和策略告警预留扩展位，但这些能力 MUST NOT 成为本次 MVP 的必需校验规则。

#### Scenario: No masked column policy is configured
- **WHEN** 当前任务没有配置字段隐藏或敏感字段策略
- **THEN** 系统 SHALL 仅执行基础数据边界、安全和规模校验

#### Scenario: Policy metadata is present
- **WHEN** 当前任务上下文提供字段策略、敏感字段或人工审核元数据
- **THEN** 系统 SHALL 能在校验结果中承载策略告警或拒绝原因，而不改变基础校验结果结构

### Requirement: Keep execution guardrail as safety backstop
系统 SHALL 在 SQL 执行工具前继续保留执行层 guardrail。业务 SQL 校验通过并不 SHALL 取消执行层的最终安全兜底。

#### Scenario: Execution receives unsafe SQL
- **WHEN** 执行层收到包含危险操作的 SQL，即使该 SQL 绕过或未经过业务校验
- **THEN** 执行层 guardrail SHALL 拒绝执行该 SQL
