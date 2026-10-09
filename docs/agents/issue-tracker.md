# Issue tracker：GitHub

本仓库需要持久跟踪的任务记录在 GitHub Issues，使用仓库根目录中的 `gh` CLI。远端仓库由当前 Git remote 确定。

选择 GitHub Issues 只确定问题记录的位置；是否需要 issue 或额外设计文档，仍按根目录 `AGENTS.md` 和当前任务范围决定。不会因为使用 issue tracker 而强制创建 Spec 或 Plan。

## 常用操作

- 创建：`gh issue create --title "..." --body "..."`
- 查看：`gh issue view <number>`
- 列表：`gh issue list --state open`
- 评论：`gh issue comment <number> --body "..."`
- 关闭：`gh issue close <number>`

## Pull Request

Pull Request 不作为 triage 请求入口。
