from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from agent_backend.capabilities.agent_runtime.prompt import (
    PromptBudgetGuard,
    PromptRenderRequest,
    PromptRenderResult,
    render_prompt,
)
from agent_backend.capabilities.agent_runtime.execution.llm_request_adapter import LlmRequestAdapter
from agent_backend.foundation.llm import LlmClient, LlmClientError, LlmCompletionResult


JsonLlmStepStatus = Literal[
    "ok",
    "prompt_budget_exceeded",
    "model_output_invalid",
    "model_call_failed",
]


@dataclass(frozen=True)
class JsonLlmStepResult:
    status: JsonLlmStepStatus
    prompt_result: PromptRenderResult
    warnings: list[str] = field(default_factory=list)
    llm_result: LlmCompletionResult | None = None
    error: LlmClientError | None = None
    raw_output: str | None = None
    parsed_output: dict[str, Any] | None = None


def execute_json_llm_step(
    *,
    prompt_request: PromptRenderRequest,
    model_client: LlmClient,
    prompt_budget_guard: PromptBudgetGuard | None = None,
    llm_request_adapter: LlmRequestAdapter | None = None,
    on_prompt_rendered: Callable[[PromptRenderResult, str, list[str]], None] | None = None,
    on_model_call_started: Callable[[], None] | None = None,
    on_model_call_finished: Callable[[], None] | None = None,
) -> JsonLlmStepResult:
    prompt_result = render_prompt(prompt_request)
    budget_guard = prompt_budget_guard or PromptBudgetGuard()
    budget_result = budget_guard.check_rendered_prompt(prompt_result.rendered_text)
    warnings = list(budget_result.warnings)

    if budget_result.status == "exceeded":
        return JsonLlmStepResult(
            status="prompt_budget_exceeded",
            prompt_result=prompt_result,
            warnings=warnings,
        )

    if on_prompt_rendered is not None:
        on_prompt_rendered(prompt_result, budget_result.status, warnings)

    if on_model_call_started is not None:
        on_model_call_started()
    try:
        completion_request = (llm_request_adapter or LlmRequestAdapter()).build_completion_request(prompt_result)
        llm_result = model_client.complete(completion_request)
        raw_output = llm_result.content
    except LlmClientError as exc:
        return JsonLlmStepResult(
            status="model_call_failed",
            prompt_result=prompt_result,
            warnings=warnings,
            error=exc,
        )
    finally:
        if on_model_call_finished is not None:
            on_model_call_finished()

    parsed_output = _parse_json_object(raw_output)
    if parsed_output is None:
        return JsonLlmStepResult(
            status="model_output_invalid",
            prompt_result=prompt_result,
            warnings=warnings,
            llm_result=llm_result,
            raw_output=raw_output,
        )

    return JsonLlmStepResult(
        status="ok",
        prompt_result=prompt_result,
        warnings=warnings,
        llm_result=llm_result,
        raw_output=raw_output,
        parsed_output=parsed_output,
    )


def _parse_json_object(raw_output: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
