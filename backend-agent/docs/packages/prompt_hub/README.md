# Prompt Hub README

## 1. 这个模块解决什么问题

`prompt_hub` 负责管理 Agent 使用的 Prompt 模板。

在数据分析 Agent 里，不同节点需要不同提示词：

```text
system：全局身份和安全规则
generate_sql：生成只读 SQL
repair_sql：修复失败 SQL
interpret_result：解释查询结果
build_chart：生成通用图表规格
```

如果把这些提示词硬编码在业务节点里，会有几个问题：

1. 不知道一次执行用了哪个版本的 Prompt。
2. Prompt 变更不容易回放和评测。
3. 变量缺失时可能把 `{{ schema_context }}` 这种占位符直接发给模型。
4. 不同节点的 Prompt 边界容易混在一起。

一句话理解：

```text
prompt_hub 是 Agent 的 Prompt 模板渲染器和版本管理入口。
```

## 2. 它不做什么

`prompt_hub` 不负责：

1. 不负责构建上下文，context 来自 `context_hub`。
2. 不负责保存记忆，记忆来自 `memory`。
3. 不负责调用工具。
4. 不负责执行 SQL。
5. 不负责让模型自由选择工具。
6. 不负责解析模型最终业务结果。

它只做：

```text
PromptTemplate + variables -> PromptRenderResult
```

## 3. 基本使用方式

调用方使用统一入口：

```python
from agent_backend.capabilities.agent_runtime.prompt import (
    PromptRenderRequest,
    render_prompt,
)

result = render_prompt(
    PromptRenderRequest(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        variables={
            "user_question": "统计每月销售额",
            "dataset_context": {"selected_dataset_id": "dataset-sales"},
            "schema_context": {"orders": ["order_date", "amount"]},
            "access_context": {"allowed_tables": ["orders"]},
        },
    )
)
```

返回结果包含：

```text
template_id
template_version
output_contract
rendered_text
rendered_hash
variables_snapshot
```

## 4. 模板文件长什么样

模板是 Markdown 文件，顶部有 `---` 包裹的 front matter。

示例：

```md
---
template_id: data_analysis.generate_sql.base
agent_id: data_analysis_agent
node_id: generate_sql
version: v1
status: active
description: Generate a single read-only SQL candidate from scoped context.
required_variables:
  - user_question
  - dataset_context
  - schema_context
  - access_context
optional_variables:
  - metric_context
  - time_context
  - recent_context
output_contract: generate_sql_result_v1
---

你正在执行 data_analysis_agent.generate_sql 节点。
...
```

front matter 描述模板是谁、属于哪个节点、当前版本、需要哪些变量、输出什么
结构。

正文是实际发给模型的 Prompt。

## 5. 当前 Prompt Set

当前 `data_analysis_agent` 有 5 个模板：

```text
system/base.v1.md
generate_sql/base.v1.md
repair_sql/base.v1.md
interpret_result/base.v1.md
build_chart/base.v1.md
```

暂不做 `planner_prompt`。复杂多步分析后续再通过 planner 或 sql_plan 扩展。

## 6. 必填变量和可选变量

模板会声明两类变量：

```text
required_variables
optional_variables
```

缺少必填变量时，`prompt_hub` 会直接失败，不调用模型。

缺少可选变量时，可以继续渲染，并默认渲染为：

```text
None -> 无
空字符串 -> 无
空 list -> []
空 dict -> {}
```

这样模型不会误以为缺失信息存在。

## 7. 为什么所有输出必须是 JSON

当前所有节点 Prompt 都要求模型返回 JSON。

原因是后续 workflow 需要稳定消费模型输出：

```text
generate_sql 输出 SQL、使用表、使用字段
repair_sql 输出修复 SQL 和修改点
interpret_result 输出答案、发现、限制
build_chart 输出 chart_type 和字段映射
```

如果输出是自由文本，后续节点很难可靠解析。

## 8. 错误如何给用户看

`prompt_hub` 内部抛工程异常，例如：

```text
MissingPromptVariablesError
```

上层 workflow 再映射成用户友好提示。

例如缺少 `schema_context`：

```text
我暂时无法读取当前数据集的表结构，所以还不能可靠生成 SQL。请确认数据源连接是否正常，或稍后重试。
```

这样既保留了工程排查信息，也不会把模板路径、权限细节或内部 trace 暴露给用户。

## 9. 当前与工具调用的关系

当前 MVP 采用 Graph Workflow 控制工具调用。

也就是：

```text
generate_sql 节点只生成 SQL
validate_sql 节点由 workflow 调用 sql_guard
execute_sql 节点由 workflow 调用 query_runner
```

Prompt 不注入完整工具列表，也不让模型自由选择工具。

后续会向 Model Tool Calling 演进，由 `tool_calling registry` 把当前节点允许的
工具 schema 注入模型调用参数。

## 10. 相关文件

代码：

```text
src/agent_backend/capabilities/agent_runtime/prompt/contracts.py
src/agent_backend/capabilities/agent_runtime/prompt/exceptions.py
src/agent_backend/capabilities/agent_runtime/prompt/loader.py
src/agent_backend/capabilities/agent_runtime/prompt/registry.py
src/agent_backend/capabilities/agent_runtime/prompt/renderer.py
src/agent_backend/capabilities/agent_runtime/prompt/service.py
```

模板：

```text
src/agent_backend/capabilities/data_analysis/prompts/
```

测试：

```text
tests/unit/test_prompt_hub.py
```

设计文档：

```text
docs/packages/prompt_hub/design.md
docs/packages/prompt_hub/architecture.md
```
