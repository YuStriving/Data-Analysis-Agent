# Prompt Hub 架构文档

## 1. 架构目标

`prompt_hub` 提供 system prompt 的小入口和深实现。

调用方只需要知道：

```python
render_system_prompt(agent_id: str) -> PromptRenderResult
```

内部负责 system prompt 文件位置、front matter 解析、active 版本选择、变量校验、hash 生成和明确异常。

## 2. 模块结构

```text
capabilities/agent_runtime/prompt/
  contracts.py
  exceptions.py
  loader.py
  registry.py
  renderer.py
  service.py
```

system prompt 放在：

```text
capabilities/data_analysis/prompts/system/base.v1.md
```

节点级 LLM 操作手册放在：

```text
capabilities/data_analysis/skills/
```

## 3. 核心流程

```text
render_system_prompt(agent_id)
-> PromptRegistry.get_template(agent_id, "system")
-> PromptRenderer.render
-> PromptRenderResult
```

`PromptRegistry` 只扫描 `*/prompts/system/**/*.md`。

## 4. 与执行层的关系

执行层负责把 system prompt 与 Node Skill 组合成模型请求：

```text
PromptRenderResult(system) -> role=system
SkillRenderResult(node skill) -> role=user
```

`prompt_hub` 不负责 Node Skill 静态绑定、required_context 校验、output_contract 映射或模型输出解析。
