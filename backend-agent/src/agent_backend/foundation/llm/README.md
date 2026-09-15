# Foundation LLM 模块说明

## 1. 模块定位

`foundation.llm` 是基础层的大模型调用模块，只负责稳定调用一个大模型。

它不关心 SQL 怎么生成、Agent 节点怎么流转、Prompt 模板怎么选择、ContextBundle 怎么构造，也不关心 `data_analysis_agent` 的业务输出协议。

如果某段代码需要理解 `generate_sql`、`repair_sql`、`PromptHub`、`ContextBundle`，它就不应该放在 `foundation.llm`。

## 2. 当前已落地目录

```text
backend-agent/src/agent_backend/foundation/llm/
  __init__.py
  README.md
  config.py
  contracts.py
  errors.py
  registry.py
  settings.py
  adapters/
    __init__.py
    fake.py
    openai_compatible.py
```

当前已落地能力：

```text
1. 统一 LlmClient 请求、响应和错误模型。
2. FakeLlmClient 测试适配器。
3. LlmClientConfig / LlmRegistryConfig 配置模型。
4. LlmClientRegistry 按 client_id 管理多个 Client。
5. 内置 fake 和 openai-compatible provider。
6. OpenAI-compatible Chat Completions 真实调用适配器。
7. 基于 YAML 文件的 LLM 配置加载入口。
```

当前还没有落地：

```text
1. graph/runtime 启动时自动注入 LlmClientRegistry。
2. node 级 client_id 选择策略。
3. 真实 API 的端到端集成验证。
```

## 3. 核心接口

核心代码在 `contracts.py`。

`LlmClient` 是基础层对外暴露的统一大模型调用接口：

```python
class LlmClient(Protocol):
    client_id: str
    provider: str
    model_name: str

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResult:
        ...
```

调用方只依赖这个接口，不依赖 OpenAI、DeepSeek、Qwen、私有网关等具体 SDK 或 HTTP 细节。

`LlmCompletionRequest` 表示一次大模型调用请求：

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
  可选，传入时必须大于 0。单次请求设置后会覆盖 Client 默认 timeout。

metadata:
  可选，字符串字典，用于透传轻量追踪信息。
```

`LlmCompletionResult` 表示一次大模型调用结果：

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

`metadata` 只放轻量标识，不要放完整 `AgentState`、数据库连接信息或大段业务上下文。

## 4. 配置模型

核心代码在 `config.py`。

`LlmClientConfig` 表示一个可被 Registry 创建的大模型 Client：

```python
class LlmClientConfig(BaseModel):
    client_id: str
    provider: str
    model_name: str
    options: dict[str, Any] = Field(default_factory=dict)
```

字段语义：

```text
client_id:
  系统内部使用的 Client 标识，例如 sql-generator。

provider:
  Adapter 类型，例如 fake、openai-compatible。

model_name:
  供应商侧模型名，例如 deepseek-chat、gpt-4o-mini。

options:
  provider 私有配置。foundation.llm 的通用配置层不提前理解每个供应商的全部字段。
```

`LlmRegistryConfig` 表示完整 Registry 配置：

```python
class LlmRegistryConfig(BaseModel):
    clients: list[LlmClientConfig]
    default_client_id: str | None = None
```

`clients` 不能为空。`default_client_id` 可以为空，但调用 `get_default()` 时如果没有默认 Client，会抛 `LlmConfigError`。

## 5. Client Registry

核心代码在 `registry.py`。

`LlmClientRegistry` 负责：

```text
1. 保存 client_id -> LlmClient。
2. 保存 provider -> factory。
3. 根据 LlmRegistryConfig 创建多个 Client。
4. 按 client_id 获取 Client。
5. 获取默认 Client。
```

典型用法：

```python
config = LlmRegistryConfig(
    default_client_id="sql-generator",
    clients=[
        LlmClientConfig(
            client_id="sql-generator",
            provider="fake",
            model_name="fake-sql",
            options={"outputs": '{"sql":"select 1"}'},
        )
    ],
)

