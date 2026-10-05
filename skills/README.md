# 仓库 Skills

本目录是本项目可复用 Agent Skill 的唯一正文与维护入口。先按任务找到分类，再读取其中与当前工作直接相关的 Skill；每个 Skill 只描述自己的具体工作流，不替代根目录 [AGENTS.md](../AGENTS.md) 的边界。

## 分类

| 分类 | 放置内容 | 当前 Skills |
| --- | --- | --- |
| [workflow](workflow/README.md) | 计划、协作、交付和仓库流程 | [plan-before-change](workflow/plan-before-change/SKILL.md) |
| [design](design/README.md) | 架构、领域建模、模块与前端界面设计 | [frontend-design](design/frontend-design/SKILL.md) |
| [implementation](implementation/README.md) | 编码、重构和模块实现 | 暂无 |
| [quality](quality/README.md) | 测试、代码审查、安全和可靠性验证 | 暂无 |

本表和各分类 README 是完整索引：登记分类及其中全部 `skills/<分类>/<skill>/SKILL.md` 正文，
不登记许可证、元数据和辅助资源；正文不符合该层级时检查报错。
新增、移位或删除 Skill 时同步两级索引；维护规则见 [文档一致性维护](../docs/WORKFLOW.md#文档一致性维护)。

按 Skill 的主要工作分类，不按业务模块复制；同一 Skill 只放一个分类。优先扩展已有分类，
当出现已确认的不同工作流时再新增类别，并同步此索引与根 AGENTS 路由。不为预想中的 Skill 建空目录。

本仓库通过根目录 [AGENTS.md](../AGENTS.md) 显式路由 Skill，不配置 Codex 隐式发现入口。
开始任务时按 AGENTS 指定的分类读取对应 Skill；`.agents/` 继续保留给本机使用的 Agent 资源，
不作为本目录的副本或自动发现桥接位置。
