# Foundation LLM 模块说明

## 1. 模块定位

`foundation.llm` 是基础层的大模型调用模块。

它和 Redis、MongoDB、MySQL、数据源 Adapter 一样，属于上层能力可以注入和替换的基础设施能力。

这个模块只负责一件事：

```text
稳定调用一个大模型。
```

它不关心：

```text
1. SQL 怎么生成。
2. Agent 节点怎么流转。
3. Prompt 模板怎么选择。
4. Prompt 变量怎么渲染。
5. ContextBundle 怎么构造。
6. data_analysis_agent 的业务输出协议是什么。
```

如果某段代码需要理解 `generate_sql`、`repair_sql`、`PromptHub`、`ContextBundle`，它就不应该放在 `foundation.llm`。

## 2. 当前已落地目录

```text
backend-agent/src/agent_backend/foundation/llm/
  __init__.py
  README.md
  contracts.py
  errors.py
  adapters/
    __init__.py
    fake.py
```

当前还没有落地：

```text
config.py
registry.py
adapters/openai_compatible.py
```

这三个文件属于下一阶段，用于配置化创建真实模型 Client。

## 3. 当前核心接口

核心代码在 `contracts.py`。

### 3.1 `LlmMessage`

`LlmMessage` 表示一次大模型调用中的一条消息。

当前支持的角色：

```text
system
user
assistant
tool
```

字段：

```text
role:
  消息角色。

content:
  消息正文，不能为空字符串。

name:
  可选名称，当前 MVP 暂不依赖。
```

设计决策：

```text
第一版直接使用 messages，而不是 prompt 字符串。
```

原因是大模型接口长期更适合 messages 结构。系统提示词、用户输入、上下文、历史对话、工具结果，后续都可以自然表达为不同 message。

### 3.2 `LlmCompletionRequest`

`LlmCompletionRequest` 表示一次大模型调用请求。

字段：

```text
messages:
  必填，不能为空。

response_format:
  输出格式，目前支持 text 和 json_object。

temperature:
  可选，传入时必须在 0 到 2 之间。

max_output_tokens:
  可选，传入时必须大于 0。

timeout_ms:
  可选，传入时必须大于 0。

metadata:
  可选，字符串字典，用于透传轻量追踪信息。
```

注意：

```text
metadata 只放轻量标识。
不要放完整 AgentState。
不要放数据库连接信息。
不要放大段业务上下文。
```

### 3.3 `LlmCompletionResult`

`LlmCompletionResult` 表示一次大模型调用结果。

字段：

```text
content:
  模型返回内容。

client_id:
  当前 Client 标识，不能为空。

provider:
  模型供应商，不能为空。

model_name:
  模型名称，不能为空。

usage:
  token 用量，可选。

latency_ms:
  调用耗时，可选，不能小于 0。

finish_reason:
  模型结束原因，可选。

raw_response_id:
  供应商原始响应 ID，可选。

metadata:
  轻量结果元数据。
```

### 3.4 `LlmUsage`

`LlmUsage` 记录 token 用量。

字段：

```text
input_tokens
output_tokens
total_tokens
```

如果字段有值，不能是负数。

### 3.5 `LlmClient`

`LlmClient` 是基础层对外暴露的统一大模型调用接口。

```python
class LlmClient(Protocol):
    client_id: str
    provider: str
    model_name: str

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResult:
        ...
```

调用方只依赖这个接口，不依赖 OpenAI、Azure、本地模型等具体 SDK。

## 4. 当前错误模型

核心代码在 `errors.py`。

所有基础层 LLM 错误都继承自 `LlmClientError`。

统一字段：

```text
message:
  错误说明。

code:
  稳定错误码，方便上层映射。

provider:
  供应商，可选。

client_id:
  Client 标识，可选。

retryable:
  原样重试是否可能成功。
```

当前错误类型：

