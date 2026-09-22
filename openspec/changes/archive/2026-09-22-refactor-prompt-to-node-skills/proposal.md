# Proposal

## Why

当前 `prompt_hub` 同时承载 system prompt 与节点级 LLM 任务说明，导致“全局系统提示词”和“某个节点的操作手册”边界混在一起。随着 `AgentSpec`、`ContextBundle`、`ToolDefinition` 和节点输出 contract 逐步稳定，需要先把节点级 LLM 内容从 prompt 概念中抽出为 Node Skill，明确职责边界。

## What Changes

- 将 `prompt` 的职责收窄为 system prompt 管理：Agent 身份、全局安全边界、权限原则、通用失败处理原则。
- 引入 Skill 概念，承接现有 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 节点 prompt 中的节点目标、rules、执行步骤、required context、output contract 和 response format。
- 将 Skill 选择范围收敛为显式节点绑定或临时静态映射；本变更不设计 Skill 注册与发现机制。
- 明确 Skill 通过稳定的 `output_contract` 标识引用输出契约，不直接依赖 Python 类；模型输出仍由现有 Pydantic contract 强校验。
- 调整 LLM message 组装模型：system prompt 进入 `role=system`，当前 Node Skill 与结构化上下文进入 `role=user`。
- 不在本变更中引入 Skill 注册/发现、模型自由选择任意 skill，也不改变工具运行时、SQL guardrails 或 Java 侧权限来源。

## Capabilities

### New Capabilities

- `agent-runtime/node-skills`: 定义 Node Skill 的文件形态、节点绑定、上下文需求、输出契约引用和 LLM 消息组装要求。

### Modified Capabilities

- 无。当前项目尚未同步主规格清单，本次以新增 capability 表达新的 Agent Runtime 行为边界。

## Impact

- 影响 `backend-agent` 中 `capabilities/agent_runtime/prompt` 的职责边界和命名。
- 影响 `capabilities/data_analysis/prompts/{generate_sql,repair_sql,interpret_result,build_chart}` 的归属，后续应迁移为 `capabilities/data_analysis/skills/...`。
- 影响 `capabilities/agent_runtime/execution` 的 LLM request 组装方式，需要支持 system message 与 skill/user message 分离。
- 影响相关文档、单元测试和回放审计字段命名，需从 `prompt_version/rendered_prompt_hash` 过渡到同时记录 system prompt 与 skill 的版本/hash。
