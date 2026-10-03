# 通用 Tools 调用契约设计

关联 [spec.md](spec.md)；验证记录见 [测试方案](../../tests/tool-calling.md)。

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
