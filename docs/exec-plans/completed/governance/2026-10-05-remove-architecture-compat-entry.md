# 移除架构兼容入口并整理 Agent 导航

- 日期：2026-10-05
- 类别：governance
- 状态：done
- 描述：删除不再需要的 `docs/ARCHITECTURE.md` 兼容入口，将架构导航统一指向 `docs/architecture/README.md`，并将根 `AGENTS.md` 的任务阅读导航整理为表格。
- 授权：用户明确要求实施。
- 适用 Spec：纯文档导航调整，不改变业务行为、契约或安全边界，不新增事项 Spec。

## 实施步骤

- [x] 删除 `docs/ARCHITECTURE.md` 兼容页，并从文档目录树中移除该入口说明。
- [x] 将 `AGENTS.md` 的按任务阅读入口整理为表格，明确架构入口指向 `docs/architecture/README.md`，保留现有路由规则。
- [x] 更新根 README 与 `docs/README.md` 的架构导航为架构 README；需要引用当前实现事实的正文继续链接 `current.md`。
- [x] 将 `scripts/ci/check-docs.py` 的必需架构入口和对应测试夹具改为 `docs/architecture/README.md`；更新旧验收记录的后续状态说明。
- [x] 运行 `python scripts/ci/check-docs.py` 与 `git diff --check`，确认没有新增链接错误并记录结果。

## 验证状态

- 结果：通过（本次范围）
- 实际结果：架构导航统一到 `docs/architecture/README.md`；兼容页删除；文档检查维持实施前 3 个失效链接，均为缺失的旧详细设计正文；`git diff --check` 退出码 0。
- 证据：本计划记录本次检查结果；未运行模块或脚本单元测试。
