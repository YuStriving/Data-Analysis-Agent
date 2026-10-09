from __future__ import annotations

from agent_backend.agent_runtime.prompt import PromptRenderResult
from agent_backend.capabilities.data_analysis.skills import SkillRenderResult
from agent_backend.foundation.llm import (
    LlmCompletionRequest,
    LlmMessage,
    LlmResponseFormat,
)


class LlmRequestAdapter:
    def build_completion_request(
        self,
        prompt_result: PromptRenderResult | SkillRenderResult,
        *,
        system_prompt_result: PromptRenderResult | None = None,
        response_format: LlmResponseFormat = "json_object",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_ms: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> LlmCompletionRequest:
        template_id = prompt_result.template_id
        template_version = prompt_result.template_version
        request_metadata = {
            "agent_id": prompt_result.agent_id,
            "node_id": prompt_result.node_id,
            "template_id": template_id,
            "template_version": template_version,
            "rendered_prompt_hash": prompt_result.rendered_hash,
            "output_contract": prompt_result.output_contract,
        }
        if isinstance(prompt_result, SkillRenderResult):
            request_metadata.update(
                {
                    "skill_id": prompt_result.skill_id,
                    "skill_version": prompt_result.skill_version,
                    "rendered_skill_hash": prompt_result.rendered_hash,
                }
            )
        if system_prompt_result is not None:
            request_metadata.update(
                {
                    "system_prompt_template_id": system_prompt_result.template_id,
                    "system_prompt_version": system_prompt_result.template_version,
                    "rendered_system_prompt_hash": system_prompt_result.rendered_hash,
                }
            )
        if metadata:
            request_metadata.update(metadata)

        messages = []
        if system_prompt_result is not None:
            messages.append(LlmMessage(role="system", content=system_prompt_result.rendered_text))
        messages.append(LlmMessage(role="user", content=prompt_result.rendered_text))

        return LlmCompletionRequest(
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            timeout_ms=timeout_ms,
            metadata=request_metadata,
        )
