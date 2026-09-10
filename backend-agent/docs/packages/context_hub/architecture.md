# Context Hub 架构文档

## 1. 架构目标

`context_hub` 的架构目标是把“上下文准备”做成一个独立、可测试、可审计的
Module。

它的外部 Interface 尽量小：

```python
ContextBuilder().build(source, policy) -> ContextBuildResult
```

调用方只需要提供：

```text
ContextSource
ContextPolicy
```

内部 Implementation 负责：

```text
必需 section 校验
允许 section 白名单过滤
schema 裁剪
conversation 裁剪
repair 记录裁剪
execution_result 原始行控制
runtime/meta 注入
```

这样做的好处是：后续新增上下文来源、调整裁剪策略、升级 policy version，
调用方不需要到处改。

## 2. 模块结构

```text
capabilities/agent_runtime/context/
  __init__.py
  contracts.py
  policies.py
  builder.py
  classifier.py
```

### contracts.py

定义上下文数据结构。

主要模型：

```text
ContextSource
ContextPolicy
ContextBundle
ContextBuildResult
ContextInjectionBundle
```

`ContextSource` 是输入原材料，`ContextBundle` 是输出资料包。

### policies.py

定义节点策略。

主要 Interface：

```python
resolve_context_policy(agent_name: str, node_name: str) -> ContextPolicy
```

当前按 `agent_name + node_name` 返回固定 policy。

### builder.py

实现上下文构造。

核心 Interface：

```python
class ContextBuilder:
    def build(self, source: ContextSource, policy: ContextPolicy) -> ContextBuildResult:
        ...
```

### classifier.py

提供轻量任务分类，用于老的 `build_context` 兼容入口。

## 3. 数据流

一次典型 SQL 生成前的上下文流程：

```text
Java task request
-> dataset resolver
-> schema reader
-> memory hot context
-> ContextSource
-> resolve_context_policy(data_analysis_agent, generate_sql)
-> ContextBuilder.build
-> ContextBundle
-> prompt_hub.render_prompt
```

如果缺少必要上下文：

```text
ContextBuilder.build
-> ContextBuildResult(status=missing_required_context)
-> workflow 返回用户友好提示
-> 不调用 LLM
```

## 4. ContextSource 到 ContextBundle

`ContextBuilder` 不直接读取 Redis、MongoDB、MySQL 或文件。它只处理传入的
`ContextSource`。

这样可以保持清晰的 seam：

```text
外部 adapter：负责取数据
context_hub：负责筛选、裁剪、组装
```

构建过程：

```text
1. 检查 required_sections。
2. 如果缺少必需 section，返回 missing_required_context。
3. 遍历 allowed_sections。
4. 将允许的 section 从 source 复制到 bundle。
5. 按 policy 限制裁剪过长内容。
6. 自动补充 runtime。
7. 自动生成 meta。
8. 返回 ContextBuildResult(status=ok)。
```

## 5. 缺失判断

不是字段存在就代表上下文可用。

当前 Implementation 对关键 section 做语义空值判断：

```text
dataset：必须有 selected_dataset_id
schema：必须有 schema_summary、semantic_schema_summary 或 field_summary
repair：必须有 failed_sql 和 error_message
execution_result：必须有 executed_sql、result_summary 或 table_preview
```

这样可以避免空对象绕过必填校验。

## 6. 裁剪策略

当前支持的裁剪：

```text
schema：按 max_schema_chars 裁剪 schema_summary 和 semantic_schema_summary
conversation：按 max_conversation_chars 裁剪 conversation_summary
repair：按 max_repair_items 裁剪 avoid_errors
execution_result：如果 include_raw_rows=false，则清空 table_preview
```

如果发生裁剪，`ContextMeta.truncated_sections` 会记录对应 section。

## 7. 节点 Policy

当前内置四组 v2 policy：

```text
generate_sql_v2
repair_sql_v2
interpret_result_v2
build_chart_v2
```

### generate_sql_v2

目标：让模型生成 SQL 时看到问题、数据集、schema 和必要历史。

关键限制：

```text
required_sections = request, dataset, schema
include_raw_rows = false
max_schema_chars = 4000
max_conversation_chars = 2000
```

### repair_sql_v2

目标：让模型基于失败 SQL 和错误信息做最小修复。

关键限制：

```text
required_sections = request, dataset, schema, repair
max_repair_items = 3
```

### interpret_result_v2

目标：只基于执行结果解释用户问题。

关键限制：

```text
required_sections = request, execution_result
include_raw_rows = false
```

### build_chart_v2

目标：只基于执行结果生成 chart spec。

关键限制：

```text
required_sections = request, execution_result
include_raw_rows = false
```

## 8. 与其他模块的关系

### 与 memory

memory 提供最近对话、上一轮 SQL、失败经验等原材料，但是否进入 Prompt 要由
`ContextPolicy` 决定。

### 与 prompt_hub

`context_hub` 输出结构化 `ContextBundle`，`prompt_hub` 再把它转换成 Prompt
变量并渲染模板。

### 与 tool_calling

工具节点也可以消费 `ContextBundle`，例如 SQL guard 可以使用 dataset 和
schema 信息做校验。

### 与 checkpoint

checkpoint 负责运行恢复。恢复时可以把 checkpoint 中的稳定状态转换成
`ContextSource`，再由 `context_hub` 构造恢复节点需要的 bundle。

## 9. 开发新节点的步骤

新增一个节点时，按这个顺序做：

```text
1. 判断节点真正需要哪些上下文 section。
2. 在 contracts.py 中确认是否已有对应 section。
3. 在 policies.py 中新增 agent_name.node_name 的 ContextPolicy。
4. 写测试验证 required_sections 缺失时会失败。
5. 写测试验证不允许的 section 不会出现在 bundle 中。
6. 写测试验证超长内容会按 policy 裁剪。
```

## 10. 当前风险与后续演进

当前风险：

1. policy 仍是代码内静态配置。
2. schema 裁剪只是字符级裁剪，还不理解表和字段优先级。
3. conversation 只做简单长度限制。
4. `ContextBundle` 到 Prompt 变量的转换还需要 workflow 侧接入。

后续演进：

1. 引入 `PolicySelector`。
2. 支持按任务类型选择更细的 schema 摘要。
3. 支持字段级权限裁剪。
4. 支持 token 预算。
5. 支持 schema 缓存和 schema hash。
