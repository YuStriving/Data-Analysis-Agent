# MVP 项目现状盘点

更新日期：2026-10-09

本文是代码与现存需求文档的状态快照，用来区分目标、已有实现和工作区中的未验证改动，不是新的 Spec 或实施计划。盘点采用静态检查，未运行测试、构建或端到端流程。

## 结论

项目已实现用户注册登录、令牌与权限上下文，以及文件上传和 MySQL 注册等基础能力；Python Agent 也已有分析图、模型调用、SQL 校验和工具运行时等组件。工作台到后端任务处理的主链尚未接通，当前不能据此判断数据分析 MVP 已可端到端使用。

工作台需求记录的目标链路是：选择已授权数据集 → 输入问题 → 创建任务 → 订阅 Java SSE → 展示 SQL、回答和图表，并在任务结束后恢复结果。2026-10-09 已确认首个 MVP 的范围更窄：单个用户针对一个已授权的 MySQL 数据集提问，执行只读 SQL 并返回真实分析结果；流式进度、图表和任务历史暂缓。首条真实任务使用同步请求还是非流式任务接口、结果响应包含哪些字段，仍需在接口实现前确认。

## 主链路状态

| 环节 | 状态 | 代码证据与缺口 |
| --- | --- | --- |
| 注册、登录、登出、刷新和当前用户 | 代码已实现，本次未运行验证 | [AuthController](../backend-java/src/main/java/com/dataagent/platform/modules/auth/controller/AuthController.java) 提供对应路由；前端 [auth.ts](../frontend-web/src/lib/auth.ts) 调用认证接口。 |
| 任务权限上下文 | 接口和部分能力已实现，任务接入未完成 | Java 有 `/api/auth/access-context` 路由；真实任务创建路径尚未接入此上下文。 |
| 文件数据集上传 | 部分实现 | [DatasetServiceImpl](../backend-java/src/main/java/com/dataagent/platform/modules/dataset/service/impl/DatasetServiceImpl.java) 将文件上传到对象存储并返回 `REGISTERING`；当前路径没有保存 Dataset 元数据，因此不能视为已完成数据集注册。 |
| MySQL 数据源注册 | 部分实现 | 同一服务会探测连接与表结构、加密保存凭据；当前没有强制验证所用数据库账号只读。数据集列表、详情、预览和授权查询也没有真实路由。 |
| 工作台提交与展示 | 当前为 mock | [workspace-store.ts](../frontend-web/src/lib/workspace-store.ts) 的 `submitTask` 使用 `buildScenarioTask` 和定时器生成本地事件，没有请求真实任务创建或 SSE 接口。 |
| Java 任务生命周期和 SSE | 演示接口，真实任务链未实现 | [JobController](../backend-java/src/main/java/com/dataagent/platform/modules/job/JobController.java) 只有 `GET /api/jobs/demo`；真实创建、持久化、详情查询和事件流缺失。 |
| Python 接收任务 | 仅返回 accepted | [main.py](../backend-agent/agent_backend/api/http/main.py) 的 `POST /internal/tasks` 返回 `accepted`，没有调用分析图。 |
| Python 分析图 | 图结构、上下文构造、SQL 生成与校验已实现；真实查询链未完成 | [graph.py](../backend-agent/agent_backend/orchestration/data_analysis/graph.py) 装配分析节点。`execute_sql`、`interpret_result`、`build_chart` 和 `persist_result` 当前都是占位节点，只记录节点进入。 |
| 前端 SSE、结果恢复和历史任务 | 未连接真实后端 | 工作台接口文档定义了目标接口，当前代码中的任务流仍由 mock 驱动。 |

因此，当前更准确的描述是“基础能力和 Agent 组件已有，端到端分析任务尚未完成”。单个组件有实现或测试文件，不等于这些能力已经通过真实服务联调。

## 已确认的首个 MVP 范围

