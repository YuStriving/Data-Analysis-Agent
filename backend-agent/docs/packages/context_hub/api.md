# Python Context Hub 接口文档

当前上下文构建主接口是 `ContextBuilder.build(source, policy)`；以下旧版
`build_context(request, snapshot)` 字典返回契约已不再是当前 API。

## 1. 当前接口

### `ContextBuilder.build(source: ContextSource, policy: ContextPolicy) -> ContextBuildResult`

先检查必需 section，再按允许 section 构建 bundle；对可变输入深复制，并按策略执行
schema/对话字符裁剪、修复项数量限制或隐藏原始结果行。结果状态为 `ok` 或
`missing_required_context`，并携带 bundle、缺失项和警告。

主要契约定义位于 `foundation/contracts/context.py`，实现位于
`capabilities/agent_runtime/context/builder.py`。

### `classify_task(request, snapshot=None) -> TaskProfile`

这是独立分类辅助函数，不负责构造新的上下文 bundle。具体分类字段与行为以
`capabilities/agent_runtime/context/classifier.py` 和当前调用方为准。

## 2. 数据分析图中的装配

图构建器将 `load_task_context` 输出的授权任务状态、数据集元信息和 schema 工具结果
交给 `build_context` 节点，再用 `ContextBuilder` 按 `generate_sql` 策略构建上下文。
缺失必需内容时进入统一失败出口。节点行为见
[图运行时说明](../graph_runtime/requirements.md) 与
`src/agent_backend/orchestration/data_analysis/nodes/build_context.py`。
