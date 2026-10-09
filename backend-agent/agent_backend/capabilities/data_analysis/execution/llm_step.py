from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_backend.agent_runtime.prompt import (
    PromptBudgetGuard,
    PromptRenderRequest,
    PromptRenderResult,
    render_prompt,
    render_system_prompt,
)
from agent_backend.capabilities.data_analysis.execution.llm_request_adapter import (
    LlmRequestAdapter,
)
from agent_backend.capabilities.data_analysis.skills import (
    SkillRenderRequest,
    SkillRenderResult,
    render_node_skill,
)
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
    prompt_result: PromptRenderResult | SkillRenderResult
    warnings: list[str] = field(default_factory=list)
    system_prompt_result: PromptRenderResult | None = None
    skill_result: SkillRenderResult | None = None
    llm_result: LlmCompletionResult | None = None
    error: LlmClientError | None = None
    raw_output: str | None = None
    parsed_output: dict[str, Any] | None = None


def execute_json_llm_step(
    *,
    prompt_request: PromptRenderRequest | None = None,
    skill_request: SkillRenderRequest | None = None,
    model_client: LlmClient,
    prompt_budget_guard: PromptBudgetGuard | None = None,
    llm_request_adapter: LlmRequestAdapter | None = None,
    on_prompt_rendered: Callable[[PromptRenderResult | SkillRenderResult, str, list[str]], None] | None = None,
    on_model_call_started: Callable[[], None] | None = None,
    on_model_call_finished: Callable[[], None] | None = None,
) -> JsonLlmStepResult:
    if skill_request is None and prompt_request is None:
        raise ValueError("prompt_request or skill_request is required")

    system_prompt_result: PromptRenderResult | None = None
    skill_result: SkillRenderResult | None = None
    if skill_request is not None:
        system_prompt_result = render_system_prompt(skill_request.agent_id)
        skill_result = render_node_skill(skill_request)
        prompt_result: PromptRenderResult | SkillRenderResult = skill_result
        response_format = skill_result.response_format
        budget_text = f"{system_prompt_result.rendered_text}\n\n{skill_result.rendered_text}"
    else:
        assert prompt_request is not None
        prompt_result = render_prompt(prompt_request)
        response_format = "json_object"
        budget_text = prompt_result.rendered_text

    budget_guard = prompt_budget_guard or PromptBudgetGuard()
    budget_result = budget_guard.check_rendered_prompt(budget_text)
    warnings = list(budget_result.warnings)

    if budget_result.status == "exceeded":
        return JsonLlmStepResult(
            status="prompt_budget_exceeded",
            prompt_result=prompt_result,
            warnings=warnings,
            system_prompt_result=system_prompt_result,
            skill_result=skill_result,
        )

    if on_prompt_rendered is not None:
        on_prompt_rendered(prompt_result, budget_result.status, warnings)

    if on_model_call_started is not None:
        on_model_call_started()
    try:
        completion_request = (llm_request_adapter or LlmRequestAdapter()).build_completion_request(
            prompt_result,
            system_prompt_result=system_prompt_result,
            response_format=response_format,
        )
        llm_result = model_client.complete(completion_request)
        raw_output = llm_result.content
    except LlmClientError as exc:
        return JsonLlmStepResult(
            status="model_call_failed",
            prompt_result=prompt_result,
            warnings=warnings,
            system_prompt_result=system_prompt_result,
            skill_result=skill_result,
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
            system_prompt_result=system_prompt_result,
            skill_result=skill_result,
            llm_result=llm_result,
            raw_output=raw_output,
        )

    return JsonLlmStepResult(
        status="ok",
        prompt_result=prompt_result,
        warnings=warnings,
        system_prompt_result=system_prompt_result,
        skill_result=skill_result,
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
