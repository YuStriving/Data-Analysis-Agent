# Proposal

## Why

当前 `validate_sql` 节点只进入节点状态，没有真正校验 `candidate_sql`，而 SQL 安全拦截主要依赖 query executor 前的工具层 guardrail。数据分析 Agent 需要在执行 SQL 前形成明确、可审计、可流转的业务校验结果，确保用户上传文件或授权数据源只在当前任务边界内被只读分析。

## What Changes

- 新增数据分析 SQL 校验能力规格，明确 `validate_sql -> execute_sql` 的节点职责和流转边界。
- 要求 `validate_sql` 基于当前任务的 `candidate_sql`、数据集上下文和 schema 上下文执行结构化校验。
- 要求 SQL 校验覆盖只读、单语句、授权 relation/table、授权字段和结果规模风险的 MVP 规则。
- 保留字段隐藏、敏感字段、人工审核等企业权限增强的扩展位，但不作为本次 MVP 必做内容。
- 要求工具层 query executor guardrail 继续作为执行前兜底，不替代业务节点校验。

## Capabilities

### New Capabilities

- `data-analysis/sql-validation`: 定义数据分析 Agent 在执行 SQL 前如何校验候选 SQL、输出结构化校验结果并路由到 `execute_sql`、修复或失败分支。

### Modified Capabilities

- 无。

## Impact

- 影响 Python Agent 编排层：`backend-agent/src/agent_backend/orchestration/data_analysis/nodes/validate_sql.py`、graph 节点流转和 `run_query`/`execute_sql` 命名一致性。
- 影响 Guardrails 能力：`backend-agent/src/agent_backend/capabilities/agent_runtime/guardrails/sql.py` 需要从 bool 结果演进为可审计的结构化校验结果。
- 影响测试：需要补充 SQL 校验节点、guardrails 规则、图流转和工具层兜底测试。
- 不引入新的外部依赖；如后续采用 AST 解析，应优先复用项目已规划的 SQL 解析方案并单独评估。
