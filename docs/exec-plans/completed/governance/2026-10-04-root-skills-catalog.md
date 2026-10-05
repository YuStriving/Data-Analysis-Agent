# 仓库 Skills 分类与路由

- 日期：2026-10-04
- 类别：governance
- 状态：done
- 授权：用户明确要求建立根目录 skills 分类、归档现有 Skill、更新 AGENTS 路由。
- 适用 Spec：纯协作治理，按 Spec 协作约定免新业务 Spec。
- 影响范围：根目录 skills 分类与索引、plan-before-change Skill 位置、根 AGENTS/文档路由、.gitignore。

## 现状与目标

项目现有唯一自定义 Skill `plan-before-change` 位于 `.agents/skills/`，并由根 AGENTS 引用。
将完整 Skill 内容与元数据归档到 `skills/workflow/plan-before-change/`；
由根 `AGENTS.md` 显式路由到根目录分类索引和对应正文，不配置自动发现入口。
建立小而稳定的分类导航，当前只归档实际存在的 Skill。

## 分类

- `workflow/`：任务计划、协作执行与交付流程。本次 `plan-before-change` 归此类。
- `design/`：架构、领域建模和模块设计方法。
- `implementation/`：编码、重构与模块实现工作流。
- `quality/`：测试、代码审查、安全与可靠性验证。

根 `skills/README.md` 登记分类、用途、当前条目和增加类别的规则；分类各自以短 README 说明用途，不为未来 Skill 建空包。出现实际重复需求后再增加条目或类别。

## 实施步骤

- [x] 在 `skills/` 保存分类索引，并建立四个类别目录及简短说明。
- [x] 将完整 Skill 指令、openai.yaml 和必要资源归档到 `skills/workflow/plan-before-change/`。
- [x] 移除为本任务临时建立的 `.agents/skills/plan-before-change/` 自动发现适配器。
- [x] 更新根 AGENTS 规则与按任务路由，使仓库修改任务手动读取 workflow 分类下对应 Skill；Skill 根目录是唯一内容来源。
- [x] 更新 `.gitignore`：根 `skills/` 纳入管理，`.agents/` 继续作为本地资源整体忽略，不为 Skill 增加自动发现例外。
- [x] 验证相对链接、Skill 校验和人工路由；修复两处旧 Skill 路径后记录实测结果。
- [x] 归档到 completed/governance 并检查归档后链接。

## 方案取舍与验收

分类采用 workflow、design、implementation、quality 四类，按 Skill 的主要工作归类，不按项目模块创建目录。
根目录保证人和 Agent 有稳定分类与路由；根 AGENTS 显式指向唯一正文，客户端不自动发现这些项目 Skill。
内容只维护在根目录归档位置，避免索引、Agent 路由与 Skill 正文互相复制流程规则。

验收：从根 AGENTS 可路由到分类索引、分类目录和规范 Skill 正文；不配置 `.agents` 自动发现；Skill 元数据通过校验；Git 忽略本地 `.agents`，根 Skills 纳入管理；文档检查零错误。

## 进展与结果

- 2026-10-04：用户明确选择由根 AGENTS 路由，不使用隐式发现；据此调整方案，移除本次临时发现适配器，保留 `.agents/` 整体忽略。
- 2026-10-04：建立根 skills 分类与导航；完整 Skill 及资源已从 `.agents` 移至 `skills/workflow/`；根 AGENTS 与 docs 索引已加显式路由。
- 2026-10-04：根 Skill 格式通过官方 quick_validate；静态路由、四类分类、正文来源和 Git 忽略检查通过。首轮文档检查发现两处历史旧路径，已改为根 Skill 正文，等待最终复验。
- 2026-10-04：最终文档检查为 117 份 Markdown、301 个本地链接、0 错误；quick_validate 通过。SKC-01～05 的结果和适用边界以本计划验收与交付记录为准；原独立验收报告已删除。
- 2026-10-04：从 active/governance 归档至 completed/governance，归档目标原先不存在；最终路径验证完成。未创建分支、提交或 PR。
