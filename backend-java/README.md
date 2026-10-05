# Backend Java

本模块是 Java 21 / Spring Boot 3.5.16 单体；权限、数据集、任务、审计与浏览器 SSE
的最终职责遵循[根 AGENTS.md](../AGENTS.md)；模块结构与实现入口见本 README。

## 模块与代码

- `common` 放跨模块基础设施；`modules/auth` 管认证与令牌，`modules/dataset`
  管数据集注册与元数据，`modules/profile` 管用户资料。
- `modules/job`、`modules/gateway`、`modules/audit` 已有入口和相应的
  [模块需求文档](docs/modules/job/requirements.md)；具体流程是否接通以实现与测试为准，
  不根据规划文档认定已完成。
- 当前代码可见模块服务接口与 `service/impl` 实现分层；控制器依赖服务接口。
  按职责选用 `domain`、`dto`、`repository`、`config` 等目录，业务逻辑留在模块内。

## 按任务阅读

权限及登录查看 [auth 文档](docs/modules/auth/requirements.md) 与安全相关代码；
数据集查看 [dataset 文档](docs/modules/dataset/requirements.md)；
任务或 SSE 查看 [job](docs/modules/job/requirements.md) 与
[gateway](docs/modules/gateway/requirements.md)；审计查看
[audit](docs/modules/audit/requirements.md)。跨 Java/Python 契约同时读取 Agent 模块入口。

相关可执行测试留在模块测试目录；按变更范围运行 Maven 目标测试，
单次实际结果记入 Plan 或交付说明；需要 Agent 重复执行的验证流程见适用的[quality Skill](../skills/quality/README.md)。