- 一个登录用户只分析一个已授权的 MySQL 数据集。
- 后端在授权范围内执行只读 SQL，并返回基于真实查询结果的分析结论。
- 首期不要求流式进度、图表和任务历史恢复；这些能力不是本次首个闭环的验收条件。
- MySQL 注册现状没有强制只读账号，因此在执行真实查询前，必须先落实并验证只读保护。
- 具体请求方式、任务状态处理和结果响应字段尚未确认；实现前需以最小接口方案说明取舍，不借此扩展首期功能。

## 已记录的目标设计与文档缺口

- [Java Job 需求](../backend-java/docs/modules/job/requirements.md) 把 Java → Python HTTP、Python → Java NDJSON、Java 向浏览器转发 SSE 记为初版目标；Kafka 被列为后续阶段。文档明确标注任务创建和 SSE 尚未实现。
- [工作台需求](../frontend-web/docs/modules/workbench/requirements.md) 明确标注当前仍使用 mock，并列出计划中的真实任务接口和流式展示。
- [数据集需求](../backend-java/docs/modules/dataset/requirements.md) 明确区分已实现和未实现路由，但“上传并完成注册”的验收尚未满足：文件上传代码目前没有保存 Dataset 元数据；MySQL 注册也没有强制只读账号。
- 根目录的架构、总体设计和协作流程文档已删除；[docs 导航](README.md) 仍保留对已删除页面的链接，[Backend Agent README](../backend-agent/README.md) 也仍引用已删除的 Spec、设计和 Plan 页面。历史架构决策因此无法仅凭当前文档完整还原。
- 当前没有一份统一文件把本期 MVP 的必选能力、验收方式和延期项集中起来。本盘点把工作台需求中描述的闭环作为候选目标，不把其中每项都宣布为已确认的首发范围。

## 当前分支与未提交改动

- 分支：`codex/foundation-llm-client`；当前提交：`b517346 chore: align project docs and implementation`。
- 本盘点开始时，Git 工作区有 365 项状态记录：27 项修改、199 项删除、139 项未跟踪。改动集中在 `backend-agent` 和文档；这些改动未提交，且本次没有验证其完整性。
- Python 包呈现整体路径迁移：旧的 `backend-agent/src/agent_backend/` 有 135 个删除项，新的 `backend-agent/agent_backend/` 有 136 个未跟踪文件；`pyproject.toml` 已切到根目录包布局。这更像目录迁移，而不能单凭 Git 统计认定功能代码被删掉。
- 迁移还没有形成可信的验证基线：[CI 工作流](../.github/workflows/ci.yml) 的 Ruff 检查仍指向旧的 `src/agent_backend/` 路径。当前没有运行 CI、Ruff 或 Python 测试来确认迁移结果。
- 工作区另有大量旧文档删除。当前统计不能说明这些删除均已完成审核；保留或重建应依据这次状态盘点和实际需求逐项决定，不应按删除行数推算功能进度。

## 建议的下一步

1. 先保留并审查这批 Python 根包迁移和文档删除；不要在尚未理解这 365 项改动前叠加新功能。
2. 迁移有了可信基线后，实现单用户、单个已授权 MySQL 数据集的真实只读查询和结果返回。写查询前落实只读保护，并覆盖未授权数据集、写 SQL 和查询失败场景。
3. 开工实现之前，简要确认 Java 到 Python 的请求方式与结果响应字段。首期按已确认范围交付，不把流式进度、图表或任务历史自动加回验收。
4. 按验证结果更新本文件和受影响的模块 README。只把真实、难以逆转且需要解释的架构取舍记录为 ADR，不为每个功能额外创建 Spec 或 Plan。

## 本次盘点的验证范围

- 本文档的 13 个本地 Markdown 链接均存在，`git diff --check -- docs/PROJECT-STATUS.md docs/README.md` 通过。
- `python scripts/ci/check-docs.py` 报告 33 个失效入口或链接；对比新增本文档前的检查结果，这些错误均已存在，本次没有增加错误。
- 本次只做静态代码与文档检查，未运行测试、编译、CI 或端到端流程，因此不能据此判断服务当前可启动或主链路可运行。
