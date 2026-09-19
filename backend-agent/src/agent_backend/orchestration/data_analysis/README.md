# Data Analysis Runtime

This package owns the data-analysis agent graph shape.

The first version uses eight MVP nodes:

1. `load_task_context`
2. `build_context`
3. `generate_sql`
4. `validate_sql`
5. `run_query`
6. `interpret_result`
7. `build_chart`
8. `persist_result`

The orchestration layer should schedule these nodes. The generic
`agent_runtime` package should remain a capability provider for context,
prompt rendering, tool calling, guardrails, memory, observability, and evals.

`build_data_analysis_graph()` receives runtime dependencies from the worker or
task runner. `model_client` is injected into `generate_sql`. If a caller does
not provide `tool_runtime`, graph construction creates the default
data-analysis `ToolCallingRuntime` and injects it into `build_context` so the
graph can read dataset schema before rendering the SQL generation prompt.

Graph construction performs startup validation for the schema tools required by
`build_context`. A custom `tool_runtime` must provide `mysql.schema_reader@v1`
and `file.relation_normalizer@v1`; otherwise graph construction fails before a
task is executed.

For the current MVP, the default runtime uses dataset metadata resolved from
task state when `build_context` runs. Java remains the permission and dataset
metadata authority; Python only uses the selected dataset metadata to create a
read-only Engine, read schema, and continue into LLM SQL generation. Callers
may still provide a custom `tool_runtime` when they need a specialized engine,
file, or relation-store lifecycle.

Reserved extension points:

- `repair_sql` for recoverable SQL validation or execution failures.
- `human_review_interrupt` for high-risk SQL or policy-sensitive results.
- `python_analysis` for post-query statistics that exceed direct SQL summaries.
- `memory_update` and `eval_record` for non-blocking after-result side effects.
