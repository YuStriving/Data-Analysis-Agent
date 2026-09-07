# Python Graph Runtime 接口文档

## 1. 公开函数

### `build_graph()`

返回已编译的 LangGraph workflow。

当前节点顺序：

```text
START -> load_context -> checkpoint_node -> write_answer -> END
```

### `capture_checkpoint(state, node_id) -> NodeCheckpointSnapshot`

捕获当前 `AgentState` 的八个核心字段组，并生成 `snapshot_id`。

### `restore_checkpoint(snapshot) -> AgentState`

从 `NodeCheckpointSnapshot` 恢复 `AgentState`，保留：

1. `node_id` 与 `resume_cursor`
2. 身份与任务信息
3. 热上下文和确认事实
4. 工具执行摘要
5. 恢复标记与审计序号

## 2. AgentState 关键字段

```python
class AgentState(TypedDict, total=False):
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    session_id: str
    task_type: str
    node_id: str
    node_name: str
    node_status: str
    resume_cursor: str | None
    hot_context: dict[str, str]
    confirmed_facts: list[str]
    conversation_summary: str
    last_tool_name: str | None
    manual_restore_required: bool
    event_seq: int
    snapshot_id: str
```

## 3. 快照事件

checkpoint 捕获可转换为内部事件：

```json
{
  "task_id": "task-1",
  "trace_id": "trace-1",
  "event_type": "checkpoint",
  "timestamp": "2026-09-07T10:00:00+08:00",
  "snapshot_id": "snapshot-1",
  "node_id": "generate_sql"
}
```

## 4. 恢复契约

1. 恢复不得自动继续高风险节点。
2. 恢复必须先经过人工确认。
3. `resume_cursor` 是恢复入口，不能跨任务直接复用。
