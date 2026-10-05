# Backend Agent

本模块是 Python 3.12、FastAPI 与 LangGraph 运行时。安全和职责约束见
[根 AGENTS.md](../AGENTS.md)，模块结构与实现入口见本 README。
这里记录目录导航和已核实的实现入口；专题契约以对应文档、代码和已确认 spec 为准。

## 目录与现状

- `src/agent_backend/api`：HTTP、Kafka 等入口适配；
  `orchestration`：图、状态和节点；`capabilities/agent_runtime`：通用能力；
  `capabilities/data_analysis`：数据分析业务能力；`foundation`：跨层契约与底层适配。
- [数据分析图](src/agent_backend/orchestration/data_analysis/README.md) 已有
  `load_task_context`、`build_context`、SQL 生成/校验/执行及后续结果节点的构图入口。
  图中已装配的节点不等于所有外部工作流、SSE 或审批恢复均已接通。
- [LLM 基础模块](src/agent_backend/foundation/llm/README.md) 说明当前客户端契约、
  配置及尚未接入的环节。模型客户端由入口注入，节点不得直接读取密钥或绑定供应商 SDK。

## 按任务阅读的契约

| 任务 | 细则入口 |
| --- | --- |
| 工具注册、版本、执行与错误 | [tool_calling](docs/packages/tool_calling/README.md)、[已确认工具 spec](../docs/spec/tool-calling/spec.md) |
| 能力、节点、风险及业务资源授权 | [工具执行与授权设计](../docs/design-docs/cross-module/tool-execution-authorization.md)、[执行控制源码](src/agent_backend/capabilities/agent_runtime/execution_control/tool_authorization_gate.py) |
| 上下文及 SQL 生成输入 | [context_hub](docs/packages/context_hub/README.md)、[图运行时](docs/packages/graph_runtime/requirements.md) |
| Prompt 与节点技能 | [prompt_hub](docs/packages/prompt_hub/README.md)、[node_skills](docs/packages/node_skills/README.md) |
| 会话记忆及持久化 | [memory](docs/packages/memory/README.md) |
| SQL 规则和图表结构 | [Guardrails 校验](docs/packages/guardrails/api.md)、[图表 spec](docs/packages/tool_chart/api.md)、[工具执行契约](../docs/spec/tool-calling/spec.md) |

具体业务实现与通用执行的分界见[总体架构不变量](../docs/DESIGN.md#2-architectural-invariants)和[根协作规范](../AGENTS.md)。
工具输入 schema、执行配置、Core Gate、业务资源检查和结构化结果的最终需求
见[工具 spec](../docs/spec/tool-calling/spec.md)；不得从旧文档的未来设想推断功能已落地。

## 验证

可执行测试保留在 `tests/`。影响 Python 运行时时，优先运行对应 pytest 与 Ruff；
单次验证结果记入 Plan 或交付说明；需要 Agent 重复执行的验证流程见适用的[quality Skill](../skills/quality/README.md)。
跨模块全面检查入口见 [scripts/README.md](../scripts/README.md)，按受影响范围使用。
