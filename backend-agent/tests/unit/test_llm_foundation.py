from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_backend.foundation.llm import (
    LlmAuthenticationError,
    LlmCallError,
    LlmCompletionRequest,
    LlmConfigError,
    LlmMessage,
    LlmProviderUnsupportedError,
    LlmRateLimitError,
    LlmTimeoutError,
    LlmUsage,
)
from agent_backend.foundation.llm.adapters.fake import FakeLlmClient


def test_completion_request_accepts_messages() -> None:
    request = LlmCompletionRequest(
        messages=[
            LlmMessage(role="system", content="You are a helpful assistant."),
            LlmMessage(role="user", content="Hello."),
        ],
        response_format="json_object",
        temperature=0,
        max_output_tokens=128,
        timeout_ms=1000,
        metadata={"trace_id": "trace-1"},
    )

    assert request.messages[0].role == "system"
    assert request.response_format == "json_object"
    assert request.metadata == {"trace_id": "trace-1"}


def test_completion_request_rejects_empty_messages() -> None:
    with pytest.raises(ValidationError):
        LlmCompletionRequest(messages=[])


def test_completion_request_rejects_blank_message_content() -> None:
    with pytest.raises(ValidationError):
        LlmCompletionRequest(messages=[LlmMessage(role="user", content="  ")])


@pytest.mark.parametrize(
    ("kwargs", "expected_error"),
    [
        ({"temperature": -0.1}, "temperature must be between 0 and 2"),
        ({"temperature": 2.1}, "temperature must be between 0 and 2"),
        ({"max_output_tokens": 0}, "max_output_tokens must be greater than 0"),
        ({"timeout_ms": 0}, "timeout_ms must be greater than 0"),
    ],
)
def test_completion_request_rejects_invalid_generation_options(
    kwargs: dict[str, float | int],
    expected_error: str,
) -> None:
    with pytest.raises(ValidationError) as exc:
        LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")], **kwargs)

    assert expected_error in str(exc.value)


def test_usage_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        LlmUsage(input_tokens=-1)


def test_fake_llm_client_returns_repeat_output_and_records_requests() -> None:
    client = FakeLlmClient(
        '{"status":"ok"}',
        client_id="test-client",
        model_name="test-model",
    )
    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Generate JSON.")])

    first = client.complete(request)
    second = client.complete(request)

    assert first.content == '{"status":"ok"}'
    assert second.content == '{"status":"ok"}'
    assert first.client_id == "test-client"
    assert first.provider == "fake"
    assert first.model_name == "test-model"
    assert first.latency_ms == 0
    assert len(client.requests) == 2
    assert client.requests[0] == request


def test_fake_llm_client_returns_queued_outputs() -> None:
    client = FakeLlmClient(["first", "second"])
    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")])

    assert client.complete(request).content == "first"
    assert client.complete(request).content == "second"
    assert client.complete(request).content == ""


def test_fake_llm_client_can_raise_configured_error() -> None:
    error = LlmCallError("model unavailable", provider="fake", client_id="fake")
    client = FakeLlmClient(error=error)
    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")])

    with pytest.raises(LlmCallError) as exc:
        client.complete(request)

    assert exc.value is error
    assert client.requests == [request]


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (LlmConfigError("missing key", client_id="c1"), "LLM_CONFIG_ERROR", False),
        (
            LlmProviderUnsupportedError("unsupported", provider="p1", client_id="c1"),
            "LLM_PROVIDER_UNSUPPORTED",
            False,
        ),
        (
            LlmAuthenticationError("bad key", provider="p1", client_id="c1"),
            "LLM_AUTHENTICATION_FAILED",
            False,
        ),
        (LlmTimeoutError("timeout", provider="p1", client_id="c1"), "LLM_TIMEOUT", True),
        (
            LlmRateLimitError("limited", provider="p1", client_id="c1"),
            "LLM_RATE_LIMITED",
            True,
        ),
        (LlmCallError("failed", provider="p1", client_id="c1"), "LLM_CALL_FAILED", True),
    ],
)
def test_llm_errors_expose_stable_code_and_retryable_flag(
    error: Exception,
    code: str,
    retryable: bool,
) -> None:
    assert getattr(error, "code") == code
    assert getattr(error, "retryable") is retryable
