# Agent Runtime Execution Control 接口草案

> 本文仍包含建议接口和流程草案。当前模型及控制器见
> `src/agent_backend/capabilities/agent_runtime/execution_control/`；请以源码签名为准。
> 控制器尚未集成到数据分析图的调度循环，文中调用时序不代表现行端到端链路。

## 1. 文档目的

本文档描述 `execution_control` 后续实现时建议暴露的内部 Interface。当前先作为
设计草案，不要求一次性全部落地。

## 2. 包路径

建议代码落位：

```text
backend-agent/src/agent_backend/capabilities/agent_runtime/execution_control/
```

建议文件结构：

```text
contracts.py
policies.py
tracker.py
loop_guard.py
budget_guard.py
tool_guard.py
termination.py
runtime.py
```

## 3. 核心模型

### AgentExecutionMode

```python
AgentExecutionMode = Literal["workflow_mode"]
```

后续可扩展：

```text
bounded_react_mode
planner_executor_mode
```

### RuntimeStatus

```python
RuntimeStatus = Literal[
    "running",
    "completed",
    "user_action_required",
    "cannot_continue",
    "failed",
    "loop_limit_exceeded",
    "budget_exceeded",
    "timeout",
    "guardrail_rejected",
]
```

### AgentSpec

```python
class AgentSpec(BaseModel):
    agent_id: str
    execution_mode: AgentExecutionMode = "workflow_mode"
    entry_node: str
    terminal_nodes: set[str]
    node_specs: dict[str, NodeSpec]
    edge_specs: list[EdgeSpec]
    runtime_policy: RuntimePolicy
    budget_policy: BudgetPolicy
    tool_policy: ToolPolicy
```

### NodeSpec

```python
class NodeSpec(BaseModel):
    node_id: str
    allowed_tools: set[str] = Field(default_factory=set)
    max_visits: int | None = None
    can_emit_final_result: bool = False
```

### EdgeSpec

```python
class EdgeSpec(BaseModel):
    from_node: str
    to_node: str
    max_traversals: int | None = None
    loop_name: str | None = None
```

### RuntimePolicy

```python
class RuntimePolicy(BaseModel):
    max_steps: int = 20
    default_max_node_visits: int = 3
    repeated_error_limit: int = 3
    no_progress_limit: int = 2
    loop_attempt_limits: dict[str, int] = Field(
        default_factory=lambda: {"sql_repair_loop": 3}
    )
```

### BudgetPolicy

```python
class BudgetPolicy(BaseModel):
    max_model_calls: int = 6
    max_tool_calls: int = 10
    max_elapsed_ms: int = 120_000
    warn_at_ratio: float = 0.8
    record_token_usage: bool = True
```

### ToolPolicy

```python
class ToolPolicy(BaseModel):
    same_tool_call_limit: int = 3
    same_tool_failure_limit: int = 2
    allowed_risk_levels: set[str] = Field(
        default_factory=lambda: {"read_only", "compute_only"}
    )
```

### TokenUsage

```python
class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False
```

Token usage 只记录，不作为 MVP 硬拦截条件。

### RuntimeUsage

```python
class RuntimeUsage(BaseModel):
    step_count: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    elapsed_ms: int = 0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
```

### NodeExecutionResult

```python
class NodeExecutionResult(BaseModel):
    node_id: str
    status: RuntimeStatus
    next_node: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    user_action_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### TerminationDecision

```python
class TerminationDecision(BaseModel):
    should_stop: bool
    status: RuntimeStatus
    failure_code: str | None = None
    failure_message: str | None = None
    next_node: str | None = None
    warnings: list[str] = Field(default_factory=list)
```

### RuntimeExecutionResult

```python
class RuntimeExecutionResult(BaseModel):
    task_id: str
    trace_id: str
    agent_id: str
    status: RuntimeStatus
    final_answer: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    usage: RuntimeUsage
    warnings: list[str] = Field(default_factory=list)
