# Frontend Web

当前实现使用 Vue 3、Vite、TypeScript、Vue Router、Tailwind CSS 与 ECharts；
以 [package.json](package.json) 和实际源码为依据。项目级边界见
[根 AGENTS.md](../AGENTS.md)，前端局部约束见下文。

## 安全与职责边界

- 前端不承担认证、授权、SQL 执行或模型调用的最终决定；数据集、SQL 和审批权限
  以 Java 为准，不直接连接 Python、Kafka、Redis 或数据库。
- 浏览器任务进度只通过 Java 提供的 SSE 消费；以类型化事件处理
  `final_answer`、`task_failed` 等终态，不靠本地猜测完成状态。
- 不把密钥放进浏览器代码或公开环境变量；渲染服务端富文本前完成安全处理。
- 保持页面、复用组件和 `src/lib` 契约的职责边界；按当前 `package.json` 的
  Vue 3、Vite 与 TypeScript 实现；本地生成的提示若与当前依赖冲突，先核对源码。

## 代码入口

- `src/pages` 是路由页面，`src/components` 是复用组件；`src/lib` 保存共享类型、
  mock 数据、状态与适配逻辑，`src/router.ts` 管路由。
- 当前路由包含登录、注册、工作台、数据集、历史与个人资料页面；
  具体已接通的后端接口以代码为准。现有 mock 状态不代表生产授权。
- 登录或注册改动读取 [登录](docs/modules/auth/login/requirements.md) 与
  [注册](docs/modules/auth/register/requirements.md)；工作台和任务展示读取
  [workbench](docs/modules/workbench/requirements.md)。

前端只消费 Java 面向浏览器的接口和 SSE，不自行裁决权限或连接 Python 内部服务。
验证优先执行相关类型检查及构建；单次结果记入 Plan 或交付说明，需要 Agent 重复执行的流程见适用的[quality Skill](../skills/quality/README.md)。
