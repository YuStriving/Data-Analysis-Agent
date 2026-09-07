# MVP 模块文档索引

## 1. 文档目的

本文档用于把 [data-analysis-agent-mvp-requirements.md](C:/Users/17924/Desktop/agent项目/docs/data-analysis-agent-mvp-requirements.md) 拆分到当前项目结构下的最小模块文档中，便于后续按模块开发、评审和测试。

与“自然语言对话 + 流式分析”初版主链相关的总体方案文档位于：

1. `docs/module-breakdown/natural-language-chat-initial-architecture.md`

## 2. 前端模块文档

1. `frontend-web/docs/modules/workbench/requirements.md`
2. `frontend-web/docs/modules/workbench/interface.md`
3. `frontend-web/docs/modules/upload-panel/requirements.md`
4. `frontend-web/docs/modules/upload-panel/interface.md`
5. `frontend-web/docs/modules/task-stream/requirements.md`
6. `frontend-web/docs/modules/task-stream/interface.md`

## 3. Java 后端模块文档

1. `backend-java/docs/modules/auth/requirements.md`
2. `backend-java/docs/modules/auth/api.md`
3. `backend-java/docs/modules/dataset/requirements.md`
4. `backend-java/docs/modules/dataset/api.md`
5. `backend-java/docs/modules/job/requirements.md`
6. `backend-java/docs/modules/job/api.md`
7. `backend-java/docs/modules/audit/requirements.md`
8. `backend-java/docs/modules/audit/api.md`
9. `backend-java/docs/modules/gateway/requirements.md`
10. `backend-java/docs/modules/gateway/api.md`

## 4. Python Agent 模块文档

1. `backend-agent/docs/apps/agent_api/requirements.md`
2. `backend-agent/docs/apps/agent_api/api.md`
3. `backend-agent/docs/apps/worker/requirements.md`
4. `backend-agent/docs/apps/worker/api.md`
5. `backend-agent/docs/packages/graph_runtime/requirements.md`
6. `backend-agent/docs/packages/graph_runtime/api.md`
7. `backend-agent/docs/packages/tool_sql/requirements.md`
8. `backend-agent/docs/packages/tool_sql/api.md`
9. `backend-agent/docs/packages/tool_chart/requirements.md`
10. `backend-agent/docs/packages/tool_chart/api.md`
11. `backend-agent/docs/packages/context_hub/requirements.md`
12. `backend-agent/docs/packages/context_hub/api.md`
13. `backend-agent/docs/packages/prompt_hub/requirements.md`
14. `backend-agent/docs/packages/prompt_hub/api.md`
15. `backend-agent/docs/packages/guardrails/requirements.md`
16. `backend-agent/docs/packages/guardrails/api.md`
17. `backend-agent/docs/packages/memory/requirements.md`
18. `backend-agent/docs/packages/memory/api.md`
19. `backend-agent/docs/packages/observability/requirements.md`
20. `backend-agent/docs/packages/observability/api.md`

## 5. 拆分原则

1. 文档严格对应当前仓库目录，不额外创造不存在的业务层级。
2. 每个模块至少包含一份需求文档和一份接口文档。
3. 需求文档描述职责、边界、核心流程、输入输出和验收点。
4. 接口文档描述 HTTP API、SSE 事件、Kafka 事件或内部函数契约。
5. 当前代码里已有的 `demo` 或 `context-demo` 接口视为骨架接口，不视为最终 MVP 契约。
