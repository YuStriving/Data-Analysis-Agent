from __future__ import annotations

import time
from typing import Any

from openai import (
    NOT_GIVEN,
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from agent_backend.foundation.llm.contracts import (
    LlmCompletionRequest,
    LlmCompletionResult,
    LlmUsage,
)
from agent_backend.foundation.llm.errors import (
    LlmAuthenticationError,
    LlmCallError,
    LlmRateLimitError,
    LlmTimeoutError,
)


class OpenAICompatibleLlmClient:
    provider = "openai-compatible"

    def __init__(
        self,
        *,
        client_id: str,
        model_name: str,
        base_url: str,
        api_key: str,
        timeout_ms: int | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.client_id = client_id
        self.model_name = model_name
        self.base_url = base_url
        self.timeout_ms = timeout_ms
        self._sdk_client = sdk_client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=_timeout_arg(timeout_ms),
        )

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResult:
        started_at = time.monotonic()
        try:
            response = self._sdk_client.chat.completions.create(
                model=self.model_name,
                messages=_build_messages(request),
                response_format=_build_response_format(request),
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                timeout=_timeout_arg(request.timeout_ms),
            )
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise LlmAuthenticationError(
                str(exc),
                provider=self.provider,
                client_id=self.client_id,
            ) from exc
        except RateLimitError as exc:
            raise LlmRateLimitError(
                str(exc),
                provider=self.provider,
                client_id=self.client_id,
            ) from exc
        except (APITimeoutError, TimeoutError) as exc:
            raise LlmTimeoutError(
                str(exc),
                provider=self.provider,
                client_id=self.client_id,
            ) from exc
        except (APIConnectionError, APIError) as exc:
            raise LlmCallError(
                str(exc),
                provider=self.provider,
                client_id=self.client_id,
            ) from exc

        return LlmCompletionResult(
            content=_extract_content(response),
            client_id=self.client_id,
            provider=self.provider,
            model_name=self.model_name,
            usage=_extract_usage(response),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            finish_reason=_extract_finish_reason(response),
            raw_response_id=getattr(response, "id", None),
        )


def _build_messages(request: LlmCompletionRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for message in request.messages:
        payload = {
            "role": message.role,
            "content": message.content,
        }
        if message.name is not None:
            payload["name"] = message.name
        messages.append(payload)
    return messages


def _build_response_format(request: LlmCompletionRequest) -> dict[str, str] | Any:
    if request.response_format == "json_object":
        return {"type": "json_object"}
    return NOT_GIVEN


def _extract_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if content is None:
        return ""
    return content


def _extract_finish_reason(response: Any) -> str | None:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return None
    return getattr(choices[0], "finish_reason", None)


def _extract_usage(response: Any) -> LlmUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    return LlmUsage(
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


def _timeout_arg(timeout_ms: int | None) -> float | Any:
    if timeout_ms is None:
        return NOT_GIVEN
    return timeout_ms / 1000
