# Python Prompt Hub 模块需求

## 1. 模块定位

`prompt_hub` 负责管理系统提示词、分析规划提示词和特定角色提示词，为 Agent 提供稳定、可审计的提示模板。

## 2. 当前代码现状

当前只有一个 `SYSTEM_PROMPT` 常量，内容强调只读分析和可追踪性。MVP 需要把 prompt 管理从常量扩展为模板中心。

## 3. 核心职责

1. 管理系统 Prompt
2. 管理规划 Prompt
3. 管理 SQL 分析 Prompt
4. 管理人工审核 Prompt
5. 支持按任务拼装 Prompt Bundle

## 4. MVP 功能需求

1. 支持从 `src/agent_backend/capabilities/data_analysis/prompts/` 目录加载模板
2. 支持模板版本管理
3. 支持拼接系统提示、角色提示和上下文片段
4. 支持记录实际使用的 prompt 版本

## 5. 验收标准

1. 不同执行节点可以拿到对应模板
2. Prompt 变更可被审计和回放
3. Planner 和 SQL 分析节点不再硬编码提示词
