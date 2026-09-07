# 数据分析 Agent MVP 需求文档

> 说明：本文档保留项目级 MVP 范围定义。对于当前首条流式主链的实现方式，请以 `docs/module-breakdown/natural-language-chat-initial-architecture.md` 和各模块子文档为准。

## 1. 文档目的

本文档基于当前仓库结构、既有架构设计和已选技术栈，定义数据分析 Agent 项目的 MVP（Minimum Viable Product，最小可用版本）需求范围，用于统一产品、架构、研发和测试的首版交付目标。

本文档关注的是“第一阶段必须落地什么”，不是企业完整版路线图。

## 2. 项目背景

当前项目定位是一个面向 `CSV / Excel / MySQL` 数据源的数据分析 Agent 平台。用户通过 Web 端提交分析问题，系统自动完成：

1. 数据集选择或上传
2. 权限校验
3. SQL 生成与只读执行
4. Python 数据分析
5. 图表生成
6. 文字结论输出
7. 任务过程流式回传
8. 基础审计留痕

项目已经明确采用 `前端 + Java 主后端 + Python Agent 后端 + 基础设施` 的双后端架构：

- `frontend-web`：用户交互入口
- `backend-java`：认证、权限、任务入口、数据集管理、SSE、审计边界
- `backend-agent`：LangGraph 编排、SQL/图表工具、分析执行
- `infra`：MySQL、Redis、Kafka 和本地启动能力

结合当前目录和代码状态，仓库目前处于“骨架搭建完成、业务能力尚未实现”的阶段，因此 MVP 需求必须以“先打通主链路”为核心。

## 3. MVP 产品目标

MVP 版本要解决的核心问题只有一个：

`让一个已登录、已授权的分析用户，能够针对一个受控数据集发起自然语言分析任务，并在页面上看到任务状态、SQL、图表和最终结论。`

MVP 成功标志：

1. 用户能接入至少一种文件型数据源和一种数据库型数据源
2. 用户能发起一次分析任务并得到结果
3. 系统能保证 SQL 只读、结果可追踪、任务过程可查看
4. 出问题时能定位任务、查看 trace 和基础日志

## 4. 当前目录对应的 MVP 交付范围

### 4.1 `frontend-web`

MVP 需要承载以下页面或区域：

1. 数据集接入区
2. 分析问题提交区
3. 任务流事件展示区
4. 分析结果展示区
5. SQL 展示区

结合当前 `app/`、`components/`、`features/` 结构，首版不要求复杂路由和后台管理台，先以单页工作台模式完成主流程。

### 4.2 `backend-java`

MVP 需要优先落地以下模块职责：

1. `auth`：登录态识别、用户身份、租户和基础角色校验
2. `dataset`：文件上传、数据集注册、Schema 摘要、数据集查询
3. `job`：任务创建、任务状态管理、Kafka 投递、结果接收
4. `gateway`：对前端暴露统一 API
5. `audit`：至少保留基础任务审计和操作留痕

### 4.3 `backend-agent`

MVP 需要优先落地以下能力：

1. `agent_api`：接收任务、健康检查、内部回调
2. `worker`：消费任务并执行分析图
3. `graph_runtime`：最小分析工作流编排
4. `tool_sql`：只读 SQL 生成、校验和执行
5. `tool_chart`：图表配置生成
6. `context_hub`：数据集上下文组装
7. `prompt_hub`：Prompt 模板管理
8. `guardrails`：规则校验和输出约束

### 4.4 `infra`

MVP 需要保证以下本地依赖可运行：

1. `MySQL`
2. `Redis`
3. `Kafka`
4. 本地启动脚本与基础初始化脚本

## 5. MVP 目标用户与使用场景

### 5.1 目标用户

1. `分析师`：上传或选择数据集，输入问题，查看分析结果
2. `管理员`：管理数据集接入、授权、基础运行配置
3. `审核人`
   当前 MVP 仅保留“高风险可挂起”的扩展位，不要求完整人工审批平台

### 5.2 核心场景

1. 用户上传一个 `CSV/Excel` 文件并注册为数据集
2. 用户配置一个只读 `MySQL` 数据源并选择表作为数据集
3. 用户输入自然语言问题，例如“过去 12 个月各月营收趋势如何”
4. 系统自动生成只读 SQL 并执行
5. 系统返回统计结论和折线图/柱状图
6. 前端实时展示任务状态、生成 SQL、图表和结论

## 6. MVP 功能需求

## 6.1 用户与权限

### 需求说明

