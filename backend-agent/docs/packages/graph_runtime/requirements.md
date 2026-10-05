# Python Graph Runtime 模块需求

## 1. 模块定位

`graph_runtime` 是 Agent 的执行编排核心，负责维护状态、节点顺序和图级路由；节点快照由独立 checkpoint 模块提供。

节点级 checkpoint 的模型、存储协议和恢复辅助函数归属
`agent_runtime.checkpoint` 独立模块；`orchestration` 只负责编排调用，不再从
memory 模块获取 checkpoint 合约。

## 2. 当前能力

当前 `build_data_analysis_graph` 装配以下节点：

节点装载与上下文构建的历史实现说明见
[load_task_context/build_context](load-task-context-build-context-spec.md)。

1. `load_task_context`
2. `build_context`
3. `generate_sql`
4. `validate_sql`
5. `execute_sql`
6. `interpret_result`
7. `build_chart`
8. `persist_result`
9. 统一失败出口 `fail_task`

成功路径按上述顺序执行；前四个可路由节点可转入 `fail_task`。当前图没有在节点间
自动调用 checkpoint，也没有接入 HTTP 流式传输或 Kafka worker。

## 3. 核心职责

1. 定义并传递分层 `AgentState`。
2. 构建数据分析节点及其条件路由。
3. 由独立的 `agent_runtime.checkpoint` 模块提供快照能力；当前图未自动装配该能力。
4. 通过 `fail_task` 统一保留可预期业务失败。

## 4. 快照要求

快照字段和恢复边界以 [Checkpoint 契约](../../../src/agent_backend/capabilities/agent_runtime/checkpoint/contracts.py)
及 checkpoint 用例为准；本需求文档不把快照能力描述成已集成进 LangGraph 主图。

## 5. Checkpoint 模块的独立验收依据

以下是 checkpoint 模块用例目标，不表示数据分析图已经集成快照与恢复。

1. `capture_checkpoint` 能从 `AgentState` 生成 `NodeCheckpointSnapshot`。
2. `restore_checkpoint` 能恢复节点、游标、热上下文和工具执行信息。
3. 同一节点捕获与恢复后 key 字段保持一致。
4. graph 能执行最小编排链路并产生最终答案。
