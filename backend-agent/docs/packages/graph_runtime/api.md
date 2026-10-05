# Python Graph Runtime 接口文档

## 当前图构建入口

`build_data_analysis_graph(*, model_client, tool_runtime=None, dataset_metadata_resolver=None, prompt_budget_guard=None)`
构建并编译数据分析 LangGraph。模型客户端为必填依赖；工具运行时、数据集元信息解析器和
Prompt budget guard 可由调用方注入。缺省工具运行时由数据分析工厂构造并校验。

实现：[graph.py](../../../src/agent_backend/orchestration/data_analysis/graph.py)。

节点顺序为：

```text
START
  -> load_task_context
  -> build_context
  -> generate_sql
  -> validate_sql
  -> execute_sql
  -> interpret_result
  -> build_chart
  -> persist_result
  -> END
```

`load_task_context`、`build_context`、`generate_sql` 和 `validate_sql` 可按状态转入
`fail_task`，然后结束。当前主图没有装配 checkpoint、HTTP NDJSON、Java SSE 或 Kafka 消费。

## AgentState 与 checkpoint

`AgentState` 定义在 `src/agent_backend/orchestration/state.py`，由图节点共享和更新。
节点快照模型及辅助能力位于
[checkpoint contracts](../../../src/agent_backend/capabilities/agent_runtime/checkpoint/contracts.py)。
这些能力目前没有自动接入 `build_data_analysis_graph`，不能据此推断任务可从持久化快照恢复。

## 验证入口

当前图的构建与节点路由用例见 `tests/unit/test_data_analysis_graph.py`；上下文节点见
`tests/unit/test_data_analysis_context_nodes.py`。这些路径表示测试定义，不代表本次已运行。