```text
LlmConfigError:
  配置错误，不可重试。

LlmProviderUnsupportedError:
  provider 没有对应 Adapter，不可重试。

LlmAuthenticationError:
  API Key、权限或鉴权错误，不可重试。

LlmTimeoutError:
  调用超时，可重试。

LlmRateLimitError:
  供应商限流，可重试。

LlmCallError:
  普通调用失败，默认可重试。
```

上层不要直接捕获供应商 SDK 异常，真实 Adapter 应该把供应商异常转换成这里的统一错误。

## 5. 当前 Fake Client

核心代码在 `adapters/fake.py`。

`FakeLlmClient` 是测试和本地开发用的大模型 Client。

它不访问网络。

支持能力：

```text
1. 返回固定字符串。
2. 返回多次调用的输出队列。
3. 记录每次收到的 LlmCompletionRequest。
4. 模拟异常。
```

典型用法：

```python
client = FakeLlmClient('{"status":"ok"}')

result = client.complete(
    LlmCompletionRequest(
        messages=[
            LlmMessage(role="user", content="Generate JSON.")
        ],
        response_format="json_object",
    )
)
```

测试可以通过 `client.requests` 检查上层到底传了什么 messages。

## 6. 和 agent_runtime 的关系

`foundation.llm` 只负责模型调用本身。

`capabilities.agent_runtime.execution` 负责把 Agent Runtime 的 Prompt 执行过程接到 `foundation.llm`。

当前相关目录：

```text
backend-agent/src/agent_backend/capabilities/agent_runtime/execution/
  __init__.py
  llm_request_adapter.py
  llm_step.py
```

### 6.1 `llm_request_adapter.py`

`LlmRequestAdapter` 是 Agent Runtime 到 Foundation LLM 的适配层。

它负责：

```text
1. 接收 PromptRenderResult。
2. 把 rendered_text 包装成 LlmCompletionRequest。
3. 默认要求 response_format=json_object。
4. 把 agent_id、node_id、template_id、template_version、rendered_hash、output_contract 写入 metadata。
```

当前第一版 messages 组织策略：

```text
把 PromptRenderResult.rendered_text 包装成一条 user message。
```

当前这样做是为了最小改造现有 PromptHub 链路。

后续如果要拆成：

```text
system message
user message
context message
tool message
```

优先改 `LlmRequestAdapter`，不要把 messages 拼装逻辑散落到各个业务节点。

### 6.2 `llm_step.py`

`execute_json_llm_step()` 是一次 JSON 模型步骤的编排函数。

它负责：

```text
1. 根据 PromptRenderRequest 渲染 Prompt。
2. 使用 PromptBudgetGuard 检查渲染后文本长度。
3. 调用 LlmRequestAdapter 构造 LlmCompletionRequest。
4. 调用 foundation.llm.LlmClient。
5. 读取 LlmCompletionResult.content。
6. 解析 JSON object。
7. 返回 JsonLlmStepResult。
```

它不负责：

```text
1. 真实供应商 SDK 调用。
2. API Key 读取。
3. SQL 结果结构校验。
4. graph 下一节点选择。
```

当前 `JsonLlmStepResult` 包含：

```text
status:
  ok
  prompt_budget_exceeded
  model_output_invalid
  model_call_failed

prompt_result:
  Prompt 渲染结果。

warnings:
  Prompt budget 等警告。

llm_result:
  LlmCompletionResult，可选。

error:
  LlmClientError，可选。

raw_output:
  模型原始文本内容。

parsed_output:
  JSON object 解析结果。
```

## 7. 当前调用链路

当前 `runtime_turn` 代码关系是：

```text
capabilities.agent_runtime.runtime_turn.RuntimeTurnRunner
  -> capabilities.agent_runtime.execution.execute_json_llm_step
    -> capabilities.agent_runtime.execution.LlmRequestAdapter
      -> foundation.llm.LlmCompletionRequest
    -> foundation.llm.LlmClient
      -> foundation.llm.adapters.fake.FakeLlmClient
```

