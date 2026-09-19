# Backend Agent Contract

## 1. Scope

`backend-agent` is the Python runtime for the analysis agent.

This local contract inherits the root `agent.md`. If this file conflicts with
the root contract, the root contract wins and this file must be updated in the
same workstream.

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
- tenant or role source-of-truth decisions
- dataset access-control source-of-truth decisions
- browser-facing SSE ownership
- frontend-facing task status aggregation
- direct user identity trust without Java context
- exposing Python internals directly to browsers

## 2. Required Stack

- `Python 3.12`
- `FastAPI`
- `LangGraph`
- `Pydantic`
- `SQLAlchemy`
- `Redis`
- `MongoDB`
- `PyMySQL`

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

Runtime capability code should be colocated with its capability module:

- `capabilities/agent_runtime/context`
  - owns context contracts, context builder, context policies, and task
    classifier logic
- `capabilities/agent_runtime/memory`
  - owns memory contracts, store protocols, Redis store, Mongo store, and
    memory service logic
- `capabilities/agent_runtime/prompt`
  - owns prompt contracts, front matter template loading, prompt registry,
    prompt rendering, missing-variable errors, rendered hash generation, and
    prompt-facing user failure mapping
- `capabilities/agent_runtime/execution`
  - owns reusable execution helpers for model-backed steps, including prompt
    rendering, budget checks, LLM request adaptation, model error mapping, and
    JSON output parsing

Do not place memory-specific Redis/Mongo semantics, context-specific contracts,
or capability-local protocols in `foundation` just because they are shared by a
few files. `foundation` is for cross-layer contracts and low-level adapters with
no agent capability semantics.

`capabilities/data_analysis` owns the current single business agent and its
concrete SQL, Python, and chart tool implementations.

Design `agent_runtime` as a reusable execution framework plus capability
interfaces. Do not make concrete agents inherit a large runtime base class.
Concrete agents should register an agent spec that declares supported task
types, context policy, prompt set, tool set, guardrails, entry graph, and output
schema version.

`foundation/datasource` may expose compatibility shims for older imports, but
memory-specific Redis/Mongo implementations live under
`capabilities/agent_runtime/memory`.

`foundation/contracts` contains cross-layer typed models such as task requests.
It may temporarily expose compatibility imports while modules are being
migrated, but new context and memory contracts should be defined in their
own `agent_runtime` capability packages.

Do not merge these packages into one generic utils directory.

## 4. Permission Rules

- trust only the access context produced by Java
- Java is the final authority for authentication, authorization, tenant
  isolation, dataset access control, and task entry
- Python should receive only least-privilege task context and selected dataset
  metadata from Java
- never expand dataset scope on the agent side
- never query platform authorization tables to discover additional datasets
- never execute write SQL
- never call unapproved MCP servers
- do not persist memory outside tenant and user boundaries
- sensitive columns must be masked or blocked before they reach the agent; if
  Java marks a field unavailable, Python must not reintroduce it through schema
  inspection, prompts, tools, or memory
- secrets, database passwords, LLM API keys, and full connection URLs must not
  be emitted into prompts, progress events, logs, memory records, or eval
  fixtures

## 5. Prompt and Context Rules

- prompts must be versioned
- context must be compact and permission-scoped
- prompt templates must live outside core business logic
- every tool-facing prompt must define a structured output target
- prompt templates live under concrete capability packages, such as
  `capabilities/data_analysis/prompts/{node_id}/base.v1.md`
- prompt templates use Markdown with `---` front matter for metadata,
  required variables, optional variables, and output contract
- prompt loading and rendering must go through
  `capabilities/agent_runtime/prompt`, not ad hoc string concatenation inside
  graph nodes
- every LLM node should receive the active `system` prompt and its node prompt
  so each node can be replayed and evaluated independently
- missing required prompt variables must fail before model invocation and be
  mapped by workflow/lifecycle into a user-friendly message
- all current `data_analysis_agent` node prompts must require JSON output
- unsupported or unsafe requests must fail explicitly
- context injection must follow task-type policies; recovery tasks use `checkpoint_first`
- multi-turn analysis context is scoped by `session_id`
- a concrete agent must receive a trimmed context bundle, not full raw context
- context contracts live in `capabilities/agent_runtime/context/contracts.py`
- `ContextPolicy` decides which context sections each agent node may receive
- `ContextBuilder` must receive structured `ContextSource` inputs and return a
  trimmed `ContextBundle`; graph nodes should not manually concatenate raw
  request, dataset, schema, memory, or repair context into prompts
- SQL generation context must include the user request, selected dataset,
  access context, and schema context before calling the model; missing required
  sections should fail before model invocation
