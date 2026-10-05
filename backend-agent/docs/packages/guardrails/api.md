# Python Guardrails 接口文档

当前实现位于 `src/agent_backend/capabilities/agent_runtime/guardrails/sql.py`。
`validate_sql` 是 `validate_sql_detailed` 的布尔包装；SQL 规则由 Python 实现，
并非 SQL AST 解析器，不能单独替代 Java 授权、数据源只读账号或查询执行限制。

## 1. 当前公开函数

### `validate_sql(sql: str, *, allowed_relations: dict[str, Any] | None = None) -> bool`

返回详细校验结果中的 `passed`。

### `validate_sql_detailed(sql: str, *, allowed_relations: dict[str, Any] | None = None, policy_metadata: dict[str, Any] | None = None) -> SqlValidationResult`

结果包括 `passed`、`rule_code`、`message`、`risk_level`、`recoverable`、引用的关系和字段、警告、策略元信息及校验版本。

当前检查空 SQL、多语句、禁止关键字、`SELECT`/`WITH` 起始、可识别的未授权关系/字段；无聚合且无 `LIMIT` 的查询会产生结果规模风险警告。关系和字段识别基于轻量文本处理，不能视作完整 SQL 语法解析。

分析图中的调用位置见 [validate_sql 节点](../../../src/agent_backend/orchestration/data_analysis/nodes/validate_sql.py)，行为用例见 `tests/unit/test_data_analysis_graph.py` 和 `tests/unit/test_data_analysis_context_nodes.py`。
