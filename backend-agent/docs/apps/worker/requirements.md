# Python Worker 模块需求

## 1. 模块定位

`api/kafka` 负责第二阶段的异步执行调度，是 Python Agent 面向 Kafka 的执行入口。

## 2. 当前代码现状

当前 `src/agent_backend/api/kafka/worker.py` 仅完成 `build_graph()` 调用和启动打印，尚未接入 Kafka、重试和回调逻辑。

## 3. 核心职责

1. 订阅 Kafka 任务消息。
2. 反序列化任务事件。
3. 构造初始 `AgentState`。
4. 调用 `graph_runtime`。
5. 处理执行成功、失败和重试。
6. 将结果回调给 Java。

## 4. MVP 功能需求

初版不要求 Worker 进入主链。

初版主链采用：

1. Java 直接调用 `agent_api` 的流式执行接口。
2. `agent_api` 直接驱动 LangGraph。

Worker 作为第二阶段能力保留，届时需要：

1. 支持消费 `analysis.task.created`
2. 支持将任务状态更新为 `running`
3. 支持 graph 执行成功后回调最终结果
4. 支持 graph 执行失败后回调失败原因
5. 支持有限次自动重试
6. 支持输出关键中间事件

## 5. 失败处理要求

1. 区分可重试异常与不可重试异常。
2. 超过重试上限后将任务标记为 `failed`。
3. 回调时必须附带 `trace_id`。

## 6. 边界约束

1. 不负责业务权限生成。
2. 不直接暴露对外 HTTP 接口。
3. 不负责长期记忆产品化。

## 7. 验收标准

第二阶段验收标准：

1. Kafka 有消息时 Worker 能拉起任务执行。
2. 执行完成后 Java 端能收到结果回调。
3. 执行失败后任务状态可追踪。
