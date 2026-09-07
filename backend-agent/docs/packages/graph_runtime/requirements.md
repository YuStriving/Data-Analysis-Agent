# Python Graph Runtime 模块需求

## 1. 模块定位

`graph_runtime` 是 Agent 的执行编排核心，负责维护状态、节点顺序、节点快照、人工恢复和最终输出。

## 2. 当前能力

当前 MVP graph 包含：

1. `load_context`
2. `checkpoint_node`
3. `write_answer`

`checkpoint_node` 会捕获 `AgentState` 为节点级快照，再恢复快照作为后续执行基线。

## 3. 核心职责

1. 定义 `AgentState`
2. 捕获节点级 checkpoint
3. 从 checkpoint 恢复状态
4. 支持人工确认后恢复
5. 在失败或中断前保留可回放状态

## 4. 快照要求

1. 快照必须包含八个核心字段组。
2. 快照保存 `snapshot_id`、scope 身份、`node_id`、`resume_cursor`。
3. `manual_restore_required` 默认为 `true`。
4. 恢复到崩溃前节点状态后，由上层人工确认再继续。

## 5. 验收标准

1. `capture_checkpoint` 能从 `AgentState` 生成 `NodeCheckpointSnapshot`。
2. `restore_checkpoint` 能恢复节点、游标、热上下文和工具执行信息。
3. 同一节点捕获与恢复后 key 字段保持一致。
4. graph 能执行最小编排链路并产生最终答案。
