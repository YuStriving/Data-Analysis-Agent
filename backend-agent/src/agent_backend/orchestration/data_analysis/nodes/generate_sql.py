from __future__ import annotations

from pydantic import ValidationError

from agent_backend.capabilities.data_analysis.contracts import GenerateSqlResult
from agent_backend.capabilities.agent_runtime.context.contracts import ContextBundle
from agent_backend.capabilities.agent_runtime.execution import LlmClient, execute_json_llm_step
from agent_backend.capabilities.agent_runtime.prompt import (
    MissingPromptInputSectionsError,
    PromptBudgetGuard,
    PromptHubError,
    PromptInputAdapter,
)
from agent_backend.capabilities.agent_runtime.prompt.contracts import PromptRenderRequest
from agent_backend.orchestration.data_analysis.nodes._shared import (
    append_event,
    complete_node,
    enter_node,
    fail_node,
    has_error,
)
from agent_backend.orchestration.state import AgentState


def generate_sql(
    state: AgentState,
    *,
    model_client: LlmClient | None = None,
    prompt_budget_guard: PromptBudgetGuard | None = None,
) -> AgentState:
    enter_node(state, "generate_sql")
    if has_error(state):
        return state
    if model_client is None:
        return fail_node(
            state,
            code="model_client_required",
            message="Model client is required to generate SQL.",
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=True,
        )

    try:
        prompt_request = _build_prompt_request(state)
        step_result = execute_json_llm_step(
            prompt_request=prompt_request,
            model_client=model_client,
            prompt_budget_guard=prompt_budget_guard,
        )
    except MissingPromptInputSectionsError as exc:
        return fail_node(
            state,
            code="missing_required_context",
            message="Required context is missing for SQL generation.",
            failure_stage="generate_sql",
            user_action_required=True,
            recoverable=True,
        )
    except (ValidationError, PromptHubError) as exc:
        return fail_node(
            state,
            code="prompt_render_failed",
            message=str(exc),
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=True,
        )

    _record_prompt_metadata(state, step_result.prompt_result.template_version, step_result.prompt_result.rendered_hash)
    _append_warnings(state, step_result.warnings)

    if step_result.status == "prompt_budget_exceeded":
        append_event(
            state,
            "context_budget_exceeded",
            {
                "prompt_version": step_result.prompt_result.template_version,
                "rendered_prompt_hash": step_result.prompt_result.rendered_hash,
                "warnings": step_result.warnings,
            },
            level="warning",
        )
        return fail_node(
            state,
            code="context_budget_exceeded",
            message="Rendered prompt exceeded budget.",
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=True,
        )
    if step_result.status == "model_call_failed":
        error = step_result.error
        append_event(
            state,
            "model_call_failed",
            {
                "prompt_version": step_result.prompt_result.template_version,
                "rendered_prompt_hash": step_result.prompt_result.rendered_hash,
                "error_code": error.code if error is not None else "LLM_CALL_FAILED",
                "retryable": error.retryable if error is not None else True,
            },
            level="warning",
        )
        return fail_node(
            state,
            code=error.code if error is not None else "LLM_CALL_FAILED",
            message=error.message if error is not None else "Model call failed.",
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=error.retryable if error is not None else True,
        )
    if step_result.status == "model_output_invalid" or step_result.parsed_output is None:
        append_event(
            state,
            "model_output_invalid",
            {
                "prompt_version": step_result.prompt_result.template_version,
                "rendered_prompt_hash": step_result.prompt_result.rendered_hash,
            },
            level="warning",
        )
        return fail_node(
            state,
            code="model_output_invalid",
            message="Model output is not valid JSON.",
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=True,
        )

    try:
        generate_sql_result = GenerateSqlResult.model_validate(step_result.parsed_output)
    except ValidationError as exc:
        append_event(
            state,
            "model_output_invalid",
            {
                "prompt_version": step_result.prompt_result.template_version,
                "rendered_prompt_hash": step_result.prompt_result.rendered_hash,
                "validation_errors": exc.errors(),
            },
            level="warning",
        )
        return fail_node(
            state,
            code="model_output_invalid",
            message="Model output does not match generate_sql_result_v1.",
            failure_stage="generate_sql",
            user_action_required=False,
            recoverable=True,
        )
    model_output = generate_sql_result.model_dump(mode="json")
    status = generate_sql_result.status

    analysis = state.setdefault("analysis", {})
    analysis["generate_sql_result"] = model_output
    analysis["prompt_version"] = step_result.prompt_result.template_version
    analysis["rendered_prompt_hash"] = step_result.prompt_result.rendered_hash
    analysis["model"] = model_client.model_name

    if status == "ok":
        analysis["candidate_sql"] = generate_sql_result.sql
        analysis["sql_dialect"] = generate_sql_result.sql_dialect
        analysis["sql_reasoning"] = generate_sql_result.reason
        analysis["used_tables"] = list(generate_sql_result.used_tables)
        analysis["used_fields"] = list(generate_sql_result.used_fields)
        analysis["assumptions"] = list(generate_sql_result.assumptions)
        analysis["sql_generation_warnings"] = list(generate_sql_result.warnings)
        append_event(
            state,
            "sql_generated",
            {
                "prompt_version": step_result.prompt_result.template_version,
                "rendered_prompt_hash": step_result.prompt_result.rendered_hash,
                "model": model_client.model_name,
                "used_tables": analysis["used_tables"],
                "used_fields": analysis["used_fields"],
            },
        )
        return complete_node(state, "validate_sql")

    questions = list(generate_sql_result.clarification_questions)
    message = generate_sql_result.reason or "SQL generation cannot continue."
    analysis["clarification_questions"] = questions
    analysis["sql_generation_warnings"] = list(generate_sql_result.warnings)
    append_event(
        state,
        "sql_generation_blocked",
        {
            "status": status,
            "reason": message,
            "clarification_questions": questions,
        },
        level="warning",
    )
    return fail_node(
        state,
        code=str(status),
        message=message,
        failure_stage="generate_sql",
        user_action_required=status == "clarification_required",
        recoverable=True,
    )


def make_generate_sql_node(
    *,
    model_client: LlmClient,
    prompt_budget_guard: PromptBudgetGuard | None = None,
):
    def _node(state: AgentState) -> AgentState:
        return generate_sql(
            state,
            model_client=model_client,
            prompt_budget_guard=prompt_budget_guard,
        )

    return _node


def _build_prompt_request(state: AgentState) -> PromptRenderRequest:
    bundle = _context_bundle(state)
    return PromptInputAdapter().build_prompt_request(
        agent_id="data_analysis_agent",
        node_id="generate_sql",
        bundle=bundle,
    )


def _context_bundle(state: AgentState) -> ContextBundle:
    bundle = state.get("context", {}).get("context_bundle")
    if isinstance(bundle, ContextBundle):
        return bundle
    if isinstance(bundle, dict):
        return ContextBundle.model_validate(bundle)
    raise MissingPromptInputSectionsError("data_analysis_agent", "generate_sql", ["context_bundle"])


def _record_prompt_metadata(state: AgentState, prompt_version: str, rendered_prompt_hash: str) -> None:
    state["prompt_version"] = prompt_version
    state["rendered_prompt_hash"] = rendered_prompt_hash


def _append_warnings(state: AgentState, warnings: list[str]) -> None:
    if not warnings:
        return
    output = state.setdefault("output", {})
    output_warnings = output.setdefault("warnings", [])
    for warning in warnings:
        output_warnings.append({"source": "generate_sql", "code": warning})