- schema context for `generate_sql` is produced by `build_context` after a
  schema tool call, not fabricated by the LLM node
- Redis hot memory can be a context source, but context builder must still trim
  and filter it before prompt injection
- `AnalysisTaskRequest.session_id` is required and must be generated or
  forwarded by Java; Python must not use `task_id` as a session fallback

## 5.1 LLM Execution Rules

- model-backed workflow nodes must use
  `capabilities/agent_runtime/execution/execute_json_llm_step()` unless a
  stronger node-specific execution helper is introduced
- `execute_json_llm_step()` is responsible for prompt rendering, prompt budget
  checks, LLM request adaptation, provider error capture, raw output capture,
  and JSON object parsing
- model clients must be injected as `LlmClient`; graph nodes must not import
  provider SDKs, read API keys, or construct provider-specific clients
- JSON model outputs must be validated against node-owned contracts such as
  `GenerateSqlResult` before mutating analysis state
- prompt version and rendered prompt hash must be recorded for replay,
  debugging, and evals

## 6. Tooling Rules

- every tool must declare input and output schema
- every tool must have timeout and retry policy
- every tool result must be serializable
- SQL tools must enforce read-only restrictions
- chart tools must output a generic chart spec, not a frontend-library-specific option
- the initial chart spec version supports only `bar`, `line`, `pie`, and `table`
- first-class data sources for the MVP are MySQL, CSV, XLS, and XLSX
- schema inspection is done live by Python for the MVP; add schema caching later as a TODO
- file datasets must enter Python as Java-selected dataset metadata containing
  a `file_ref` and parsing hints such as `sheet_names`, `header_row`,
  `sample_rows`, and `max_rows_to_inspect`
- data-analysis tool runtime assembly must go through
  `capabilities/data_analysis/tools/runtime.py`
- `build_data_analysis_tool_runtime()` is the standard factory for wiring
  data-analysis tools into `ToolCallingRuntime`
- `build_engine_resolver_from_dataset_metadata()` is the MVP bridge from
  Java-provided dataset metadata to SQLAlchemy `Engine`
- `build_file_resolver_from_dataset_metadata()` is the MVP bridge from
  Java-provided file dataset metadata to local file paths for
  `file.relation_normalizer`
- Java remains the authority for dataset permission checks and connection
  metadata selection; Python must not expand dataset scope or query platform
  authorization tables to discover extra datasets
- MySQL credentials may be passed in Java-provided dataset metadata for the
  MVP only; keep them out of logs and replace this with Java-issued secret
  references or short-lived readonly credentials before production
- OSS file refs must be resolved through Java-issued signed URLs,
  short-lived file tokens, or Java-staged local paths before production;
  Python must not hold long-lived OSS credentials
- the MVP engine resolver creates a new SQLAlchemy `Engine` on each resolver
  call; add Engine caching later with explicit invalidation and shutdown
  disposal
- current MVP uses Graph Workflow to control tool calls; future Model Tool
  Calling should inject allowed tool schemas from `tool_calling` based on
  `agent_id + node_id` while keeping permission checks and guardrails in code

## 7. Streaming Rules

- Python may emit internal progress events
- event payloads must be typed and stable
- final browser-facing SSE formatting belongs to Java
- progress events must include `task_id` and `trace_id`
- progress events emitted by Python should include or preserve `event_type` and
  timestamp metadata so Java can forward or repackage them consistently
- Python terminal progress events should map cleanly to Java-owned
  `final_answer` or `task_failed` browser events
- for the MVP, Java may forward Python Agent events to the frontend without repackaging
- Python endpoints and internal event streams must not be exposed directly to
  untrusted browsers

## 8. Memory and Recovery Rules

- memory code lives in `capabilities/agent_runtime/memory`
- memory scope is `tenant_id + user_id + session_id`; for the C-side MVP,
  `tenant_id` defaults to `default`
- Redis stores hot context, recent turns, pending flush items, pending sequence,
  flush lock, and dead letter items
- Redis key families are `hot`, `recent_turns`, `pending`, `seq`,
  `flush_lock`, and `dead` under the memory namespace
- MongoDB is the durable store for `memory_turns` and `memory_events`
- `memory_turns` stores user-visible question and final assistant answer turns
- `memory_events` stores the agent's typed analysis process events
- `MemoryEvent.payload` must use strong typed payload models, not free-form
  `dict[str, Any]`
- `payload.type` must match the outer `event_type`
- supported memory event payloads include question received, dataset resolved,
  schema loaded, SQL generated, SQL validated, SQL repaired, query executed,
  result summarized, chart built, answer generated, and task failed
