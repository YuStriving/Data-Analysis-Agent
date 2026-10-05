# 详细设计索引

第一次阅读本目录，请看[目录说明](README.md)。本页只负责查找详细设计正文及其适用范围。
总体约束与导航见 [DESIGN.md](../DESIGN.md)，系统地图见
[当前架构地图](../architecture/current.md)。新建详细设计正文时可从[架构设计模板](template.md)
复制并按适用性裁剪。详细设计正文统一存放在本目录，并按主题分类；
本索引负责正文导航、范围和适用说明；每份设计正文在元信息中记录自己的设计状态。
索引不替代 Spec 中的行为契约，也不证明设计已实现。
原则及理由见 [核心设计信念](core-beliefs.md)。

## Agent Runtime

目前尚无已登记的 Agent Runtime 详细设计正文。模块 README、API 与需求文档仍在
模块目录，作为局部导航和契约入口；只有形成实际设计正文后，再添加对应分类与索引条目。

## 跨模块设计

| 主题 | 设计正文 | 负责范围与解决的问题 | 权威依据与验证 |
| --- | --- | --- | --- |
| 工具执行与授权 | [工具调用设计](cross-module/tool-execution-authorization.md) | Python 通用执行与数据分析业务装配；接收 Java 授予的范围；说明 Core Gate、业务资源检查与执行顺序 | 行为与接口以[工具 Spec](../spec/tool-calling/spec.md)为准；可执行测试见模块测试目录 |

## 模块需求与局部入口

| 范围 | 入口 | 使用方式 |
| --- | --- | --- |
| Java | [模块说明](../../backend-java/README.md)、[任务需求](../../backend-java/docs/modules/job/requirements.md)、[数据集需求](../../backend-java/docs/modules/dataset/requirements.md) | 定位任务、数据集与权限的现状和目标；现有需求文档不等于已完成的跨模块设计 |
| Python Agent | [模块说明](../../backend-agent/README.md)、[执行控制需求](../../backend-agent/docs/packages/execution_control/requirements.md)、[图运行时需求](../../backend-agent/docs/packages/graph_runtime/requirements.md) | 定位图、节点、工具及执行策略；结合适用契约、源码和测试核实 |
| 前端 | [模块说明](../../frontend-web/README.md)、[工作台需求](../../frontend-web/docs/modules/workbench/requirements.md)、[工作台接口](../../frontend-web/docs/modules/workbench/interface.md) | 定位交互、状态与 Java 接口/SSE；规划接口与 mock 展示需区分当前实现 |

## 新增与维护

所有详细设计正文（包括模块内部设计和跨模块方案）统一放在 `docs/design-docs/`，
按主题归入子目录并登记在本索引。模块 README、API、需求和 AGENTS 等局部文档可以留在
模块目录，但只作为入口、契约或模块规范，不另存一份详细设计正文。模块关系的目标架构文档另见
[架构文档索引](../architecture/README.md)。Spec 保留行为要求，
Plan 记录实施顺序、实际结果和未验证项；可执行测试与代码同放模块，Agent 需要重复执行的验证流程归入适用的 quality Skill。

仅在有实际设计内容时建立正文，不为目录完整性创建空文档。新增条目标明主题、正文、
负责范围和适用说明；设计状态记录在正文元信息中，不在索引重复维护。正文说明现状依据、目标与非目标、职责与流程、契约、错误及安全边界、
取舍和验证入口。模板中的设计状态使用 `proposed`（未确认）、`accepted`（已确认）、
`deprecated`（不再推荐但保留参考）或 `superseded`（已有替代设计）；设计状态与实现状态
分开记录。状态变化需有明确依据：`accepted` 需有确认记录，`deprecated` 与 `superseded` 需有弃用或替代决定，`superseded` 还须链接替代设计。代码已实现、文档过时或文件更新时间均不构成依据。没有对应实现或验证证据时不写成完成。
设计之间存在替代关系时注明适用范围及切换条件。移位、替代或范围变化时同步本索引和引用，