MVP 需要具备最小权限体系，保证 Agent 不能脱离业务权限边界独立访问数据。

### 必做项

1. 支持基础登录态识别
2. 支持用户、租户、角色三个基本维度
3. 支持数据集级授权
4. Java 在任务下发前生成最小权限上下文
5. Python Agent 只能消费 Java 传入的权限上下文

### MVP 简化策略

1. 不做 SSO
2. 不做复杂组织架构
3. 不做完整行列级动态权限平台
4. 行列权限可先通过静态规则或白名单配置实现

## 6.2 数据集管理

### 需求说明

系统需要提供一个统一的数据集入口，屏蔽底层数据源差异。

### 必做项

1. 支持上传 `CSV`
2. 支持上传 `Excel`
3. 支持配置只读 `MySQL` 数据源
4. 支持数据集注册、列表查询、详情查询
5. 支持展示数据集 Schema 摘要
6. 支持展示样例数据预览
7. 支持为数据集分配授权用户或角色

### 数据集元数据至少包含

1. `dataset_id`
2. `dataset_name`
3. `dataset_type`
4. `source_location`
5. `schema_summary`
6. `owner`
7. `tenant_id`
8. `created_at`
9. `permission_scope`

## 6.3 分析任务创建与执行

### 需求说明

MVP 的主链路是“提交问题 -> 创建任务 -> 异步执行 -> 返回结果”。

### 必做项

1. 用户可选择一个或多个已授权数据集
2. 用户可输入自然语言问题
3. Java 创建任务并生成 `task_id`、`trace_id`
4. 任务上下文写入 MySQL
5. Java 向 Kafka 投递任务消息
6. Python Worker 消费任务消息并启动 LangGraph
7. 任务状态至少包含：
   `queued`、`running`、`needs_review`、`succeeded`、`failed`
8. Java 能接收 Python 回传的最终结果或失败状态

## 6.4 Agent 分析工作流

### 需求说明

MVP 只要求实现最小闭环分析图，不要求一步到位实现全部增强能力。

### MVP 最小工作流

1. `load_task_context`
2. `schema_profile`
3. `build_context`
4. `plan_analysis`
5. `generate_sql`
6. `sql_guard`
7. `run_query`
8. `python_analysis`
9. `build_chart`
10. `write_answer`
11. `persist_result`

### 输出结果至少包含

1. 分析结论文本
2. 执行 SQL
3. SQL 解释或生成理由
4. 图表配置
5. 任务警告信息
6. 执行耗时
7. `trace_id`

## 6.5 SQL 安全与执行约束

### 需求说明

这是 MVP 的核心风控能力，优先级高于复杂分析能力。

### 必做项

1. 只允许 `SELECT`
2. 禁止 `INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE`
3. 限制最大返回行数
4. 限制单次查询超时时间
5. 限制允许访问的数据集和表范围
6. 对高风险 SQL 返回拦截原因
7. 记录最终执行 SQL

### 高风险触发条件示例

1. 访问未授权表
2. 查询疑似敏感字段
3. 未加限制地扫描超大结果集
4. 查询语句包含多语句拼接

## 6.6 Python 分析与图表生成

### 需求说明

MVP 需要证明系统不只是“会写 SQL”，还能够输出可读的分析结果。

### 必做项

1. 对 SQL 结果集进行基础聚合和统计分析
2. 支持生成折线图、柱状图、饼图三类基础图表配置
3. 前端使用图表配置直接渲染
4. 结果为空时返回明确提示，而不是报错

### MVP 简化策略

1. 不做复杂 Notebook 式分析
2. 不做自定义 Python 代码执行开放能力
3. 不做高级可视化编辑器

## 6.7 任务流与结果展示

### 需求说明

用户必须能感知任务在“正在做什么”，否则系统不可用。

### 必做项

1. 前端通过 SSE 订阅任务事件
2. 至少展示以下事件类型：
   `task_started`、`context_built`、`sql_generated`、`query_executed`、`chart_ready`、`task_finished`、`task_failed`
3. 展示任务当前状态和时间戳
4. 展示最终 SQL
5. 展示最终图表
6. 展示最终结论文本
7. 展示错误原因或警告信息

## 6.8 审计与可追踪性

### 需求说明

MVP 不能缺少基础审计，否则无法用于真实数据分析场景。

### 必做项

1. 保存任务创建记录
2. 保存任务发起人
3. 保存所用数据集
4. 保存最终 SQL
5. 保存结果状态
6. 保存 `trace_id`
7. 保存关键时间点
8. 保存失败原因

