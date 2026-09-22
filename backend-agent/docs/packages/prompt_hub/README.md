# Prompt Hub README

## 1. 模块定位

`prompt_hub` 只负责 system prompt 的加载、版本选择、渲染、hash 生成和审计信息。

system prompt 定义 Agent 的全局身份、安全边界、权限原则、事实约束和失败处理原则。它不描述某个 workflow 节点的具体任务。

## 2. 它不做什么

`prompt_hub` 不负责：

1. 不负责节点级 LLM 操作说明。
2. 不负责 `generate_sql`、`repair_sql`、`interpret_result`、`build_chart` 的规则和步骤。
3. 不负责构建上下文，context 来自 `context_hub`。
4. 不负责调用工具或执行 SQL。
5. 不负责解析模型业务输出。

节点级 LLM 内容属于 Node Skill，见 `docs/packages/node_skills/README.md`。

## 3. 基本使用方式

```python
from agent_backend.capabilities.agent_runtime.prompt import render_system_prompt

result = render_system_prompt("data_analysis_agent")
```

返回结果包含：

```text
template_id
template_version
rendered_text
rendered_hash
output_contract
```

## 4. System Prompt 文件

system prompt 仍使用 Markdown + front matter：

```text
src/agent_backend/capabilities/data_analysis/prompts/system/base.v1.md
```

## 5. 与 Node Skill 的关系

一次 LLM 节点调用应组装两类消息：

```text
system message = prompt_hub 加载的 active system prompt
user message = Node Skill 正文 + 当前 ContextBundle
```

`prompt_hub` 不扫描 `skills/` 目录，也不负责 Skill 绑定、上下文校验或输出契约选择。