```

## 4. 建议 Interface

### RuntimeExecutionController

外部主 Interface：

```python
class RuntimeExecutionController:
    def before_node(self, node_id: str) -> TerminationDecision: ...

    def after_node(
        self,
        result: NodeExecutionResult,
    ) -> TerminationDecision: ...

    def before_model_call(self, node_id: str) -> TerminationDecision: ...

    def after_model_call(
        self,
        node_id: str,
        token_usage: TokenUsage | None = None,
    ) -> None: ...

    def before_tool_call(
        self,
        request: ToolCallRequest,
    ) -> TerminationDecision: ...

    def after_tool_call(
        self,
        request: ToolCallRequest,
        error: ToolCallError | None = None,
    ) -> None: ...
```

调用方只需要在节点、模型调用、工具调用前后经过该 Interface。

### LoopGuard

```python
class LoopGuard:
    def before_node(self, node_id: str) -> TerminationDecision: ...

    def after_transition(
        self,
        from_node: str,
        to_node: str,
        result: NodeExecutionResult,
    ) -> TerminationDecision: ...

    def before_tool_call(self, fingerprint: ToolCallFingerprint) -> TerminationDecision: ...

    def after_tool_call(
        self,
        fingerprint: ToolCallFingerprint,
        error_code: str | None,
    ) -> None: ...
```

### BudgetGuard

```python
class BudgetGuard:
    def before_model_call(self) -> TerminationDecision: ...

    def after_model_call(self, token_usage: TokenUsage | None = None) -> None: ...

    def before_tool_call(self) -> TerminationDecision: ...

    def after_tool_call(self) -> None: ...

    def check_elapsed(self) -> TerminationDecision: ...
```

### ToolGuard

```python
class ToolGuard:
    def check_allowed_tool(
        self,
        node_id: str,
        tool_name: str,
        tool_version: str | None,
    ) -> TerminationDecision: ...

    def build_fingerprint(
        self,
        request: ToolCallRequest,
    ) -> ToolCallFingerprint: ...
```

## 5. 调用时序

### 节点调度

```text
orchestration
-> controller.before_node(node_id)
-> execute node
-> controller.after_node(node_result)
-> if should_stop: return RuntimeExecutionResult
-> schedule decision.next_node
```

### 模型调用

```text
node
-> controller.before_model_call(node_id)
-> execute_json_llm_step
-> controller.after_model_call(node_id, token_usage)
```

### 工具调用

```text
node
-> controller.before_tool_call(request)
-> ToolCallingRuntime.call(request)
-> 成功：controller.after_tool_call(request)
-> 捕获 ToolCallError：controller.after_tool_call(request, error)
```

`ToolCallResult` 只表示成功；失败直接抛出 `ToolCallError`，包含 `reason`、
`message`、`retryable`、`detail`。控制器以 `error.reason` 识别重复失败，不依赖
工具错误码或失败结果对象；业务调用方继续处理异常并保留完整 payload。

## 6. 与现有模块的集成点

1. `orchestration/data_analysis` 负责把节点返回结果映射为
   `NodeExecutionResult`。
2. `agent_runtime/execution/llm_step.py` 后续可把模型 token usage 传回
   `after_model_call`。
3. `agent_runtime/tool_calling/runtime.py` 继续负责单次工具调用。
4. `execution_control` 在 `ToolCallingRuntime.call()` 之前做节点白名单、重复工具
   调用和工具调用预算判断。
5. `checkpoint` 后续保存 `RuntimeUsage` 和 loop counters。

## 7. MVP 默认 data_analysis_agent 配置

```text
agent_id = data_analysis_agent
execution_mode = workflow_mode
entry_node = load_task_context
terminal_nodes = persist_result, fail_task

runtime_policy:
  max_steps = 20
  default_max_node_visits = 3
  repeated_error_limit = 3
  no_progress_limit = 2
  sql_repair_loop.max_attempts = 3

budget_policy:
  max_model_calls = 6
  max_tool_calls = 10
  max_elapsed_ms = 120000
  record_token_usage = true

tool_policy:
  same_tool_call_limit = 3
  same_tool_failure_limit = 2
  allowed_risk_levels = read_only, compute_only
```

## 8. 非兼容说明

该 Interface 不要求替换现有 `RuntimeTurnRunner`。后续可以先在
`orchestration/data_analysis` 主 workflow 中接入，再逐步收敛旧的单轮 runner。
