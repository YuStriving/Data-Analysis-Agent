# Context Hub README

## 1. 这个模块解决什么问题

`context_hub` 负责给 Agent 准备“当前节点能看到的资料包”。

用户问一个数据分析问题时，系统里会有很多信息：

```text
用户问题
当前用户身份
当前 session
已选择的数据集
数据表结构
最近对话
上一轮 SQL
SQL 失败原因
查询结果摘要
图表摘要
```

这些信息不能全部直接塞给模型。原因有三点：

1. 有些信息没有权限给当前 Agent 节点看。
2. 有些信息太大，比如完整聊天历史、完整查询结果。
3. 有些信息和当前节点无关，放进去会干扰模型。

所以 `context_hub` 的职责就是：

```text
从原始资料中选出当前节点需要的部分，
裁剪掉过长或不该看的部分，
产出结构化 ContextBundle。
```

一句话理解：

```text
context_hub 是 Agent 的资料包生成器。
```

## 2. 它不做什么

`context_hub` 不是万能模块，它不负责：

1. 不负责保存长期记忆，长期记忆属于 `memory`。
2. 不负责渲染 Prompt，Prompt 渲染属于 `prompt_hub`。
3. 不负责执行 SQL，SQL 执行属于工具或 workflow。
4. 不负责判断用户真实权限，权限结果由 Java 后端或数据权限模块提供。
5. 不负责调用大模型。

它只做一件事：

```text
ContextSource + ContextPolicy -> ContextBundle
```

## 3. 三个核心概念

### 3.1 ContextSource

`ContextSource` 是原材料。

它可以理解为“系统目前收集到的全部上下文候选信息”。

常见内容包括：

```text
identity：任务、用户、session 信息
request：用户问题和任务类型
dataset：当前可用数据集和选中数据集
schema：表结构、字段、指标映射、时间字段提示
conversation：对话摘要和已确认事实
previous_turn：上一轮问题、SQL、结果和图表摘要
repair：失败 SQL、错误信息和重试次数
execution_result：已执行 SQL 的结果摘要
chart：图表相关上下文
runtime：当前 Agent 和节点信息
```

### 3.2 ContextPolicy

`ContextPolicy` 是规则。

它回答：

```text
当前 Agent 的当前节点允许看哪些 section？
哪些 section 是必须的？
哪些内容需要裁剪？
```

比如 `generate_sql` 节点需要 `request`、`dataset`、`schema`，但不需要完整
查询结果。

### 3.3 ContextBundle

`ContextBundle` 是最终输出。

它是经过白名单过滤和裁剪后的结构化上下文。后续 `prompt_hub` 会基于它渲染
具体 Prompt。

注意：

```text
ContextBundle 不是 Prompt 字符串。
```

## 4. 当前支持的节点策略

当前围绕 `data_analysis_agent` 支持四个主要节点：

```text
generate_sql
repair_sql
interpret_result
build_chart
```

每个节点都有自己的 `ContextPolicy`。

### generate_sql

用途：生成只读 SQL。

必须有：

```text
request
dataset
schema
```

原因：没有用户问题、数据集和表结构，模型很容易编造 SQL。

### repair_sql

用途：修复失败 SQL。

必须有：

```text
request
dataset
schema
repair
```

原因：修复 SQL 必须知道原问题、失败 SQL、错误原因和可用 schema。

### interpret_result

用途：解释查询结果。

必须有：

```text
request
execution_result
```

原因：解释结果不能脱离用户问题和真实执行结果。

### build_chart

用途：生成通用图表规格。

必须有：

```text
request
execution_result
```

原因：图表必须基于真实查询结果，而不是模型自己想象数据。

## 5. 基本使用方式

典型调用流程：

```python
policy = resolve_context_policy("data_analysis_agent", "generate_sql")
result = ContextBuilder().build(source, policy)
```

如果成功：

```python
result.status == "ok"
result.bundle is not None
```

如果缺少必需上下文：

```python
result.status == "missing_required_context"
result.missing_sections == ["dataset", "schema"]
```

上层 workflow 看到缺上下文后，不应该继续调用模型，而应该给用户友好提示。

## 6. 为什么要按 session 隔离

当前产品优先面向 C 端用户。一个用户可以开启多个对话窗口，每个窗口就是一个
`session_id`。

`session_id` 的作用是防止上下文串台：

```text
A 对话上传了销售数据
B 对话上传了库存数据
```

如果没有 session 隔离，B 对话可能错误地复用 A 对话的数据集或 SQL。

所以当前上下文隔离顺序是：

```text
user_id
session_id
dataset_id
```

`tenant_id` 在 MVP 中保留，默认可为 `default`，为后续团队空间或多租户保留
扩展位置。

## 7. 常见问题

### 为什么不直接把 memory 全部注入 Prompt？

因为 memory 是存储层，里面有很多历史信息。是否能注入 Prompt，必须经过
`ContextPolicy` 裁剪。

### 为什么不注入完整查询结果？

完整结果可能很大，也可能包含敏感信息。MVP 只注入摘要、有限预览或引用。

### schema 为什么要限制长度？

schema 太长会挤占模型上下文，还会干扰 SQL 生成。当前 policy 支持
`max_schema_chars`。

### 缺少 dataset 或 schema 时为什么直接失败？

这是为了避免模型编造表名、字段名和 SQL。失败比胡编更安全。

## 8. 相关文件

代码：

```text
src/agent_backend/capabilities/agent_runtime/context/contracts.py
src/agent_backend/capabilities/agent_runtime/context/policies.py
src/agent_backend/capabilities/agent_runtime/context/builder.py
src/agent_backend/capabilities/agent_runtime/context/classifier.py
```

测试：

```text
tests/unit/test_context_hub.py
```

设计文档：

```text
docs/packages/context_hub/design.md
docs/packages/context_hub/architecture.md
```
