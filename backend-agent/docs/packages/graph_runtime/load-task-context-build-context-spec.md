# load_task_context 与 build_context 实现说明

> 本文源自节点实现前的设计 brief。两个节点现已进入数据分析图；本文保留可复用的
> 约束与决策，当前行为以源码及对应测试为准，不代表 HTTP/SSE/Kafka 链路已接通。

## Problem Statement

数据分析 Agent 的 LangGraph 主链使用 `load_task_context` 和 `build_context`
装载请求、校验授权范围并准备 schema 上下文；后续 `generate_sql`、`validate_sql` 和
`execute_sql` 都依赖这两个节点产出的任务身份、数据集选择、权限边界、schema
上下文和裁剪后的 prompt context。若不先稳定这两个节点的契约，后续节点会把
dataset 选择、权限校验、schema 读取和错误处理散落到各自实现里。

## Solution

当前实现遵循以下决策：

1. `AgentState` 采用嵌套分层结构，同时保留迁移期平铺字段兼容 checkpoint。
2. `load_task_context` 负责请求装载、单数据集选择、只读访问校验和授权确认。
3. `build_context` 负责根据数据集元信息调用现有 schema 工具，并通过
   `ContextBuilder` 生成面向 `generate_sql` 的 `context_bundle`。
4. 可预期业务失败写入 `error` 层，并通过 `graph.next_node=fail_task` 进入统一
   失败出口。
5. 节点事件先写入 `graph.events`；当前 HTTP API 不执行图，Java SSE 传输也尚未接通。

## User Stories

1. As an analyst, I want my selected dataset to be validated before SQL generation, so that the agent never analyzes unauthorized data.
2. As an analyst, I want the agent to reuse the session dataset when I omit a dataset, so that follow-up questions remain convenient.
3. As an analyst, I want inferred dataset usage to be recorded, so that I can tell whether the dataset was explicit or session-derived.
4. As an analyst, I want a clear prompt when no dataset is available, so that I know what action to take next.
5. As an operator, I want readonly access to be enforced before schema loading, so that Python cannot broaden the Java-issued permission boundary.
6. As an operator, I want schema loading to go through the existing tool runtime, so that tool permission checks, timeouts, validation, and logs stay consistent.
7. As a developer, I want `build_context` to output a stable `context_bundle`, so that `generate_sql` can depend on one contract.
8. As a developer, I want node failures to share one error shape, so that graph routing, tests, and frontend events can remain stable.
9. As a developer, I want migration compatibility with flat state fields, so that current checkpoint tests and scaffold graph do not break immediately.
10. As a maintainer, I want events to be accumulated in state first, so that streaming transport can be added without changing node logic.

## Implementation Decisions

- `AgentState` is layered into `task`, `graph`, `context`, `analysis`, `output`, and
  `error`.
- Flat fields such as `task_id`, `trace_id`, `node_id`, `node_status`,
  `resume_cursor`, and `event_seq` remain during migration.
- `request_to_initial_state` adapts `AnalysisTaskRequest` into graph state instead
  of using the API request object directly as runtime state.
- MVP supports exactly one selected dataset.
- If no dataset is explicitly selected, `load_task_context` may use
  `context.recent_dataset_id` and must set `context.inferred_dataset=true`.
- Dataset selection is represented by `selected_dataset_id`, `inferred_dataset`,
  and `dataset_selection_source`.
- `load_task_context` validates task identity, question, access context,
  readonly mode, single dataset selection, and dataset authorization.
- `build_context` consumes `selected_dataset_id`; it does not choose datasets.
- `build_context` requires dataset metadata containing at least `dataset_type`.
  File datasets also require `file_ref`.
- Schema loading uses `ToolCallingRuntime` and registered data-analysis tools:
  `mysql.schema_reader` for MySQL and `file.relation_normalizer` for CSV/XLS/XLSX.
- Existing schema tools allow `build_context` as an authorized node.
- Tool outputs are converted into `SchemaContext`, then passed through
  `ContextBuilder` with the `generate_sql` context policy.
- Business failures write `error.has_error=true` and route to `fail_task`.

## Testing Decisions

- Test the highest practical seam: adapter plus node behavior, not private helper
  internals.
- Verify `request_to_initial_state` maps task identity, access context, request
  source, and empty analysis/output/error layers.
- Verify `load_task_context` accepts one authorized dataset, records selection
  details, emits `task_context_loaded`, and routes to `build_context`.
- Verify `load_task_context` fails multi-dataset, missing dataset, non-readonly, and
  unauthorized dataset cases by writing `error` state.
- Verify `build_context` calls the real tool runtime using a fake registered schema
  tool and emits `context_built`.
- Verify schema tool failures and empty schema responses become stable state errors.

## 当前实现与验证入口

图构建与节点路由见
[数据分析图](../../../src/agent_backend/orchestration/data_analysis/graph.py)，
任务装载和上下文节点分别见 `nodes/load_task_context.py`、`nodes/build_context.py`。
测试定义见 `tests/unit/test_data_analysis_context_nodes.py` 和
`tests/unit/test_data_analysis_graph.py`；本轮未执行这些业务测试。

此说明不承诺 HTTP NDJSON、Java SSE、Kafka worker、跨数据集 join 或持久化记忆驱动的数据集推断。
对应能力须按实际实现和已确认 Spec 另行核对。

## Further Notes

`build_context` currently targets the `generate_sql` context policy because it builds
the next node's prompt-ready context. Later, context can be sliced per node without
changing the public state layers.
