# Node Skills README

## 1. 模块定位

Node Skill 是节点级 LLM 操作手册。它承接原先节点 prompt 中的节点目标、边界、内部推理流程、rules、few-shot 示例、上下文需求和输出契约引用。

本阶段不做 Skill 注册与发现，也不让模型自由选择 Skill。workflow 节点通过静态 node binding 或显式路径映射加载对应 Skill。

## 2. Skill 文件位置

```text
src/agent_backend/capabilities/data_analysis/skills/
  generate_sql/base.v1.md
  repair_sql/base.v1.md
  interpret_result/base.v1.md
  build_chart/base.v1.md
```

## 3. Front Matter

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

## 4. 正文结构

Skill 正文建议使用：

```text
目标
边界
内部推理流程（不要输出完整推理链）
规则
Few-shot 示例
输出要求
失败处理
```

内部推理流程用于约束模型在节点内的检查顺序，例如先识别意图、再匹配 schema、再检查权限、最后输出 JSON。它不要求模型把完整推理链返回给用户或写入业务状态；最终输出只能保留符合 contract 的简短依据字段，例如 `reason`、`basis`、`warnings`。

Few-shot 示例应包含输入场景、关键上下文证据和期望 JSON。示例 JSON 必须贴近 `output_contract`，但真正可信的强校验仍由 Pydantic contract 或节点解析逻辑完成。

## 5. 与 system prompt 的关系

```text
system prompt -> role=system
Node Skill + ContextBundle -> role=user
```

system prompt 是全局规则，Node Skill 是当前工位的操作说明。

## 6. 本阶段明确不做

1. 不做 SkillRegistry。
2. 不做 Skill 搜索与发现。
3. 不做模型自主选择 Skill。
4. 不做远程 Skill 发布。
