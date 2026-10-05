# 通用 Tools 调用契约实施计划

Spec：[spec.md](spec.md)；相关可执行测试见[授权 Gate](../../../backend-agent/tests/unit/test_tool_authorization_gate.py) 与[执行器](../../../backend-agent/tests/unit/test_tool_executor.py)。

目标：建立可替换工具、统一 Core 授权和明确目标上下文的调用路径。
技术：现有 Python、Pydantic、jsonschema、asyncio、pytest、Ruff。
执行：当前会话按序实施，不主动创建分支、提交或 PR；保留原有未提交改动。

## 任务

- [x] P0：落盘规格、设计、任务与集中测试方案；迁移 RULE-01～RULE-07；验证链接及编号。
- [x] P1：先补契约失败测试，再分离通用/业务 context 与组合请求；验证目标必填和业务类型保留。
- [x] P2：先补 Gate 拒绝测试，再实现公共能力与授权检查；保留业务资源与 SQL 检查。
- [x] P3：先补执行器及 Runtime 测试，再固定配置注入、接入 Gate 和 JSON 输出检查。
- [x] P4：迁移业务工厂、build_context 与执行控制请求读取；验证身份匹配与原数据分析路径。
- [x] P5：相关测试与 Ruff 通过后移除重复逻辑、更新规范与使用说明，记录实际验证结果。

## 文件责任与验证

代码路径相对 backend-agent：
- tool_calling/contracts.py、executor.py、runtime.py：通用模型、执行及路由。
- execution_control/tool_authorization_gate.py：公共授权；runtime.py 与 tool_guard.py：组合请求读取。
- data_analysis/tools/contracts.py、policy.py、runtime.py：业务范围与装配。
- orchestration/data_analysis/nodes/build_context.py：从可信任务构造 goal/purpose 与业务上下文。
- tests/unit 下现有契约、执行器、数据分析和控制测试；新增 test_tool_authorization_gate.py。

每个代码任务按失败测试 → 确认失败原因 → 最小实现 → 目标测试通过执行。
授权旧检查只有在新路径接好并通过拒绝场景后才移除。
最终命令与结果统一记录在根目录测试方案，关键场景未验证不得标记完成。

## 实施记录

2026-10-03：用户确认完整计划并授权实施；P0～P5 已完成。
Ruling：遵循用户指定当前会话与不操作 Git 的方式，直接在当前工作区实施；不创建 worktree。

- P0：规格与用例集中落位，保留 RULE-01～07 并增加测试集中管理的 RULE-08。
- P1：通用 context 独立权限、必填 goal/purpose；业务 context 持有 DatasetScope；组合请求保留具体类型。
- P2：Core Gate 检查 AgentSpec、节点、权限、风险、审批；业务检查显式注入，移除业务 checker 中的重复公共判断。
- P3：独立执行器固定 options 与授权；Runtime 精确查找并直接传递 context；严格 JSON 输出校验。
- P4：业务工厂与调用节点完成迁移，Java 任务身份不匹配或非只读上下文拒绝；执行控制读取 request.context。
- P5：独立复核发现非法授权返回值被忽略，新增 9 个失败用例后修正；已声明 DuckDB 依赖在忽略目录补齐。
  最终目标测试 127 passed、无跳过，Ruff 通过；文档、函数引用及规则编号通过核验。

实现和复核澄清：authorize/business_check 的返回 None 契约是同步契约；bool/awaitable
均拒绝，而业务工具仍支持异步。该规则已同步 design 与使用说明，未扩大需求范围。
执行控制保留用于流程终止决策和重复失败统计的预检查；每次实际执行仍必须通过 Core Gate。
测试方案的 V1～V4 保存命令、实际结果、复核证据和未运行的范围；实施阶段未执行提交、分支或 PR 操作。
后续用户明确授权本次本地 commit，提交包含工具调用链及其直接依赖，其他独立改动保留在工作区。
