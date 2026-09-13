from __future__ import annotations

from agent_backend.capabilities.agent_runtime.prompt import PromptRenderResult
from agent_backend.foundation.llm import (
    LlmCompletionRequest,
    LlmMessage,
    LlmResponseFormat,
)


class LlmRequestAdapter:
    def build_completion_request(
        self,
        prompt_result: PromptRenderResult,
        *,
        response_format: LlmResponseFormat = "json_object",
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        timeout_ms: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> LlmCompletionRequest:
        request_metadata = {
            "agent_id": prompt_result.agent_id,
            "node_id": prompt_result.node_id,
            "template_id": prompt_result.template_id,
            "template_version": prompt_result.template_version,
            "rendered_prompt_hash": prompt_result.rendered_hash,
            "output_contract": prompt_result.output_contract,
        }
        if metadata:
            request_metadata.update(metadata)

        return LlmCompletionRequest(
            messages=[LlmMessage(role="user", content=prompt_result.rendered_text)],
            response_format=response_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            timeout_ms=timeout_ms,
            metadata=request_metadata,
        )
