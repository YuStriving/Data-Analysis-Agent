# 项目文档导航

这里是项目文档的入口。第一次阅读时，不必从头读完所有文件；先按你要解决的问题找到对应目录。各目录负责不同内容，下面的地图会说明它们分别能帮你做什么。

## 按问题查找

| 你想了解什么 | 从这里开始 | 简单来说 |
| --- | --- | --- |
| 系统由哪些部分组成，各部分如何配合 | [架构文档](architecture/README.md) | 查看系统全貌和模块关系 |
| 设计必须遵守哪些共同规则 | [总体设计约束](DESIGN.md) | 查看项目的长期设计边界 |
| 某个技术方案为什么这样设计 | [详细设计说明](design-docs/README.md) | 查看具体方案及其理由 |
| 用户需要什么功能或接口行为 | [需求说明（Spec）](spec/README.md) | 查看已经确认的需求 |
| 一项改动要按什么顺序完成 | [实施计划（Plan）](exec-plans/README.md) | 查看任务步骤、进度和实际结果 |
| 一次任务怎样开始、实现和交付 | [协作执行流程](WORKFLOW.md) | 查看人与 AI 配合的步骤 |
| 怎样为代码变更执行验证 | [Quality Skills](../skills/quality/README.md) | 查看适用的验证流程；测试代码在对应模块 |

## 文件夹地图

| 文件夹或文件 | 这里放什么、有什么用 |
| --- | --- |
| `architecture/` | 系统地图：说明模块目前怎样连接；目前还没有已确认的全局未来蓝图 |
| `design-docs/` | 具体技术方案：说明方案怎样满足需求、为什么选择它 |
| `design-docs/cross-module/` | 需要 Java、Python 等多个部分共同配合的方案 |
| `exec-plans/` | 任务计划：记录正在做和已经完成的改动 |
| `exec-plans/active/` | 尚未完成的计划，按治理、功能、维护分类 |
| `exec-plans/active/governance/` | 正在进行的规则、文档和协作方式改动 |
| `exec-plans/active/features/` | 正在进行的新功能开发 |
| `exec-plans/active/maintenance/` | 正在进行的修复和维护 |
| `exec-plans/completed/` | 已通过验收的计划，按相同类别归档 |
| `exec-plans/completed/governance/` | 已完成的规则、文档和协作方式改动 |
| `exec-plans/completed/features/` | 已完成的新功能开发 |
| `exec-plans/completed/maintenance/` | 已完成的修复和维护 |
| `spec/` | 已确认的功能和接口要求 |
| `spec/tool-calling/` | 工具调用功能的需求和旧版实施记录 |
| `DESIGN.md` | 整个项目都要遵守的共同设计规则 |
| `WORKFLOW.md` | 任务如何分类、实施、验证和交付 |

任务大小会影响是否需要计划：局部的小改动（Micro）通常免 Plan；需要分步骤完成的任务（Normal）和范围较大或跨模块的任务（Complex）按流程建立 Plan。`governance` 管理规则和工作方式，`features` 增加功能，`maintenance` 修正或维护已有内容。每个分类在 `active/` 和 `completed/` 中都有对应位置。

这里说的“模块”，就是按职责划分的一部分代码。例如 Java 后端负责认证、权限、数据集和任务；Python Agent 负责流程编排、工具与模型调用；前端负责页面和交互。

## 这些文档有什么区别

- **需求说明（Spec）**：说清楚系统应该怎样表现。
- **架构地图**：帮助你找到系统有哪些部分、它们在哪里。
- **详细设计**：解释某个方案怎样工作，以及为什么这样选择。
- **实施计划（Plan）**：安排这一次具体要做的步骤，并记录实际进展和验证结果。
- **验证**：按适用的 quality Skill 执行检查；可执行测试与代码放在对应模块，单次结果记入 Plan 或交付说明。

比如，需求说明回答“要做成什么样”，详细设计回答“采用什么方案”，实施计划回答“这次怎么完成”。不要把计划中的内容写成已经实现，也不要把一次验证结果当成长期规则。

## 从哪里继续

如果你要改某个模块，先看[系统架构地图](architecture/current.md)，再从对应模块 README 找代码和局部说明：

- [Java 后端](../backend-java/README.md)：认证、权限、数据集和任务等服务。
- [Python Agent](../backend-agent/README.md)：Agent 的流程编排、工具和模型调用。
- [前端](../frontend-web/README.md)：页面、交互和服务端事件展示。
- [基础设施](../infra/README.md)：本地及部署所需的容器和服务。
- [脚本](../scripts/README.md)：仓库检查和辅助命令。

改完文档后，从仓库根目录运行 `python scripts/ci/check-docs.py`，确认文档入口和链接有效。具体任务的验证命令和结果记在对应 Plan 或交付说明中。
