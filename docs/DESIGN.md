# 总体设计约束与导航

## 1. 文档定位与事实边界

本文是项目级规范性架构文档（normative），定义长期有效的架构不变量；实现应满足这些约束。
若当前实现与约束不一致，应记录为实现偏差并核实原因，不应仅为迁就现有代码而改写约束。
修改架构原则须按适用协作流程讨论并确认。

[当前架构地图](architecture/current.md) 是描述性文档（descriptive），记录当前已核实的结构、依赖、实现缺口和技术债。某种实现已经存在，不代表它因此成为架构规则。

| 文档 | 权威内容 |
| --- | --- |
| [Spec](spec/README.md) | WHAT：可观察行为、输入输出、错误、兼容要求和验收标准 |
| 本文 | 项目级稳定架构约束及不可突破的边界 |
| [详细设计](design-docs/index.md) | 具体机制的职责、依赖、状态与数据流，以及设计取舍；不得放宽本文的不变量 |
| [Plan](exec-plans/README.md) | 本次改动的位置、实施顺序、进度与验证安排 |
| [当前架构地图](architecture/current.md) | 当前已核实的实现结构和偏差 |

| [AGENTS.md](../AGENTS.md) | 唯一的 Agent 协作边界与执行地图；模块 README 提供局部入口和实现说明 |
| [WORKFLOW.md](WORKFLOW.md) | 任务分类、执行与交付流程 |

设计目标、代码现状和验证证据彼此不能替代：设计存在不代表实现完成，实现存在不代表验证正确，历史验证也不代表本次修改已通过。

## 2. Architectural Invariants

以下规则是项目级架构约束。模块 README 可以提供局部执行说明，但不能放宽这些不变量。

### ARCH-001 授权与数据范围

Java 持有身份、授权和数据访问的最终决定权，并向 Python 提供完成当前任务所需的最小权限与数据范围。Python 只能在该范围内编排和执行，不得扩权或重新暴露已屏蔽的数据；分析查询保持只读 SQL。前端只展示并通过 Java 提供的接口交互，不承担授权。

工具的具体授权契约见[工具 Spec](spec/tool-calling/spec.md)与[工具执行设计](design-docs/cross-module/tool-execution-authorization.md)。

### ARCH-002 权威状态有明确所有者

每个权威业务事实都必须有明确的所有者。缓存、前端状态和派生字段可以作为投影或加速手段，但不能反向覆盖权威事实，也不能产生或扩大授权。相关设计原则见[核心设计信念](design-docs/core-beliefs.md#2-状态有明确所有者派生视图不变成第二份事实)。

### ARCH-003 Python 通用能力与业务装配分离

通用 Agent 执行层不得直接导入、构造或按业务名称分支到具体业务实现。业务工具、资源适配和策略必须通过入口、工厂、配置或图构建过程显式提供；通用层只依赖稳定契约并执行被装配的能力。执行授权的职责分层见[工具执行设计](design-docs/cross-module/tool-execution-authorization.md)，实现入口见 [Python Agent README](../backend-agent/README.md)。

### ARCH-004 Java 业务模块保持清晰归属

业务规则归属于对应业务模块；Controller 通过服务接口调用业务逻辑，不直接承载业务规则。`common` 只容纳稳定共享契约或不带具体业务语义的跨模块基础设施，不因多个模块暂时需要而下沉业务规则。模块入口见 [Java README](../backend-java/README.md)。

## 3. 契约、安全与实现偏差

具体输入输出、错误和兼容行为由适用 Spec 定义；架构设计说明由哪些职责和依赖满足这些契约。安全实施细则遵循根及模块规范；其他文档不得以摘要、展示或缓存放宽本文规定的数据与授权边界。

发现实现偏离不变量时，在[当前架构地图](architecture/current.md)或适用模块说明中记录当前事实与缺口，并提供验证依据；不要把偏差写成新规则。只有经确认的架构决策变化才更新本文。

## 4. 设计文档治理

本节是本仓库的文档管理约定，不是 Architectural Invariant。详细设计正文集中在 `docs/design-docs/`，按[设计索引](design-docs/index.md)分类和导航；模块 README、API 与需求文档仍可保留在模块目录作为局部入口。Spec 保留行为要求，Plan 记录实施过程及单次验证结果，可执行测试与代码同放模块；Agent 需要重复执行的验证流程归入适用的 quality Skill。

每份详细设计正文在元信息中记录设计状态，沿用模板中的 `proposed`、`accepted`、`deprecated` 和 `superseded`；设计索引只负责导航、范围和适用说明，不重复登记状态。状态变化需在正文记录明确依据：`accepted` 需有确认记录，`deprecated` 和 `superseded` 需有明确的弃用或替代决定，`superseded` 还须链接替代设计。代码已实现、文档过时或文件更新时间均不构成状态依据。替代关系和历史验证按适用文档保留。

## 5. 修改设计时的最小核对

修改前阅读适用 Spec、[当前架构地图](architecture/current.md)、相关设计正文，并确认受影响的 Architectural Invariants。修改后检查设计要求、实现状态与验证证据没有混写，更新受影响的设计索引和导航链接；具体协作步骤遵循 [WORKFLOW.md](WORKFLOW.md)。文档变更运行 `python scripts/ci/check-docs.py`；涉及代码行为时另运行适用的模块测试。