后续 data_analysis SQL 生成节点接入时，推荐关系是：

```text
orchestration.data_analysis.nodes.generate_sql
  -> capabilities.agent_runtime.execution.execute_json_llm_step
    -> capabilities.agent_runtime.execution.LlmRequestAdapter
      -> foundation.llm.LlmCompletionRequest
    -> foundation.llm.LlmClient
      -> foundation.llm.adapters.fake.FakeLlmClient
```

当前还没有真实 OpenAI-compatible Adapter，所以生产真实调用能力仍需下一阶段实现。

## 8. 当前测试覆盖

已覆盖的测试文件：

```text
tests/unit/test_llm_foundation.py
tests/unit/test_llm_request_adapter.py
tests/unit/test_data_analysis_context_nodes.py
tests/unit/test_runtime_turn_runner.py
```

覆盖内容：

```text
1. LlmCompletionRequest 的 messages 校验。
2. message.content 不能为空。
3. temperature、max_output_tokens、timeout_ms 的参数校验。
4. LlmUsage token 数不能为负。
5. LLM 错误 code 和 retryable 语义。
6. FakeLlmClient 固定输出。
7. FakeLlmClient 队列输出。
8. FakeLlmClient 异常模拟。
9. LlmRequestAdapter 将 PromptRenderResult 转成 user message。
10. runtime_turn 可以使用统一 LlmClient。
```

验证命令：

```text
pytest tests/unit
```

当前验证结果：

```text
92 passed, 1 skipped
```

`ruff` 当前环境没有安装，因此本轮未执行 lint。

## 9. 后续实现规划

### 9.1 下一步：配置和 Registry

建议新增：

```text
config.py
registry.py
```

目标：

```text
1. 通过配置声明多个 LLM Client。
2. 启动时根据配置创建 Client。
3. 上层通过 client_id 获取 Client。
4. 支持测试 fake Client 和真实 Client 并存。
```

注意：

```text
foundation.llm.registry 只按 client_id 获取。
不要在 foundation 层按 sql_generation、repair_sql、node_id 选择模型。
这些属于 agent_runtime 或具体 Agent 的策略。
```

### 9.2 再下一步：OpenAI-compatible Adapter

建议新增：

```text
adapters/openai_compatible.py
```

目标：

```text
1. 支持 OpenAI-compatible chat completions。
2. 把 LlmCompletionRequest.messages 转成供应商请求。
3. 支持 response_format=text/json_object。
4. 记录 usage、latency_ms、finish_reason、raw_response_id。
5. 把供应商异常转换为统一 LlmClientError。
```

### 9.3 再后续：生产 graph 注入

建议改造：

```text
orchestration/data_analysis/graph.py
orchestration/graph.py
api/kafka/worker.py
```

目标：

```text
1. 应用启动时构建 LlmClientRegistry。
2. Agent Runtime 或 graph 根据配置选择 client_id。
3. 把 LlmClient 注入 generate_sql。
4. SQL 生成节点真正调用真实模型。
```

## 10. 分层判断标准

判断代码是否应该放在 `foundation.llm`：

```text
是否只和稳定调用大模型有关？
  是：可以放 foundation.llm。

是否需要统一不同供应商的请求、响应、错误？
  是：可以放 foundation.llm。

是否需要知道 PromptHub 或 PromptRenderResult？
  是：不要放 foundation.llm，放 agent_runtime.execution。

是否需要知道 generate_sql、repair_sql、interpret_result？
  是：不要放 foundation.llm，放具体 Agent 或 orchestration。

是否需要知道 SQL 结果协议？
  是：不要放 foundation.llm，放 data_analysis。
```

当前最终边界：

```text
foundation.llm:
  我能稳定调用一个大模型。

agent_runtime.execution:
  我知道一次 Agent 模型步骤应该怎么执行。

data_analysis:
  我知道 SQL 生成、校验、执行和解释的业务流程。
```
