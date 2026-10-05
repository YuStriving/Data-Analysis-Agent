# 通用 Tools 调用契约需求规格

状态：用户已确认实施（2026-10-03）。必须表示强制要求，不得表示禁止行为。

## 目标与边界

完善现有工具调用，支持不同业务工具通过相同契约注册、授权和执行。MVP 包含强类型上下文、Core Gate、配置分离及现有调用迁移；模型自主调用循环、远程协议、审批恢复和前端事件展示不在本次范围。

设计见 [design.md](../../design-docs/cross-module/tool-execution-authorization.md)，历史实施记录见 [tasks.md](tasks.md)，可执行测试见[授权 Gate](../../../backend-agent/tests/unit/test_tool_authorization_gate.py) 与[执行器](../../../backend-agent/tests/unit/test_tool_executor.py)。

### Requirement TC-001：最小业务工具契约

业务工具必须提供 name、description、输入 JSON Schema input_args 和 execute(args, context)。不得要求工具继承执行器、提供 definition() 或声明授权策略。

#### Scenario：替换业务工具

- **GIVEN** 文本工具与计算工具均满足最小契约。
- **WHEN** 分别通过通用入口执行。
- **THEN** 两者得到结构化结果，通用模块无需增加业务分支或数据集依赖。

### Requirement TC-002：任务目标与调用目的

每次调用必须提供非空 goal 和 purpose。参数决定操作，目标和目的不得扩大权限或覆盖参数。

#### Scenario：传递执行背景

- **GIVEN** 任务目标为分析销售趋势，本次目的为查明字段。
- **WHEN** Core 授权通过并调用工具。
- **THEN** Tool 获得准确的目标、目的和参数。

### Requirement TC-003：通用与业务上下文分离

通用上下文不得强制包含数据集字段；业务资源范围必须通过强类型上下文提供，传递时不得丢失业务字段。

#### Scenario：业务上下文传递

- **GIVEN** 请求持有具体业务上下文。
- **WHEN** Gate 检查并调用 Tool。
- **THEN** Gate 与 Tool 获得完整的具体上下文；非数据工具无需 DatasetScope。

### Requirement TC-004：统一 Capability / Authorization Gate

Runtime 和独立执行器的工具执行必须经过 Core Gate。检查能力声明、Agent/节点、权限、风险、审批条件，并注入业务资源授权。授权只能来自可信装配层和 Java 上下文。

#### Scenario：允许调用

- **GIVEN** 工具、节点、权限和资源范围均满足声明。
- **WHEN** Gate 检查本次调用。
- **THEN** 允许 Tool 执行。

### Requirement TC-005：工具与执行配置独立

版本、输出 schema、超时必须通过独立配置提供；执行器不得查询注册表或根据业务名称创建依赖。

#### Scenario：指定版本

- **GIVEN** 工具注册了不同版本和配置。
- **WHEN** 请求指定一个版本。
- **THEN** 只执行该版本及其配置，不自动回退。

### Requirement TC-006：执行前后校验

输入必须在授权及执行前解析并校验。成功输出必须非空、符合输出 schema 且可序列化为 JSON。非空指不为 None，允许空对象、空列表、0、False。

#### Scenario：输入不合法

- **GIVEN** 输入缺必填字段、类型错误或不是对象。
- **WHEN** 执行器处理输入。
- **THEN** 返回输入错误，Tool 不执行。

### Requirement TC-007：同步、异步与超时

支持同步、异步及同步返回 awaitable；同步业务方法不得阻塞事件循环。超时明确失败，取消向上传播，不自动重试。

#### Scenario：超时与取消

- **GIVEN** 工具超时或任务取消。
- **WHEN** 执行器等待结果。
- **THEN** 分别返回超时错误或传播取消，不再次执行。

### Requirement TC-008：稳定结果与错误

成功字段保持 tool_call_id、tool_name、tool_version、data。ToolCallError 保持 reason、message、retryable、detail；已有工具异常原样传播，普通业务异常统一包装。

#### Scenario：业务异常

- **GIVEN** 工具抛出已有 ToolCallError。
- **WHEN** 执行器处理失败。
- **THEN** 保留异常与字段，不生成成功结果。

### Requirement TC-009：现有行为及安全限制兼容

迁移不得削弱数据集授权、节点能力和只读 SQL 限制；工具发现列表不得代替执行授权。

#### Scenario：危险 SQL

- **GIVEN** 参数包含违反现有只读规则的 SQL。
- **WHEN** Gate 执行业务策略。
- **THEN** 执行 SQL 前拒绝。

### 补充验收场景

#### Scenario TC-002：缺少必要背景

- **GIVEN** goal 或 purpose 缺失、为空或只有空白。
- **WHEN** 构造调用上下文。
- **THEN** 明确拒绝，Tool 不执行。

#### Scenario TC-004：调用资格不足

- **GIVEN** 策略缺失、节点未声明工具、权限不足、风险不允许或需要审批。
- **WHEN** 通过 Runtime 或独立执行器调用。
- **THEN** 明确失败，Tool 调用次数为零。

#### Scenario TC-004：业务资源越权

- **GIVEN** 指定未授权数据集或不允许的数据源类型。
- **WHEN** Gate 执行业务授权策略。
- **THEN** 拒绝资源访问。

#### Scenario TC-005：工具或版本不存在

- **GIVEN** 请求的工具或版本未注册。
- **WHEN** Runtime 查找。
- **THEN** 返回查找失败，不执行其他版本。

#### Scenario TC-006：输出不合法

- **GIVEN** 输出为 None、违反 schema 或不可 JSON 序列化。
- **WHEN** 执行器处理输出。
- **THEN** 返回输出错误，不产生成功结果。

#### Scenario TC-009：发现可见但调用不允许

- **GIVEN** 工具可被查询到，但本次调用不满足授权条件。
- **WHEN** 发起执行。
- **THEN** Gate 仍然拒绝。

## 兼容性及限制

Java 任务入口、成功及错误字段保持兼容。内部请求一次迁移；可执行测试留在模块目录。
同步线程超时只停止等待，不保证底层线程终止。目标和调用目的不用于授予权限。
