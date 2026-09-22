# Python Prompt Hub 模块需求

## 1. 模块定位

`prompt_hub` 负责管理 system prompt，为 Agent 提供稳定、可版本化、可审计的全局系统提示词。

## 2. 核心职责

1. 加载 system prompt Markdown 文件。
2. 解析 front matter。
3. 选择 active system prompt。
4. 渲染 system prompt。
5. 生成 rendered hash。

## 3. 非职责

1. 不管理节点级 LLM Skill。
2. 不管理 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 的规则和步骤。
3. 不负责上下文构建。
4. 不负责模型输出校验。

## 4. MVP 功能需求

1. 支持从 `src/agent_backend/capabilities/data_analysis/prompts/system/` 加载 system prompt。
2. 支持 system prompt 版本管理。
3. 支持记录 system prompt 版本和 hash。
4. 支持与 Node Skill 组合成 system/user 两类消息。

## 5. 验收标准

1. `render_system_prompt("data_analysis_agent")` 能返回 active system prompt。
2. `prompt_hub` 不再加载节点级 Skill 文件。
3. 执行层能记录 system prompt 版本和 hash。