registry = LlmClientRegistry.from_config(config)
client = registry.get_default()
```

内置 provider：

```text
fake
openai-compatible
```

错误语义：

```text
provider 不支持:
  LlmProviderUnsupportedError

client_id 不存在:
  LlmConfigError

default_client_id 为空或不存在:
  LlmConfigError

重复 client_id:
  LlmConfigError
```

`foundation.llm.registry` 只按 `client_id` 获取。不要在 foundation 层按 `sql_generation`、`repair_sql`、`node_id` 选择模型，这些属于 `agent_runtime` 或具体 Agent 的策略。

## 6. Fake Client

核心代码在 `adapters/fake.py`。

`FakeLlmClient` 是测试和本地开发用的大模型 Client，不访问网络。

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
        messages=[LlmMessage(role="user", content="Generate JSON.")],
        response_format="json_object",
    )
)
```

测试可以通过 `client.requests` 检查上层到底传了什么 messages。

## 7. OpenAI-Compatible Adapter

核心代码在 `adapters/openai_compatible.py`。

`OpenAICompatibleLlmClient` 是真实模型调用适配器，使用 OpenAI Python SDK 调用 Chat Completions。

它负责：

```text
1. 把 LlmCompletionRequest.messages 转成 Chat Completions messages。
2. 把 response_format=json_object 转成 {"type": "json_object"}。
3. 透传 temperature、max_output_tokens、timeout_ms。
4. 解析 content、usage、finish_reason、raw_response_id。
5. 记录 latency_ms。
6. 把 SDK 异常转换为统一 LlmClientError。
```

`provider` 固定为：

```text
openai-compatible
```

配置要求：

```yaml
client_id: sql-generator
provider: openai-compatible
model_name: deepseek-chat
options:
  base_url: https://api.deepseek.com/v1
  api_key_env: DEEPSEEK_API_KEY
  timeout_ms: 30000
```

安全规则：

```text
1. base_url 必填。
2. api_key_env 必填。
3. 禁止在 options 中配置 api_key 明文。
4. 真实 API Key 只能从 api_key_env 指向的环境变量读取。
```

错误转换：

```text
AuthenticationError / PermissionDeniedError:
  LlmAuthenticationError

RateLimitError:
  LlmRateLimitError

APITimeoutError / TimeoutError:
  LlmTimeoutError

APIConnectionError / APIError:
  LlmCallError
```

## 8. YAML 配置加载

核心代码在 `settings.py`。

当前采用：

```text
YAML 配置文件 + 环境变量保存真实 API Key
```

入口环境变量：

```text
LLM_CONFIG_PATH
```

推荐本地配置示例：

```yaml
default_client_id: sql-generator

clients:
  - client_id: sql-generator
    provider: openai-compatible
    model_name: deepseek-chat
    options:
      base_url: https://api.deepseek.com/v1
      api_key_env: DEEPSEEK_API_KEY
      timeout_ms: 30000

  - client_id: summary
    provider: fake
    model_name: fake-summary
    options:
      outputs: summary ok
```

对外函数：

```python
load_llm_registry_config(path)
load_llm_registry_config_from_env()
build_llm_client_registry_from_env()
```

职责：

```text
load_llm_registry_config:
  读取 YAML 文件，解析成 LlmRegistryConfig。

load_llm_registry_config_from_env:
  从 LLM_CONFIG_PATH 读取路径，再加载配置。

build_llm_client_registry_from_env:
  加载配置，并创建 LlmClientRegistry。
```

错误语义：

```text
LLM_CONFIG_PATH 缺失:
  LlmConfigError

配置文件不存在或不是文件:
  LlmConfigError

YAML 语法错误:
  LlmConfigError

YAML 顶层不是 mapping:
  LlmConfigError

Pydantic 配置校验失败:
  LlmConfigError
```

## 9. 错误模型

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

## 10. 和 agent_runtime 的关系

`foundation.llm` 只负责模型调用本身。

