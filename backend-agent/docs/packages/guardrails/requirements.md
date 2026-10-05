# Python Guardrails 模块需求

## 1. 模块定位

`guardrails` 负责在 Agent 执行过程中实施安全和稳定性约束，首要目标是阻止危险 SQL 和越权操作。

## 2. 当前代码现状

当前实现 `validate_sql_detailed` 检查空语句、多语句、禁止关键字、只读
`SELECT`/`WITH`、可识别的关系及字段范围，并对无聚合且无 `LIMIT` 的查询给出
规模风险警告。实现使用轻量文本处理，不是 AST 级校验；关系/字段识别有语法覆盖限制。
业务节点传入 Schema 关系及 SQL policy metadata，详见 [接口文档](api.md) 与
`src/agent_backend/capabilities/agent_runtime/guardrails/sql.py`。

## 3. 核心职责

1. SQL 只读校验
2. 未授权访问拦截
3. 多语句拦截
4. 结果规模约束
5. 高风险任务标记

## 4. MVP 功能需求

1. 维护只读 SQL 校验结果及稳定规则码。
2. 把范围校验结果交由调用节点和数据访问策略共同处理。
3. 明确记录轻量文本识别的限制，不宣称 AST、敏感字段策略或查询执行配额已在本模块实现。

## 5. 验收标准

1. 非法 SQL 能被拦截
2. 风险规则命中后能返回明确原因
3. 风险输出可被 `audit` 模块记录
