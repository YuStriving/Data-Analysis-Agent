# Design

## Context

见 `proposal.md` 的动机说明。当前 `prompt_hub` 负责 Markdown front matter 加载、active 版本选择、变量校验、渲染和 hash 生成；`LlmRequestAdapter` 当前把渲染结果作为单条 `user` message 发给模型。项目已经存在 `AgentSpec/NodeSpec`、`ContextBundle`、`ToolDefinition` 和 `GenerateSqlResult` 等运行时契约，这些契约应继续承担运行控制、上下文输入、工具权限和输出强校验职责。

当前四个节点级文件 `generate_sql/base.v1.md`、`repair_sql/base.v1.md`、`interpret_result/base.v1.md`、`build_chart/base.v1.md` 已经包含 Skill 雏形：节点目标、边界、输入、rules 和输出 JSON 契约。重构重点是重新命名和归位，而不是重新设计这些节点行为。

## Goals / Non-Goals

**Goals:**

- 将 `prompt` 语义收窄为 system prompt。
- 将节点级 LLM 任务说明抽象为 Node Skill。
- 通过显式节点绑定或临时静态映射确定当前节点使用的 Skill。
- 让 Skill 通过 `output_contract` 标识连接现有输出校验器。
- 让 LLM 调用显式区分 `system` message 与当前节点任务 message。
- 先迁移现有四个数据分析 LLM 节点，保持行为兼容。

**Non-Goals:**

- 不引入 Skill 注册与发现机制。
- 不引入模型自由选择全量 Skill 的自主路由。
- 不重写 `tool_calling`、`guardrails`、`ContextBuilder` 或 Java 权限来源。
- 不把 Pydantic contract 内容复制进 Skill 作为唯一可信 schema。
- 不在本变更实现完整 Skill 管理后台、远程发布或 A/B 实验。

## Decisions

### Decision 1: 新增 Node Skill 定义与加载能力，而不是继续扩展 prompt_hub

新增 `capabilities/agent_runtime/skills` 或 `capabilities/agent_runtime/node_skills`，承载通用 Skill contract、loader、renderer/composer 与错误类型。`capabilities/agent_runtime/prompt` 保留 system prompt 能力。

本变更不实现 registry/discovery。备选方案是继续把 `PromptTemplate` 扩展成 SkillTemplate。该方案改动少，但会继续让 `prompt` 同时代表系统提示词和节点操作手册，无法解决命名和职责混杂。

### Decision 2: MVP 使用静态 node binding 选择 Skill

MVP 的选择规则为节点代码或配置显式绑定 Skill 文件路径，例如 `generate_sql -> data_analysis/skills/generate_sql/base.v1.md`。这与当前 Graph Workflow 一致：节点已经决定当前步骤，不需要模型再猜测调用哪个 Skill。

备选方案是先做 `SkillRegistry` 并通过 `agent_id + node_id` 查找 active Skill。该方案是合理演进方向，但当前需求明确先不做注册与发现，因此本变更只保留静态绑定能力。

### Decision 3: Skill 引用 output_contract id，而不是直接依赖 Python 类

Skill front matter 声明 `output_contract: generate_sql_result_v1`。运行时通过一个 output contract 映射表或节点现有解析逻辑把该 id 映射到对应 Pydantic 校验器。

备选方案是在 Skill 中写 Python 类名或 import path，例如 `GenerateSqlResult`。该方案耦合实现细节，后续类名、包路径或语言实现变化会导致 Skill 文本也必须变更。

### Decision 4: Context 使用 section 级声明

Skill 使用 `required_context` 和 `optional_context` 声明 `ContextBundle` section，例如 `request`、`dataset`、`schema`、`access`、`repair`、`execution_result`。字段级裁剪继续由 `ContextPolicy` 与 ContextBuilder 负责。

备选方案是在 Skill 中声明 `user_question`、`schema_context` 等扁平变量。该方案沿用 prompt_hub 变量模型，但会重复 ContextBundle 的结构，并让节点消息组装层重新承担上下文建模职责。

### Decision 5: 先保留 Markdown + front matter 文件格式

Skill 文件继续使用 Markdown + front matter，目录建议为：

