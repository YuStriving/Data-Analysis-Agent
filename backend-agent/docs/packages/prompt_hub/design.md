# Python Prompt Hub 设计文档

## 1. 背景

`prompt_hub` 曾同时管理 system prompt 和节点级 LLM prompt。随着 Agent Runtime 中 `ContextBundle`、`AgentSpec`、`ToolDefinition` 和节点输出 contract 逐步稳定，节点级 LLM 内容已经从 prompt 概念中拆出，归入 Node Skill。

## 2. 核心定位

`prompt_hub` 只回答一个问题：

```text
当前 Agent 应使用哪一个 system prompt？
```

system prompt 定义 Agent 身份、全局安全边界、权限原则、事实约束和通用失败处理原则。

## 3. 非职责

`prompt_hub` 不负责节点目标、rules、执行步骤、上下文校验、业务输出契约、Tool schema 注入或模型输出解析。

这些内容分别由 Node Skill、ContextBuilder、节点输出 contract、tool_calling 和 workflow 节点处理。

## 4. 文件结构

```text
src/agent_backend/capabilities/agent_runtime/prompt/
src/agent_backend/capabilities/data_analysis/prompts/system/base.v1.md
```

`PromptRegistry` 只扫描 `prompts/system`。

## 5. 消息组装

模型调用由 execution 层组装：

```text
system prompt -> LlmMessage(role="system")
Node Skill + ContextBundle -> LlmMessage(role="user")
```

## 6. 审计字段

执行结果应记录：

```text
system_prompt_version
rendered_system_prompt_hash
skill_id
skill_version
rendered_skill_hash
```

过渡期可继续保留 `prompt_version` 和 `rendered_prompt_hash`，其中旧字段指向当前节点 Skill，用于兼容已有 checkpoint、memory 和测试。
