# 项目文档导航

这里集中索引当前维护的项目状态、架构决策和 Agent 配置。模块实现说明放在各模块 README 中；按当前任务读取相关入口即可。

## 项目状态与决策

| 你想了解什么 | 从这里开始 |
| --- | --- |
| MVP 当前实现到什么程度、下一步先做什么 | [项目现状盘点](PROJECT-STATUS.md) |
| 为什么简化 MVP 阶段的 Agent 协作约定 | [MVP 协作决策记录](adr/0001-mvp-agent-collaboration.md) |

## Agent 配置

| 你想了解什么 | 从这里开始 |
| --- | --- |
| 仓库通用协作与安全边界 | [AGENTS.md](../AGENTS.md) |
| 任务记录和 GitHub Issues 操作 | [Issue tracker](agents/issue-tracker.md) |
| Agent triage 标签含义 | [Triage labels](agents/triage-labels.md) |
| 项目领域词汇表 | [CONTEXT.md](../CONTEXT.md) |
| 领域词汇与 ADR 的查阅规则 | [Domain docs](agents/domain.md) |

## 按模块查阅

- [Java 后端](../backend-java/README.md)：认证、权限、数据集、任务与审计。
- [Python Agent](../backend-agent/README.md)：流程编排、工具、模型和 SQL 校验。
- [前端](../frontend-web/README.md)：页面、交互与接口调用。
- [基础设施](../infra/README.md)：本地开发及部署所需服务。
- [脚本](../scripts/README.md)：启动、CI 检查与辅助命令。
- [仓库 Skills](../skills/README.md)：可复用的 Agent 工作流。
- [质量 Skills](../skills/quality/README.md)：验证与代码质量工作流。

## 文档验证

从仓库根目录运行 `python scripts/ci/check-docs.py`，检查维护中的必需入口和本地 Markdown 链接。模块测试与验证命令见对应模块 README；单次验证结果记入交付说明。