- Redis pending items use an envelope with `item_type`, `scope`, `scope_key`,
  `pending_seq`, `payload`, and `created_at`
- `pending_seq` is generated by Redis `INCR` per scope to preserve session
  flush order
- flush uses a lightweight Redis `SET NX EX` lock with TTL; Python does not use
  a Redisson-style watchdog in the MVP
- flush batch size is capped; default design target is 500 items
- flush must be idempotent and trim Redis only after MongoDB upsert succeeds
- successful flush must use `LTRIM` for the read batch, not delete the full
  pending key
- MongoDB writes use natural IDs: `turn_id` for turns and `event_id` for events
- MongoDB write failure must leave Redis pending data in place for retry
- bad JSON or payload validation failure should move the item to a dead letter
  queue and continue with valid items
- hot memory keeps only recent reusable context; recent turns are capped at 6
  turns, hot context TTL is 2 hours, and idle flush threshold is 1 hour
- session context may include selected dataset, generated SQL, SQL failures,
  retry history, result summary, chart summary, and final answer when available
- large query results must not be stored directly in memory or context; store
  previews, summaries, and references only
- session file staging is isolated per `session_id`; a new conversation window
  requires a new upload or explicit dataset selection
- checkpoint is not a memory responsibility; it is an independent
  `agent_runtime` recovery capability
- snapshots must be captured at node level before interruption or failure
- restore must require manual confirmation before execution resumes
- alerts are log-only and bucketed by day under `runtime/logs/backend-agent/alerts/`

Memory compatibility rule:

- old imports from `foundation.contracts.memory` or `foundation.datasource`
  may remain as temporary shims
- new memory code must import from `agent_backend.capabilities.agent_runtime.memory`
  directly

## 8.1 Data Analysis Agent Rules

- `data_analysis` is the first concrete business agent
- it handles natural-language questions by resolving a dataset, loading schema, generating SQL, validating SQL, executing SQL, interpreting results, and building a chart spec when useful
- `orchestration/data_analysis/graph.py` owns the data-analysis graph builder;
  do not register data-analysis nodes ad hoc in generic scaffold graphs
- `build_data_analysis_graph()` must receive runtime dependencies explicitly,
  including `model_client`, optional `tool_runtime`, optional
  `dataset_metadata_resolver`, and optional `prompt_budget_guard`
- graph routing should follow node-produced `graph.next_node` values and route
  recoverable node failures to `fail_task` instead of continuing the happy path
- if the user selected a dataset in the current turn, use that dataset
- if no dataset was selected, use the current session's most recent uploaded or used dataset
- if the current session has no available dataset, return an explicit dataset-selection prompt
- Python executes read-only SQL directly and returns structured results to Java
- `build_context` must receive a `ToolCallingRuntime` so it can call
  `mysql.schema_reader` or file relation tools before `generate_sql`
- `build_context` is responsible for turning Java-selected dataset metadata and
  live schema tool output into the `ContextBundle` consumed by `generate_sql`
- `generate_sql` must receive an injected `LlmClient`; graph nodes must not
  construct provider-specific clients directly
- `generate_sql` must call the shared JSON LLM execution path and then validate
  model output against `GenerateSqlResult` before writing `candidate_sql`
- task and trace identifiers from Java must be preserved across graph state,
  tool calls, LLM request metadata, progress events, and persisted runtime
  records
- query result limits must come from configuration
- when results exceed the configured maximum, return the first N rows, a summary, and a truncation warning
- SQL generation or execution failure may trigger automatic SQL repair, with a maximum of 3 attempts
- SQL repair must include the previous SQL, error message, failure stage, schema, retry count, and lessons from prior failures

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
- Java/Python task context, dataset metadata, or event handoff contracts change
- local development or CI verification commands become standard for
  `backend-agent`

Automatic updates are not allowed for:

- weakening SQL safety rules
- broadening access beyond Java-issued context
- replacing the Python runtime stack without explicit approval

## 11. Non-Goals

- no direct frontend rendering
- no root authorization logic
- no unsafe shell execution without explicit sandbox policy
- no hardcoded production secrets or committed local credential files
- no undocumented runtime behavior that only exists in helper scripts

## 12. Validation and Documentation Rules

- before publishing Python runtime changes, run the most relevant targeted
  pytest and ruff checks for the affected packages
- `scripts/ci/verify.ps1` is the repository aggregate verification entrypoint
  when a broader local check is needed
- when backend-agent changes affect architecture, package boundaries, event
  contracts, prompt/context behavior, tool contracts, or security boundaries,
  update this file and the related README or docs in the same change set
- checked-in examples may use placeholders, but real local credential files
  must stay ignored by git
