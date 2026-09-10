# Prompt Hub 架构文档

## 1. 架构目标

`prompt_hub` 的目标是提供一个小 Interface、深 Implementation 的 Prompt
Module。

调用方只需要知道：

```python
render_prompt(PromptRenderRequest) -> PromptRenderResult
```

它不需要知道：

```text
模板文件在哪里
front matter 怎么解析
active 版本怎么选择
变量怎么校验
hash 怎么生成
缺失变量怎么映射用户提示
```

这些复杂度都留在 `prompt_hub` 内部。

## 2. 模块结构

```text
capabilities/agent_runtime/prompt/
  __init__.py
  contracts.py
  exceptions.py
  loader.py
  registry.py
  renderer.py
  service.py
  templates.py
```

业务模板放在：

```text
capabilities/data_analysis/prompts/
  system/base.v1.md
  generate_sql/base.v1.md
  repair_sql/base.v1.md
  interpret_result/base.v1.md
  build_chart/base.v1.md
```

## 3. 各文件职责

### contracts.py

定义公开数据结构：

```text
PromptTemplate
PromptRenderRequest
PromptRenderResult
UserFacingFailure
```

`PromptRenderRequest` 是输入。

`PromptRenderResult` 是成功渲染后的输出，包含模板版本和 hash。

### exceptions.py

定义明确异常：

```text
PromptTemplateFormatError
PromptTemplateNotFoundError
DuplicateActivePromptTemplateError
MissingPromptVariablesError
UndeclaredPromptVariablesError
```

这些异常用于工程排查和 workflow 分支处理。

### loader.py

负责读取 `.md` 模板并解析 front matter。

当前不新增 YAML 依赖，只支持 MVP 需要的简单格式：

```text
key: value
list_key:
  - item
```

### registry.py

负责扫描模板目录并建立索引：

```text
(agent_id, node_id, version) -> PromptTemplate
```

如果调用方不指定版本，则选择 `status=active` 的模板。

同一个 `agent_id + node_id` 下多个 active 模板会报错。

### renderer.py

负责：

```text
校验模板中使用的变量是否已声明
校验 required_variables 是否存在
为 optional_variables 填默认空值
替换 {{ variable }} 占位符
生成 sha256(rendered_text)
```

### service.py

提供对外统一入口：

```python
render_prompt(request)
map_prompt_error_to_user_failure(error)
```

`render_prompt` 串联 registry 和 renderer。

`map_prompt_error_to_user_failure` 把工程错误映射成用户友好反馈。

## 4. 渲染流程

完整流程：

```text
PromptRenderRequest
-> PromptRegistry.get_template
-> PromptRenderer.render
-> 校验 declared placeholders
-> 校验 required variables
-> 补 optional variables
-> 替换占位符
-> 计算 rendered_hash
-> PromptRenderResult
```

如果失败：

```text
缺模板 -> PromptTemplateNotFoundError
front matter 错误 -> PromptTemplateFormatError
多个 active -> DuplicateActivePromptTemplateError
缺必填变量 -> MissingPromptVariablesError
模板引用未声明变量 -> UndeclaredPromptVariablesError
```

## 5. Front Matter 契约

每个模板必须声明：

```yaml
template_id: data_analysis.generate_sql.base
agent_id: data_analysis_agent
node_id: generate_sql
version: v1
status: active
description: Generate a single read-only SQL candidate from scoped context.
required_variables:
  - user_question
optional_variables:
  - recent_context
output_contract: generate_sql_result_v1
```

字段说明：

```text
template_id：模板稳定 ID
agent_id：所属 Agent
node_id：所属节点
version：模板版本
status：active / inactive / deprecated
description：给开发者看的说明
required_variables：缺少即失败
optional_variables：缺少可渲染为空
output_contract：模型必须返回的 JSON 契约
```

## 6. 版本选择

指定版本：

```python
PromptRenderRequest(
    agent_id="data_analysis_agent",
    node_id="generate_sql",
    template_version="v1",
    variables={...},
)
```

不指定版本：

```text
选择当前 active 模板。
```

版本规则：

```text
Prompt 语义变化要升版本
变量契约变化要升版本
输出契约变化要升版本
同一 agent_id + node_id 只能有一个 active
```

## 7. 变量处理

缺少 required variable：

```text
抛 MissingPromptVariablesError
不渲染 Prompt
不调用模型
```

缺少 optional variable：

```text
允许渲染
默认渲染为“无”、[] 或 {}
不保留 {{ variable }}
```

变量存在但语义不足时，`prompt_hub` 不做深度业务判断。业务判断由
`context_hub`、workflow 和节点输出状态负责。

## 8. 输出契约

所有节点 Prompt 都必须返回 JSON。

当前支持：

```text
generate_sql_result_v1
repair_sql_result_v1
interpret_result_v1
build_chart_result_v1
```

`prompt_hub` 当前只声明 `output_contract`，不负责解析模型输出。解析应由
workflow 或节点 result parser 完成。

## 9. 与 System Prompt 的关系

`system` 也作为普通 `node_id` 管理：

```text
data_analysis_agent.system -> system/base.v1.md
```

每次 LLM 节点调用都应携带 system prompt。这样单节点回放、eval 和 checkpoint
恢复更稳定。

## 10. 与 Model Tool Calling 的关系

当前不采用 Model Tool Calling。

当前流程：

```text
Prompt 生成候选输出
Workflow 决定下一步
Workflow 调用工具
Guardrails 做硬校验
```

后续演进：

```text
tool_calling registry
-> 根据 agent_id + node_id 找到 allowed_tools
-> 转换成模型 tools 参数
-> 模型选择工具
-> tool_calling 校验权限和参数
-> guardrails 校验
-> 执行工具
-> 规范化结果和 trace
```

Prompt 层只描述工具使用规则和节点边界，不保存工具实现细节。

## 11. 开发新 Prompt 的步骤

新增节点 Prompt 时：

```text
1. 在 data_analysis/prompts/{node_id}/ 新增 base.v1.md。
2. 在 front matter 中声明 template_id、agent_id、node_id、version、status。
3. 声明 required_variables 和 optional_variables。
4. 声明 output_contract。
5. 正文写清楚节点职责、禁止事项、输入信息和 JSON 输出要求。
6. 增加 Prompt Hub 测试，验证能加载、能渲染、缺必填变量会失败。
7. 如果输出契约需要解析，补 workflow 或 result parser 测试。
```

## 12. 当前风险与后续演进

当前风险：

1. front matter 解析器只支持 MVP 简单格式。
2. `PromptRenderResult.variables_snapshot` 当前返回完整变量，落盘前必须由调用方脱敏。
3. 旧模板文件仍存在，但没有 front matter，不会被 registry 注册。
4. 当前还没有把 prompt_hub 接入实际 graph 节点。

后续演进：

1. 增加 JSON Schema 级输出校验。
2. 增加完整 prompt audit event。
3. 增加 debug 模式下短期保存 rendered_text。
4. 增加 Model Tool Calling 工具 schema 注入。
5. 增加 prompt eval 数据集。
