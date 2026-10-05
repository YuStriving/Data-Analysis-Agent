# 通用 Tools 调用契约设计

关联 [spec.md](../../spec/tool-calling/spec.md)；可执行拒绝路径测试见
[执行器测试](../../../backend-agent/tests/unit/test_tool_executor.py) 与
[Gate 测试](../../../backend-agent/tests/unit/test_tool_authorization_gate.py)。

## 元信息

- **Status**: proposed
- **Status Rationale**: 截至 2026-10-05 未找到明确的设计确认记录；已存在实现不作为确认依据。

## 职责

- tool_calling：最小契约、注册、输入输出校验、同步/异步执行、超时、错误包装。
- execution_control：统一 ToolAuthorizationGate，复用 AgentSpec 与 ToolAccessPolicy。
- data_analysis/tools：DatasetScope、DataAnalysisToolExecutionContext、资源及 SQL 授权策略。
- 数据分析工厂与图节点：显式装配 Gate、执行配置、资源依赖和调用上下文。
- Java：权限来源。Tool 不决定调用者资格，保留业务不变量。

## 接口

```python
class BusinessTool(Protocol):
    name: str
    description: str
    input_args: dict[str, Any]
    def execute(self, args: dict[str, Any], context: ToolExecutionContext) -> Any: ...

ToolAuthorizationGate.check(tool, args, context) -> None
ToolExecutor(*, options: ToolExecutionOptions, authorize: AuthorizationCheck)
await executor.execute(tool, raw_input, context)
```

授权通过返回 None，拒绝抛 ToolCallError。Gate 注入 AgentSpec 查询、策略查询和业务检查，
不导入具体业务模块。独立执行器也必须提供授权方法。
授权回调和业务检查均为同步检查；执行器与 Gate 只接受 None，返回布尔值或 awaitable
均以 Invalid authorization check 拒绝，Tool 不执行。误返回的 coroutine 会被关闭，避免
未等待警告。异步业务工具仍按 TC-007 支持，异步授权回调不属于本次接口。

## 数据契约

| 模型 | 内容 |
| --- | --- |
| ToolExecutionContext | 调用及任务身份、tool_version、Agent/节点、goal、purpose、permissions、可选超时 |
| DataAnalysisToolExecutionContext | 通用上下文扩展及 DatasetScope |
| ToolCallRequest | tool_name、args、context；tool_version 读取 context，避免重复存储 |
| ToolExecutionOptions | version、output_schema、timeout_ms |
| ToolCallResult | 原成功四字段 |

DatasetScope 位于业务 contracts.py，权限位于通用 context。内部直接传递具体上下文对象，
序列化保留业务字段；从外部字典恢复业务类型属于业务入口职责。

goal 取 task.question；purpose 由节点提供。Java 下发的 allowed_dataset_ids 与 readonly
约束资源范围，只沿用既有只读分析委托语义映射内部权限。身份不一致或非只读上下文拒绝。
输入参数、goal、purpose 均不能产生权限。

## 执行顺序及配置

查找工具与配置 → 解析输入 → schema 校验 → Gate → Tool.execute → 输出校验 → 成功包装。
Runtime 取得固定配置后创建执行器，执行器不查询注册表。上下文版本必须匹配配置版本。
上下文超时优先，否则采用配置值。业务策略纯检查，不修改已校验输入或权限。
已有 ToolCallError 原样传播；取消向上传播；不自动重试。展示、事件和恢复由外层负责。

## 迁移

先接好 Gate 与原业务检查，再移除重复授权判断。迁移现有调用位置和执行控制请求读取。
不改变 Java 任务入口、不迁移可执行测试、不引入新的工具框架。
同步线程超时不能强制终止线程，调用方不能假定底层工作已停止。

## 设计理由与取舍

| 决策 | 为什么采用 | 替代方案及代价 |
| --- | --- | --- |
| 通用执行器与业务检查显式组合 | 注册、校验、超时能复用；业务数据集与 SQL 规则保持在业务模块，拒绝路径可单独检查 | 每个工具复制授权流程易漏检查；通用执行器按业务名称分支会反向依赖业务 |
| 授权接受同步 None 或抛异常 | 未配置、未知策略、错误返回都不能落入执行路径；避免把 bool 或未等待协程误判为通过 | 隐式真值判断含糊；异步授权需独立明确契约，不是本次接口 |
| 输入校验 → Gate → 执行 → 输出校验 | Gate 检查规范化输入；被拒绝工具不执行，未通过输出契约的结果不包装成成功 | 先执行再授权不能撤销资源访问；只依赖工具自身检查易产生独立调用绕过路径 |
| 配置在 Runtime 解析，版本从上下文读取 | 调用链共享同一版本来源，Executor 不自行查询业务注册表 | 请求与上下文重复保存版本会增加冲突；执行器自行查配置会隐藏装配依赖 |
| 错误上抛、取消传播，不自动重试 | 外层掌握任务状态、审计与重试语义；通用层无法判断副作用或重试许可 | 自动重试可能重复执行；吞错转成功会损失拒绝与失败证据 |

## 实现依据与验证限制

2026-10-04 静态核对 [Executor](../../../backend-agent/src/agent_backend/capabilities/agent_runtime/tool_calling/executor.py)
和 [Gate](../../../backend-agent/src/agent_backend/capabilities/agent_runtime/execution_control/tool_authorization_gate.py)：
授权回调必填、非法返回拒绝、版本匹配、输入/输出校验顺序均有实现入口。
拒绝路径与错误包装用例见 [执行器测试](../../../backend-agent/tests/unit/test_tool_executor.py)
和 [Gate 测试](../../../backend-agent/tests/unit/test_tool_authorization_gate.py)。

这些是源码与测试定义核对，不是本轮业务测试结果；既有测试方案中的历史数字不自动视为当前通过。
同步线程超时只停止等待，不能保证底层终止；跨 Java/Python 的完整部署验证仍需单独执行。
