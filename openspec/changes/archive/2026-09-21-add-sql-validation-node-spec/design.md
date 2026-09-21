# Design

## Context

当前 Python Agent 的数据分析图已经包含 `generate_sql -> validate_sql -> run_query`，但 `validate_sql` 和 `run_query` 仍是占位节点。真实 SQL 禁写校验目前在工具调用运行时中作为 query executor 前置 guardrail 存在，返回值也还是 bool 级别，无法为前端展示、审计、SQL 修复和节点流转提供结构化原因。

项目目标是分析用户上传的 CSV/XLS/XLSX 文件或用户授权连接的数据源。MVP 不把字段隐藏、敏感字段识别和列级权限策略作为主线；核心是保证 Agent 生成的 SQL 只能在当前任务绑定的数据边界内只读执行。

## Goals / Non-Goals

**Goals:**

- 将 `validate_sql` 设计为执行前的业务校验节点，输出结构化 `sql_validation`。
- 将通过后的执行节点统一命名为 `execute_sql`，消除 `run_query` 与工具 `allowed_nodes=["execute_sql"]` 的不一致。
- 保留工具层 guardrail 作为最后兜底，防止未来绕过业务节点直接调用执行工具。
- 明确 MVP 规则：只读、单语句、当前任务 relation/table、当前 schema 字段、结果规模风险和审计字段。
- 保留企业策略扩展位，但不在本次实现字段脱敏、敏感字段策略引擎或人工审核。

**Non-Goals:**

- 不实现复杂 SQL 语义正确性评审，例如 SQL 是否完整回答用户问题。
- 不实现完整成本估算、查询计划分析或数据库 optimizer 集成。
- 不引入多 SQL 计划、自动人工审核中断或完整 `repair_sql` 节点实现。
- 不把用户上传文件场景强行套入字段隐藏策略。

## Decisions

### Decision 1: `validate_sql` 负责业务准入，工具层 guardrail 负责执行兜底

`validate_sql` 在 graph 中读取候选 SQL 和任务上下文，输出结构化校验结果并决定后续流转。工具层 guardrail 继续在 `mysql.query_executor` 和 `relation.query_executor` 前执行安全检查。

选择原因：

- 业务节点可以生成前端、审计、修复流程需要的规则代码和可读原因。
- 工具层 guardrail 可以防止未来新增路径绕过业务节点。
- 两层职责清晰，避免把工具运行时变成业务流程决策器。

替代方案：

- 只依赖工具层 guardrail：实现最少，但失败发生太晚，也缺少节点级审计和 repair 上下文。
- 只保留 `validate_sql`：业务体验清楚，但执行工具被直接调用时缺少最终安全兜底。

### Decision 2: 统一执行节点命名为 `execute_sql`

后续图节点从 `run_query` 统一为 `execute_sql`。现有工具定义已经使用 `allowed_nodes=["execute_sql"]`，文档中也多次采用 `execute_sql` 表示 SQL 执行动作。

选择原因：

- `execute_sql` 更接近工具权限模型和执行语义。
- 避免后续实现 `run_query` 调用工具时被 `TOOL_NODE_NOT_ALLOWED` 拦截。
- 减少文档、测试和代码之间的长期命名分裂。

替代方案：

- 保留 `run_query` 并修改工具 `allowed_nodes`：可行，但会扩大权限命名口径，也需要同步更多文档。

### Decision 3: MVP 校验以数据边界和 SQL 安全为核心

MVP 校验规则聚焦：

- 候选 SQL 必须存在。
- 只允许单条只读 SQL。
- 允许单条 `SELECT`，后续可支持安全的 `WITH ... SELECT`。
- 拒绝 DDL、DML、权限、事务和多语句。
- 引用 relation/table 必须来自当前任务 schema 上下文。
- 引用字段必须来自当前任务 schema 上下文。
- 明细查询必须具备可控返回规模，或依赖执行阶段 `max_rows` 兜底。

字段隐藏、敏感字段和人工审核以 metadata 和结果字段预留，不作为第一版阻断规则。

选择原因：

- 用户上传文件场景中，数据本身来自用户，复杂字段隐藏不是 MVP 主要风险。
- 数据库场景仍需要数据集和 schema 边界，避免 Agent 查询未授权 relation/table。
- 规则足够支撑安全执行和审计，又不会把校验节点做成数据治理平台。

### Decision 4: 结构化校验结果由 guardrails 能力提供，节点负责写入状态和流转

建议将 guardrails 从 `validate_sql(sql) -> bool` 演进为结构化结果，例如：

```json
{
  "passed": false,
  "rule_code": "SQL_FORBIDDEN_TOKEN",
  "message": "SQL contains forbidden token: DELETE",
  "risk_level": "high",
  "recoverable": false,
  "referenced_relations": [],
  "referenced_fields": [],
  "validation_version": "sql_validation_v1"
}
```

`validate_sql` 节点将该结果写入 `state["analysis"]["sql_validation"]`。通过时写入 `state["analysis"]["validated_sql"]` 并路由到 `execute_sql`；失败时根据 `recoverable` 和错误类型路由到未来 `repair_sql` 或当前 `fail_task`。

选择原因：

- guardrails 保持规则职责。
- 编排节点保持状态变更和流程职责。
- 测试可以分别覆盖规则和节点流转。

## Risks / Trade-offs

- [Risk] 不引入 AST 解析时，表字段识别可能不完整。 -> Mitigation: MVP 可先支持常见 SELECT 结构，并用测试锁定已支持范围；后续再评估 sqlglot 等解析方案。
- [Risk] 字段策略只预留扩展位，企业敏感字段场景短期保护不足。 -> Mitigation: 依赖 Java 端数据集授权和 schema 裁剪作为上游边界，本次不承诺列级策略。
- [Risk] `run_query` 改名为 `execute_sql` 会影响现有测试和文档。 -> Mitigation: 作为同一变更中的命名统一任务处理，测试覆盖 graph 节点顺序。
- [Risk] 聚合查询缺少 `LIMIT` 不被拒绝，极端聚合维度可能仍产生大结果。 -> Mitigation: 执行阶段必须继续使用 `max_rows` 截断或限制返回规模。

## Migration Plan

1. 新增结构化 SQL 校验结果模型和 guardrails 规则返回。
2. 改造 `validate_sql` 节点，读取候选 SQL 和上下文，写入 `sql_validation`。
3. 将 graph 中 `run_query` 统一迁移为 `execute_sql`，同步工具 allowed node、导出和测试命名。
4. 保留工具层 guardrail，并让其使用相同或兼容的基础安全规则。
5. 补齐单元测试后再进入实现合并。

回滚策略：如果节点级校验导致主链路不可用，可临时恢复 graph 到原占位流转并保留工具层 guardrail 兜底；结构化结果模型不应影响执行工具的原有安全拒绝能力。
