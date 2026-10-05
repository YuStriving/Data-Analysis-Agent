# 退役 docs/tests 并统一计划与验证生命周期

- 日期：2026-10-05
- 类别：governance
- 状态：done
- 描述：删除过时的 `docs/tests/` 文档目录，明确 Plan、可复用验证知识、模块测试和 TDD 的职责，为 Plan 生命周期增加机械校验，并统一 Normal/Complex 任务的落库审阅门槛；全仓仅保留根目录 `AGENTS.md` 作为 Agent 地图；补充遗留问题修复后的自动重验与归档规则。
- 授权：用户明确要求按修订方案实施，并确认所有需 Plan 的任务先保存为待审阅状态、收到明确确认后再实施。
- 用户审阅确认：2026-10-05；批准范围：Normal/Complex 落库后等待明确审阅确认，审阅门覆盖仓库 Plan 规范、模板与 Skill。
- 适用 Spec：纯文档治理和 CI 文档检查规则调整，不改变产品行为或契约。

## 背景现状与问题

`docs/tests/` 当前只含索引和一份架构迁移验收记录；对应结果已存在于归档 Plan。`docs/verify/README.md` 仍描述集中保存测试方案和验收记录，并链接多份已不存在的文件，与当前 Plan 和模块测试职责不一致。Workflow 需要区分 Implement 阶段适用代码改动的 TDD 与 Verify 阶段的交付验证 Gate。归档中另有一份状态仍为 `in_progress` 的 Plan 位于 `completed/`。

## 目标

- 删除 `docs/tests/`，不影响模块可执行测试及 `scripts/ci/` 的检查器测试。
- 将单次实际验证结果保留在 Plan 或 Micro 交付说明；`docs/verify/` 只登记确有复用价值的验证知识。
- 明确代码变更在 Implement 阶段使用测试优先；Verify 负责交付前验证并保留失败回路。
- 用 Skill 指引 Plan 生命周期，并由文档检查器校验 active/completed 与 Plan 状态一致。
- 为所有需 Plan 的 Normal/Complex 任务增加落库审阅门：计划模式只输出方案；实施模式先保存 `draft` Plan 并暂停，收到用户明确确认后记录审阅范围与日期、进入 `ready`，再开始实现；Micro 免 Plan。

## 实施步骤

- [x] 重写 `docs/verify/README.md`，定义可复用验证知识的范围，删除指向不存在验收文档的索引项；无合格资产时保持空索引。
- [x] 删除 `docs/tests/` 下的索引与架构验收记录；保留完整归档 Plan 历史。
- [x] 更新 `AGENTS.md`、`docs/WORKFLOW.md`、`docs/exec-plans/README.md` 与模板，统一记录归属，并说明 TDD 在 Implement、Verify 是交付 Gate；纯文档任务不强套 TDD。
- [x] 扩展 `plan-before-change` Skill，在创建、执行、知识分流、验证完成及归档各阶段提供一致指引；模板增加简短知识沉淀字段。
- [x] 更新 `scripts/ci/check-docs.py`，校验 Plan 状态值及 active/completed 路径一致性；在 `scripts/ci/test_check_docs.py` 增加对应规则测试，并处理已归档但标记为 `in_progress` 的计划。
- [x] 在根规范、Workflow、Plan 工作流、Plan 模板和 `plan-before-change` Skill 中同步“计划模式只提案、落库后等待审阅、明确确认后实施”的流程；定义 `draft`、`ready` 状态与审阅记录字段。
- [x] 核对原生 Plan 模式、Normal/Complex 落库暂停、修改后再次审阅、明确批准后实施、Micro 免 Plan、Spec Change Gate 和获批后扩围重新审阅等场景。
- [x] 搜索当前规范与入口中的旧目录引用，检查文档链接，运行检查并记录实际结果。
- [x] 将前端局部 Agent 约束迁入 `frontend-web/README.md`，删除模块级 `AGENTS.md`，使根 `AGENTS.md` 成为唯一 Agent 地图。
- [x] 更新规范、架构图及模块入口中的模块级 `AGENTS.md` 链接；扩展文档 CI，拒绝根目录以外的 `AGENTS.md`。
- [x] 从详细设计索引移除尚无正文的占位条目，不创建未经确认的设计文档。
- [x] 更新 Plan 工作流与 `plan-before-change` Skill：遗留问题解决且必要验收通过后，主动更新原 Plan 的结果与证据、置为 `done` 并归档到 `completed/`，无需等待用户再次提醒。

## 验证状态

- 结果：通过
- 实际结果：`python -B scripts/ci/test_check_docs.py` 通过（44 项）；`rg --files -g AGENTS.md` 仅列出根 `AGENTS.md`；`git diff --check` 退出码 0。移除尚无正文的三条设计索引占位后，`python -X utf8 scripts/ci/check-docs.py` 检查 114 份 Markdown 和 264 个本地链接，0 个错误。根 Agent 地图、TDD 与 Verify 职责、计划审阅 Gate 和遗留问题修复后的主动归档规则均已核对。
- 审阅门子范围结果（2026-10-05）：检查器单测 43 项通过；目标文档无尾随空白，`git diff --check` 退出码 0；文档检查当时报告 4 个错误（一个工作区内的嵌套 Agent 地图规则错误及 3 个缺失详细设计目标），均非本次审阅门规则引入。只读复核确认本次流程范围内无遗留问题。
- 证据：本次命令输出；`git diff --check` 退出码 0。
