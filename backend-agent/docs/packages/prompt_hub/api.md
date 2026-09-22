# Python Prompt Hub 接口文档

## 1. 公开入口

### `render_system_prompt(agent_id: str, variables: dict | None = None) -> PromptRenderResult`

加载并渲染指定 Agent 的 active system prompt。

返回字段：

```text
agent_id
node_id = system
template_id
template_version
output_contract
rendered_text
rendered_hash
variables_snapshot
```

## 2. 兼容入口

### `render_prompt(request: PromptRenderRequest) -> PromptRenderResult`

保留为底层渲染入口，但当前只支持 `node_id="system"` 的 system prompt。

节点级 LLM 内容应使用 Node Skill 相关接口。

## 3. Prompt 来源

```text
src/agent_backend/capabilities/data_analysis/prompts/system/base.v1.md
```
