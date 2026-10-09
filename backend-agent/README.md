# Backend Agent

本模块是 Python 3.12、FastAPI 与 LangGraph 服务。项目职责与安全边界见[根 AGENTS.md](../AGENTS.md)，当前整体实现进度见[项目现状盘点](../docs/PROJECT-STATUS.md)。模块使用根目录包布局：源码位于 `agent_backend/`，测试位于 `tests/`。

## 目录职责

- `agent_backend/api`：HTTP 等外部入口适配。
- `agent_backend/orchestration`：工作流图、节点与执行状态；数据分析图入口见[数据分析图说明](agent_backend/orchestration/data_analysis/README.md)。
- `agent_backend/agent_runtime`：业务中立的执行控制、提示词模板管理、技能元数据加载和工具调用。
- `agent_backend/capabilities/data_analysis`：数据分析契约、上下文与记忆、SQL 校验、提示词和技能、工具及业务执行装配。
- `agent_backend/foundation`：共享访问上下文与模型客户端、配置和供应商适配；模型模块说明见[LLM 基础模块](agent_backend/foundation/llm/README.md)。
- `tests/`：单元、集成与回归测试。

通用运行时不得导入或按名称分支到具体业务能力。业务策略、资源范围与模型节点配置由图构建和业务装配显式提供。Java 是身份、授权和数据访问范围的最终责任方；Python 只在收到的受限范围内执行分析，SQL 保持只读。

## 按任务查找

| 任务 | 入口 |
| --- | --- |
| 工具注册、调用和授权 | `agent_backend/agent_runtime/tool_calling/`、`agent_backend/capabilities/data_analysis/tools/`；共同边界见[根 AGENTS.md](../AGENTS.md) |
| 分析上下文、提示词和技能 | `agent_backend/capabilities/data_analysis/context/`、`prompting/`、`skills/` |
| 分析 SQL 校验和执行 | `agent_backend/capabilities/data_analysis/guardrails/`、`execution/`、`orchestration/data_analysis/nodes/` |
| 记忆与持久化 | `agent_backend/capabilities/data_analysis/memory/`、`contracts/memory.py` |
| 模型供应商和客户端 | `agent_backend/foundation/llm/` |

## 验证

测试保留在 `tests/`。模块变更优先运行受影响的 pytest 测试和 Ruff；包配置从本目录发现 `agent_backend/`。单次验证结果记入交付说明，文档导航变更后从仓库根目录运行 `python scripts/ci/check-docs.py`。
