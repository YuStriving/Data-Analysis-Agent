# 让 docs 下的 README 更适合人阅读

- 日期：2026-10-05
- 类别：governance
- 状态：done
- 描述：改写 `docs/` 下全部 README，用清楚、少术语的中文说明各目录负责什么、读者何时应该查看。
- 授权：用户要求面向人类读者改写 docs 内全部 README，并说明各文件夹/模块的作用。
- 用户审阅确认：2026-10-05；批准范围：改写 `docs/` 下全部六份 README，说明目录职责与阅读方式，保留必要流程和安全规则。
- 适用 Spec：纯文档整理，不改变产品行为或接口契约。

## 背景现状与问题

`docs/` 下目前有六份 README，分别介绍文档总入口、架构、详细设计、Plan、Spec 和验证知识。部分内容直接使用流程术语，初学者不容易知道每个目录解决什么问题、该从哪里开始；总览目录树还列有当前不存在的 `design-docs/agent-runtime/`，并且没有解释 `spec/tool-calling/` 和 Plan 分类子目录。

## 当前需要实现的目标

- 让 `docs/` 下全部 README 使用简单中文，先说明目录用途和阅读入口，再保留必要规范。
- 在 `docs/README.md` 准确说明 docs 当前所有目录和主要子目录的职责，不列不存在的路径。
- 各专题 README 说明本目录包含什么、什么时候使用、相关文档分别负责什么。
- 保留已有行为、Spec/Plan Gate、状态值和安全边界，不因简化文字而改变规则。

## 实施步骤

- [x] 改写 `docs/README.md` 的目录地图与阅读路线，覆盖当前实际存在的顶层和主要子目录。
- [x] 简化 `docs/architecture/README.md`、`docs/design-docs/README.md`、`docs/exec-plans/README.md`、`docs/spec/README.md`、`docs/verify/README.md`，明确各自职责和文件/子目录用途。
- [x] 核对术语解释、各 README 之间的链接和目录树，删除过时路径；保留必要流程约束。
- [x] 运行文档链接检查和 `git diff --check`，记录实际结果。
- [x] 将每一个README需要通俗的描述这个README文件是干嘛的，有什么作用

## 实现后的验证状态

- 结果：通过
- 实际结果：已改写 `docs/` 下全部 6 份 README，以浅白中文说明各目录和主要子目录的用途、入口和文档分工；目录地图与当前文件结构核对一致。
- 实际验证：`python -X utf8 scripts/ci/check-docs.py` 检查 116 份 Markdown 和 257 个本地链接，0 个错误；`git diff --check` 退出码 0；新增/改写的 6 份 README 均无行尾空格。

## 知识沉淀（可选）

- 结论：无可复用结论