```text
capabilities/data_analysis/skills/
  generate_sql/base.v1.md
  repair_sql/base.v1.md
  interpret_result/base.v1.md
  build_chart/base.v1.md
```

推荐 front matter：

```yaml
skill_id: data_analysis.generate_sql
agent_id: data_analysis_agent
nodes:
  - generate_sql
version: v1
status: active
description: Generate a single read-only SQL candidate from scoped context.
selection:
  strategy: node_binding
required_context:
  - request
  - dataset
  - schema
  - access
optional_context:
  - conversation
  - previous_turn
output_contract: generate_sql_result_v1
response_format: json_object
allowed_tools: []
```

正文使用稳定结构：

```text
目标
边界
输入上下文
内部推理流程（不要输出完整推理链）
规则
Few-shot 示例
输出要求
失败处理
```

其中，内部推理流程用于约束节点内的检查顺序，不要求模型输出完整思维链；最终响应仍只能输出符合 `output_contract` 的 JSON，并把依据压缩到 `reason`、`basis`、`warnings` 等 contract 字段。Few-shot 示例用于降低模型对 contract、状态枚举和失败分支的理解偏差。

### Decision 6: LLM 消息组装由 execution 层使用 prompt + skill + context 完成

模型调用时组装：

```text
system message = active system prompt
user message = rendered Node Skill + rendered ContextBundle sections
```

`LlmRequestAdapter` 不再只接收单个 `PromptRenderResult`。可新增 `SkillExecutionRequest` 或 `LlmStepMessages`，包含 system prompt 结果、skill 渲染结果、response format 和 metadata。

### Decision 7: Node Skill 使用内部推理流程与 few-shot 示例增强可执行性

Node Skill 不应只声明抽象规范，还需要提供节点级内部检查流程与少量 few-shot 示例。内部检查流程采用 COT-style 的分步检查方式，但必须明确“不要输出完整推理链”，只允许在 contract 字段中输出简短依据摘要。

Few-shot 示例需要覆盖至少一个成功路径和一个失败或降级路径，例如 `clarification_required`、`cannot_repair`、`empty_result` 或 `not_applicable`。示例是行为引导，不替代运行时 contract 强校验。

## Risks / Trade-offs

- [Risk] 重命名 prompt 到 skill 会影响较多测试和文档。 → Mitigation: 先保留兼容字段或过渡 adapter，逐节点迁移，优先跑现有 `generate_sql` 流程测试。
- [Risk] Skill 中继续写 JSON 示例可能与 Pydantic contract 漂移。 → Mitigation: Skill 只引用 `output_contract` 并保留人类可读示例，强校验以 output contract 映射表为准；测试覆盖 schema 不一致场景。
- [Risk] 双 hash 记录增加审计字段复杂度。 → Mitigation: 明确 metadata 字段为 `system_prompt_*` 与 `skill_*`，旧字段仅在过渡期保留。
- [Risk] 后续 intent/context 路由可能扩大复杂度。 → Mitigation: MVP 只做 node binding，设计中预留 `selection.strategy` 但不实现自主路由。

## Migration Plan

1. 新增 Node Skill contract、loader 与错误类型，覆盖缺 metadata、缺 required context 等测试。
2. 新增或调整 system prompt 能力，确保 active system prompt 可单独加载、版本化并生成 hash。
3. 将四个节点 prompt 文件复制/迁移到 `skills` 目录，转换 front matter；正文保留现有规则并按 Skill 结构轻微整理。
4. 为四个 Node Skill 增加内部推理流程和 few-shot 示例，覆盖成功与失败或降级路径。
5. 新增消息组装逻辑，将 system prompt 与 Node Skill 分别组装为 `system` 与 `user` message。
6. 将 `generate_sql` 先切到 Node Skill 执行路径，保留输出校验与现有状态写入逻辑。
7. 迁移 `repair_sql`、`interpret_result`、`build_chart` 到同一路径。
8. 更新 `prompt_hub` 文档、`backend-agent/agent.md` 中 Prompt and Context Rules，以及相关单元测试。
9. 通过测试后移除或标记废弃节点级 prompt 路径，保留 system prompt 路径。

## Open Questions

无。当前 MVP 采用静态 node binding，Skill 注册与发现留到后续变更。
