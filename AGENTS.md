# 项目协作边界与文档入口

本文件是仓库唯一的全局 Agent 规范入口。默认使用中文；先核对受影响的代码、
现有规范和工作区改动，再按任务读取下方入口。文档与代码不一致时，核实差异，
不得将规划中的能力写成已经实现，也不得用局部文件放宽以下边界。

## 始终适用的边界

- `backend-java` 是认证、授权、租户及数据集访问控制、任务入口、审计和浏览器 SSE
  的最终责任方；`backend-agent` 负责受限上下文内的编排与执行；前端只负责交互与展示。
  浏览器不得直连 Python 内部端点，前端权限提示不构成授权。
- 分析流程只允许只读 SQL。Java 下发最小权限与数据范围；Python 不得扩大范围、
  绕过工具授权及校验，或重新暴露 Java 已屏蔽的数据。敏感操作要可审计，结论要有证据；
  不得输出隐藏推理内容、伪造指标或静默吞掉安全失败。
- 密钥、数据库密码及完整连接信息不得进入前端资源、提示词、事件、日志、记忆、
  测试样例或版本库。基础设施和脚本不得隐式执行破坏性操作或扩大网络暴露。
- 通用与业务职责、模块分层和显式装配遵守[总体设计约束](docs/DESIGN.md)
  及适用模块规范；迁移安全检查时，先接好等效的新路径并验证拒绝场景。
- 任务分类及 Plan 要求遵循[协作执行规范](docs/WORKFLOW.md)，Spec 是否必需遵循
  [Spec 协作约定](docs/spec/README.md)；Micro 免 Plan 不代表免 Spec。已确认行为或契约变化
  必须先更新并确认适用 Spec；
  可重复执行的 Agent 验证流程归入适用的 quality Skill；单次实际结果记入 Plan 或交付说明，
  可执行测试留在模块内。适用的产品代码改动在 Implement 阶段采用 TDD。必要验证通过且记录证据后才能标记完成；
  交付时说明执行结果及未验证项，不把预期写成已通过。

## 按任务阅读

按当前任务查阅下表中的入口，不要求通读文档库。Skills 只读取与任务相关的部分，且不能放宽本文件的边界；模块级技术说明与实现入口见相应模块 README。

| 任务/场景 | 必读入口 | 阅读重点 |
| --- | --- | --- |
| 项目地图与协作执行 | [文档索引](docs/README.md)、[架构文档索引](docs/architecture/README.md)、[协作执行规范](docs/WORKFLOW.md) | 先定位系统视图、任务分类与 Gate，再进入对应模块或专题文档 |
| 仓库修改与计划 | [协作执行规范](docs/WORKFLOW.md)、[plan-before-change](skills/workflow/plan-before-change/SKILL.md)、[Plan 工作流](docs/exec-plans/README.md) | Normal/Complex 先保存 `draft` Plan 并暂停，用户明确审阅确认后才能实施；计划模式只输出方案、不写文件 |
| 需求讨论或范围变化 | [Spec 协作约定](docs/spec/README.md)、适用的事项 Spec | 核对行为契约和确认状态；验收时检查适用的模块测试与 quality Skill |
| 设计或调整模块 | [总体设计约束](docs/DESIGN.md)、[详细设计索引](docs/design-docs/index.md)、[架构文档索引](docs/architecture/README.md) | 定位已确认方案与模块细则；按需读取 [design 分类](skills/design/README.md) 中相关 Skill |
| 实现功能或维护代码 | [implementation 分类](skills/implementation/README.md) | 只使用适用于当前语言和模块的 Skill |
| 测试、审查、安全与可靠性验证 | [quality 分类](skills/quality/README.md) | 只使用与本次验证目标匹配的 Skill |
| 跨任务协作或交付 | [workflow 分类](skills/workflow/README.md)、[Plan 工作流](docs/exec-plans/README.md) | 定位相应 Skill；计划要求遵循任务分类与 Plan 状态规则 |
| Java 权限、数据集、任务或 SSE | [Java 模块入口](backend-java/README.md) | 再读取相应模块文档 |
| Python 图、模型、工具或记忆 | [Agent 模块入口](backend-agent/README.md)、[工具契约 Spec](docs/spec/tool-calling/spec.md) | 工具和授权改动须同时核对工具契约 |
| 前端页面、契约或展示 | [前端模块入口与约束](frontend-web/README.md) | 核对交互、接口契约和展示边界 |
| 基础设施或脚本 | [infra 入口](infra/README.md)、[scripts 入口](scripts/README.md) | 跨模块改动读取双方入口 |
| 通用与业务职责调整 | [架构不变量](docs/DESIGN.md#2-architectural-invariants)、适用模块规范 | 仓库交付规则见[验证与交付](docs/WORKFLOW.md#验证与交付) |

## 完成功能时维护规范

每项功能交付前检查本次变更是否影响全局边界、模块职责、稳定约定或导航目标：
全局规则或入口变化时更新本文件；模块局部边界或实现入口变化时更新对应模块 README；
实现说明变化时更新模块 README 或专题文档；Plan 流程细则变化时更新 `docs/exec-plans/README.md`。
按 [文档一致性维护](docs/WORKFLOW.md#文档一致性维护) 核对受影响索引与正文；
文档导航或目录变化时同步引用，并运行 `python scripts/ci/check-docs.py`。
根文件无需变化时，在交付说明中写明检查结论，不为留下修改记录而增加冗余。
全局架构、Java/Python 职责、只读策略、
安全模型或核心框架的放宽与替换，须先取得用户明确确认。
