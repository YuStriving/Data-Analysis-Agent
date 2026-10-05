# 集中管理详细设计文档

- 日期：2026-10-05
- 类别：governance
- 状态：done
- 授权：用户明确要求将设计文档迁入 `docs/design-docs/`、分类并更新索引
- 适用 Spec：纯文档治理，不新增业务 Spec；遵循 `docs/DESIGN.md`、`docs/WORKFLOW.md` 与 Plan 工作流

## 目标与范围

将当前仓库中已索引的五份详细设计正文及 Python Agent 包内三份架构设计正文统一迁入 `docs/design-docs/`，按适用范围分类，修正所有当前入口和正文中的本地链接，并更新设计落位规则。

迁移分类：

- `docs/design-docs/agent-runtime/`：context_hub、memory、prompt_hub、tool_calling 的模块设计和架构正文。
- `docs/design-docs/cross-module/`：工具执行与授权的跨模块设计正文。

迁移文件：

- `docs/spec/tool-calling/design.md`
- `backend-agent/docs/packages/context_hub/{design,architecture}.md`
- `backend-agent/docs/packages/memory/{design,architecture}.md`
- `backend-agent/docs/packages/prompt_hub/{design,architecture}.md`
- `backend-agent/docs/packages/tool_calling/architecture.md`

保留原位：总体约束 `docs/DESIGN.md`、系统地图 `docs/ARCHITECTURE.md`、行为契约和实施任务 `docs/spec/`、执行计划、验证记录、模块 README/API/requirements 文档，以及工作区中已删除的历史文档。模块入口保留并链接到集中设计正文。

## 实施步骤

- [x] 将八份设计正文移至分类目录，保持正文内容和现有工作区修改。
- [x] 将总体设计规则更新为所有详细设计正文集中在 `docs/design-docs/`，明确 Spec、Plan、测试记录和模块入口的边界。
- [x] 更新分类索引、仓库导航、Spec/模块入口及迁移正文中的路径引用。
- [x] 在 `docs/tests/` 记录迁移映射、验收命令和实际结果，并更新测试索引。
- [x] 运行文档链接检查并核对所有旧设计路径没有仍作为当前入口引用。
- [x] 完成后将计划归档至 `docs/exec-plans/completed/governance/`。

## 验收方式

- `python scripts/ci/check-docs.py` 通过。
- 新索引按分类列出全部八份设计正文；每份正文可从索引或相关入口访问。
- `docs/spec/`、`docs/exec-plans/`、`docs/tests/` 的职责与位置不因集中设计正文而混淆。
- 文档检查的实际结果记入对应 `docs/tests/` 验收记录；语义核对未证明实现行为，模块设计中的现状与目标仍按各正文声明理解。

## 文档影响与进展

- 文档影响：`docs/DESIGN.md`、`docs/design-docs/`、`docs/README.md`、`docs/ARCHITECTURE.md`、`docs/spec/`、`docs/tests/`、Python Agent 模块入口及设计正文。
- 实际结果：八份正文按 `agent-runtime/` 与 `cross-module/` 分类集中；分类索引与相关入口已更新。`python scripts/ci/check-docs.py` 检查 117 份 Markdown、332 个本地链接，0 错误；索引映射核验为 8 项、无缺失或未登记正文；`git diff --check` 退出码 0。
- 未验证内容：未对设计文档描述的实现行为重新做业务验证；本任务只核验迁移、导航与文档链接。