### 审计字段建议

1. `task_id`
2. `trace_id`
3. `tenant_id`
4. `user_id`
5. `dataset_ids`
6. `question`
7. `sql_text`
8. `status`
9. `result_size`
10. `error_message`
11. `started_at`
12. `finished_at`

## 6.9 运维与可观测性

### 必做项

1. Java 和 Python 提供健康检查接口
2. 关键接口打印结构化日志
3. 任务链路使用统一 `trace_id`
4. 本地环境可通过 `docker-compose` 启动基础依赖
5. 至少具备本地演示数据初始化脚本

### MVP 简化策略

1. 可以先不完整接入 Prometheus / Grafana 大盘
2. 可以先以日志和基础状态接口替代完整指标平台

## 7. 非功能需求

## 7.1 性能

1. 普通分析任务在演示数据规模下应可在 `30 秒` 内返回结果
2. SSE 状态更新应在任务关键节点实时可见
3. 文件上传和任务创建接口应具备基本超时控制

## 7.2 安全

1. 所有数据库分析执行必须为只读
2. Agent 不可绕过 Java 直接使用业务权限
3. 用户只能访问已授权数据集
4. 关键审计数据不可缺失

## 7.3 可维护性

1. 模块边界与当前目录结构一致
2. Java 业务边界保持单体分模块，不提前拆微服务
3. Python Agent 按 `src/agent_backend` 四层组织，具体工具归属 `capabilities/data_analysis/tools/*`
4. 关键链路需要具备基础测试

## 8. MVP 明确不做

以下内容不纳入首版必交付：

1. 长短期记忆的完整产品化能力
2. 外部 MCP Server 大规模接入
3. 多模型路由与成本优化策略
4. 复杂人工审批工作台
5. 高级审计回放系统
6. 多租户企业管理后台
7. 复杂权限策略引擎
8. 自助式可视化报表设计器
9. 微服务化拆分
10. 大规模生产级容灾方案

## 9. MVP 建议接口与页面清单

## 9.1 前端页面

1. 分析工作台首页
2. 数据集接入/列表弹层或侧栏
3. 任务流展示区
4. 分析结果展示区

## 9.2 Java API

1. `POST /api/datasets/upload`
2. `POST /api/datasets/mysql/register`
3. `GET /api/datasets`
4. `GET /api/datasets/{id}`
5. `POST /api/tasks`
6. `GET /api/tasks/{id}`
7. `GET /api/tasks/{id}/stream`
8. `POST /internal/agent/tasks/{id}/callback`

## 9.3 Python API

1. `GET /health`
2. `POST /internal/tasks`
3. `GET /internal/tasks/{id}`

## 10. MVP 验收标准

满足以下条件可视为 MVP 达标：

1. 本地环境能启动 `MySQL + Redis + Kafka + Java + Python + Frontend`
2. 用户能上传一个 `CSV` 并成功注册数据集
3. 用户能配置一个只读 `MySQL` 数据集
4. 用户能从前端提交一个自然语言分析问题
5. Java 能创建任务并向 Kafka 投递消息
6. Python 能消费消息并完成最小分析工作流
7. 前端能实时看到至少 5 个关键任务事件
8. 前端能看到 SQL、图表和最终结论
9. 非法 SQL 或越权访问会被阻断并返回明确原因
10. MySQL 中可查询到对应任务记录和审计字段

## 11. MVP 开发优先级建议

### P0：必须先打通

1. 前端任务工作台骨架
2. Java `auth + dataset + job + SSE`
3. Python `agent_api + worker + graph_runtime`
4. `tool_sql + guardrails`
5. 基础任务审计

### P1：提升可用性

1. `tool_chart`
2. Schema 摘要与数据预览
3. 更完整的任务结果页
4. 本地演示数据和回归测试

### P2：为下一阶段预埋

1. `memory`
2. `mcp_hub`
3. `evals`
4. 人工审核节点

## 12. 结论

针对当前项目的架构、目录层级和技术选型，MVP 的本质不是“做一个全能 Agent”，而是先交付一条可信、受控、可追踪的数据分析主链路。

首版只要完成以下闭环，就已经具备明确业务价值：

`数据集接入 -> 权限校验 -> 分析任务创建 -> 只读 SQL 执行 -> 图表与结论输出 -> SSE 流式反馈 -> 审计留痕`

这条主链路与当前仓库结构完全一致，也最符合现阶段的实施成本和风险控制要求。
