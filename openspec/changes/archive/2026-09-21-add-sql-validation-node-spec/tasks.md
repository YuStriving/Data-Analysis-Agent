# Tasks

## 1. 校验契约与规则结果

- [x] 1.1 定义结构化 SQL 校验结果模型，并用单元测试验证通过、拒绝、warning、扩展策略字段可以序列化
- [x] 1.2 将 guardrails SQL 校验从 bool 返回扩展为结构化结果，并用单元测试验证危险 token、空 SQL、多语句和安全 SELECT 的结果
- [x] 1.3 保留兼容执行层 guardrail 的布尔判断入口或适配逻辑，并用现有 tool calling runtime 测试验证危险 SQL 仍会被拒绝

## 2. 数据边界与规模规则

- [x] 2.1 实现 relation/table 引用校验，并用单元测试验证当前 schema relation 允许、未知 relation 拒绝
- [x] 2.2 实现字段引用校验，并用单元测试验证当前 schema 字段允许、未知字段拒绝
- [x] 2.3 实现基础结果规模风险判断，并用单元测试验证明细查询缺少限制会产生 warning 或约束标记、聚合查询不会仅因缺少 LIMIT 被拒绝

## 3. 编排节点落地

- [x] 3.1 改造 `validate_sql` 节点读取 `candidate_sql` 和上下文，写入 `analysis.sql_validation`，并用节点单元测试验证失败和通过状态
- [x] 3.2 校验通过时写入 `analysis.validated_sql` 并路由到 `execute_sql`，用图流转测试验证 `generate_sql -> validate_sql -> execute_sql`
- [x] 3.3 校验失败时写入结构化错误和事件，并用节点单元测试验证可修复失败、不可修复失败和缺失 SQL 的输出

## 4. 执行节点命名统一

- [x] 4.1 将数据分析 graph 中的 `run_query` 统一为 `execute_sql`，并用 DAG/graph 测试验证节点顺序和导出名称一致
- [x] 4.2 同步工具调用的 allowed node、节点模块导出和相关测试命名，并用 tool runtime 权限测试验证 `execute_sql` 可调用 query executor
- [x] 4.3 检查文档和测试中仍引用 `run_query` 的位置，完成必要同步并用 `rg "run_query|execute_sql"` 验证无不一致的关键路径引用

## 5. 集成验证

- [x] 5.1 补充数据分析 graph 集成测试，验证合法 MySQL SQL 通过校验并进入执行节点
- [x] 5.2 补充文件 relation 场景测试，验证 `relation_1` 和 `col_1` 等归一化 schema 可以通过 SQL 校验
- [x] 5.3 补充非法 SQL 回归测试，验证业务 `validate_sql` 和执行层 guardrail 都能拒绝危险 SQL
- [x] 5.4 运行 `backend-agent` 相关单元测试，并记录未执行或失败的验证项