`capabilities.agent_runtime.execution` 负责把 Agent Runtime 的 Prompt 执行过程接到 `foundation.llm`。

当前相关目录：

```text
backend-agent/src/agent_backend/capabilities/agent_runtime/execution/
  __init__.py
  llm_request_adapter.py
  llm_step.py
```

`LlmRequestAdapter` 负责接收 `PromptRenderResult`，把 `rendered_text` 包装成 `LlmCompletionRequest`，并把轻量追踪信息写入 metadata。

当前第一版 messages 组织策略：

```text
把 PromptRenderResult.rendered_text 包装成一条 user message。
```

后续如果要拆成 system/user/context/tool message，优先改 `LlmRequestAdapter`，不要把 messages 拼装逻辑散落到各个业务节点。

`execute_json_llm_step()` 是一次 JSON 模型步骤的编排函数。它负责渲染 Prompt、检查 PromptBudget、构造 `LlmCompletionRequest`、调用 `LlmClient`、解析 JSON object，并返回 `JsonLlmStepResult`。

它不负责：

```text
1. 真实供应商 SDK 调用。
2. API Key 读取。
3. SQL 结果结构校验。
4. graph 下一节点选择。
5. 根据 node_id 选择 client_id。
```

## 11. 当前调用链路

当前 LLM 基础层已经支持：

```text
YAML config
  -> foundation.llm.settings
  -> LlmRegistryConfig
  -> LlmClientRegistry
  -> LlmClient
  -> FakeLlmClient / OpenAICompatibleLlmClient
```

当前业务运行链路仍主要依赖显式注入：

```text
RuntimeTurnRunner / data_analysis node
  -> execute_json_llm_step
  -> LlmClient.complete
```

下一步推荐改造为：

```text
应用启动 / graph 构建
  -> build_llm_client_registry_from_env()
  -> 根据默认 client_id 或 node 策略获取 LlmClient
  -> 注入 RuntimeTurnRunner / data_analysis node
```

node 不应该直接依赖 `OpenAICompatibleLlmClient`，只应该依赖统一的 `LlmClient`。

## 12. 当前测试覆盖

已覆盖的测试文件：

```text
tests/unit/test_llm_foundation.py
tests/unit/test_llm_registry.py
tests/unit/test_openai_compatible_llm_adapter.py
tests/unit/test_llm_settings.py
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
6. FakeLlmClient 固定输出、队列输出、异常模拟。
7. Registry 多 Client、默认 Client、client_id 获取。
8. provider 不支持、默认缺失、重复 client_id 的统一错误。
9. OpenAI-compatible 请求转换、响应解析、错误转换。
10. 禁止配置明文 api_key。
11. YAML 配置加载、env 路径读取和配置错误包装。
12. LlmRequestAdapter 将 PromptRenderResult 转成 user message。
13. runtime_turn 可以使用统一 LlmClient。
```

验证命令：

```text
python -m ruff check src/agent_backend/foundation/llm tests/unit/test_llm_settings.py tests/unit/test_openai_compatible_llm_adapter.py tests/unit/test_llm_registry.py
python -m pytest tests/unit
```

当前验证结果：

```text
All checks passed!
124 passed, 1 skipped
```

## 13. 后续实现规划

### 13.1 下一步：生产 graph 注入

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
4. SQL 生成节点真正调用配置指定的模型。
```

MVP 策略：

```text
所有 LLM node 先使用 default_client。
node 级 client_id 策略后续再加。
```

### 13.2 再下一步：真实 API 手动集成验证

建议新增手动验证脚本或文档：

```text
1. 设置 LLM_CONFIG_PATH。
2. 设置 DEEPSEEK_API_KEY / OPENAI_API_KEY。
3. 构建 LlmClientRegistry。
4. 调用默认 Client。
5. 验证返回 content、usage、finish_reason。
```

真实 API 调用不进入默认单元测试，避免依赖网络和真实密钥。

## 14. 分层判断标准

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
