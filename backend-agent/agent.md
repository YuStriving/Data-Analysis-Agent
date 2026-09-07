# Backend Agent Contract

## 1. Scope

`backend-agent` is the Python runtime for the analysis agent.

This directory is responsible for:

- LangGraph orchestration
- tool registration and invocation
- SQL planning and guardrails
- Python post-processing
- chart generation
- memory management
- MCP integration
- context engineering
- prompt engineering
- evals and regression checks

This directory is not responsible for:

- primary authentication
- primary authorization
- browser-facing SSE ownership
- direct user identity trust without Java context

## 2. Required Stack

- `Python 3.12`
- `FastAPI`
- `LangGraph`
- `Pydantic`
- `SQLAlchemy`
- `Redis`
- `MongoDB`

Model-facing integrations should prefer:

- `OpenAI Responses API`
- structured outputs
- typed tool schemas

## 3. Package Boundaries

The runtime root is `src/agent_backend/` and follows four layers:

- `api`
  - HTTP and Kafka entrypoint adapters only
- `orchestration`
  - LangGraph graph, state, transitions, node checkpoints, and manual resume logic
- `capabilities`
  - concrete agent capability code and reusable agent runtime services
- `foundation`
  - typed contracts and data source adapters consumed by upper layers

`capabilities/agent_runtime` contains reusable services such as context,
prompt loading, tool calling, memory service, guardrails, observability, and
evaluation helpers.

`capabilities/data_analysis` owns the current single business agent and its
concrete SQL, Python, and chart tool implementations.

`foundation/datasource` owns Redis, MongoDB, MySQL, and file data adapters.
`foundation/contracts` contains cross-layer typed models.

Do not merge these packages into one generic utils directory.

## 4. Permission Rules

- trust only the access context produced by Java
- never expand dataset scope on the agent side
- never execute write SQL
- never call unapproved MCP servers
- do not persist memory outside tenant and user boundaries

## 5. Prompt and Context Rules

- prompts must be versioned
- context must be compact and permission-scoped
- prompt templates must live outside core business logic
- every tool-facing prompt must define a structured output target
- unsupported or unsafe requests must fail explicitly
- context injection must follow task-type policies; recovery tasks use `checkpoint_first`

## 6. Tooling Rules

- every tool must declare input and output schema
- every tool must have timeout and retry policy
- every tool result must be serializable
- SQL tools must enforce read-only restrictions
- chart tools must output frontend-consumable config

## 7. Streaming Rules

- Python may emit internal progress events
- event payloads must be typed and stable
- final browser-facing SSE formatting belongs to Java
- progress events must include `task_id` and `trace_id`

## 8. Memory and Recovery Rules

- Redis stores only the pending flush queue and hot context
- MongoDB is the durable store for memory turns and checkpoints
- flush must be idempotent and clear Redis only after MongoDB commit
- memory keys must include tenant, user, and session scope
- snapshots must be captured at node level before interruption or failure
- restore must require manual confirmation before execution resumes
- alerts are log-only and bucketed by day under `runtime/logs/backend-agent/alerts/`

## 9. Evaluation Rules

- any change to prompts, tool schemas, or guardrails should be regression-tested
- track SQL correctness, failure rate, latency, and review-required rate
- keep eval data separate from production runtime code

## 10. Self-Evolution Rules

This local contract must evolve whenever the Python runtime changes in a stable way.

Automatic updates are required when:

- a new agent package becomes a standard part of the runtime
- prompt, context, memory, or MCP workflows are formalized
- tool contracts or structured outputs change
- new evaluation or guardrail requirements become standard
- internal event contracts change

Automatic updates are not allowed for:

- weakening SQL safety rules
- broadening access beyond Java-issued context
- replacing the Python runtime stack without explicit approval

## 11. Non-Goals

- no direct frontend rendering
- no root authorization logic
- no unsafe shell execution without explicit sandbox policy
