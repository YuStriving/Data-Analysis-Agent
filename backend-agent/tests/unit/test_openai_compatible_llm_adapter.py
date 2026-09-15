from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from openai import (
    NOT_GIVEN,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from agent_backend.foundation.llm import (
    LlmAuthenticationError,
    LlmCallError,
    LlmClientConfig,
    LlmClientRegistry,
    LlmCompletionRequest,
    LlmConfigError,
    LlmMessage,
    LlmRateLimitError,
    LlmRegistryConfig,
    LlmTimeoutError,
    build_openai_compatible_llm_client,
)
from agent_backend.foundation.llm.adapters.openai_compatible import (
    OpenAICompatibleLlmClient,
)


class FakeCompletionsResource:
    def __init__(self, response: Any | None = None, error: Exception | None = None) -> None:
        self.response = response or _completion_response()
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: Any | None = None, error: Exception | None = None) -> None:
        self.completions = FakeCompletionsResource(response=response, error=error)
        self.chat = SimpleNamespace(completions=self.completions)


def test_openai_compatible_client_maps_request_and_response() -> None:
    sdk_client = FakeOpenAIClient(
        response=_completion_response(
            content='{"ok":true}',
            response_id="chatcmpl-1",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    client = OpenAICompatibleLlmClient(
        client_id="main",
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        timeout_ms=30000,
        sdk_client=sdk_client,
    )
    request = LlmCompletionRequest(
        messages=[
            LlmMessage(role="system", content="Return JSON."),
            LlmMessage(role="user", content="Hello.", name="user_1"),
        ],
        response_format="json_object",
        temperature=0.2,
        max_output_tokens=128,
        timeout_ms=1000,
    )

    result = client.complete(request)

    assert sdk_client.completions.calls == [
        {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": "Hello.", "name": "user_1"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 128,
            "timeout": 1.0,
        }
    ]
    assert result.content == '{"ok":true}'
    assert result.client_id == "main"
    assert result.provider == "openai-compatible"
    assert result.model_name == "deepseek-chat"
    assert result.usage is not None
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.finish_reason == "stop"
    assert result.raw_response_id == "chatcmpl-1"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


def test_openai_compatible_client_omits_text_response_format() -> None:
    sdk_client = FakeOpenAIClient()
    client = OpenAICompatibleLlmClient(
        client_id="main",
        model_name="model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        sdk_client=sdk_client,
    )

    client.complete(LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")]))

    assert sdk_client.completions.calls[0]["response_format"] is NOT_GIVEN
    assert sdk_client.completions.calls[0]["timeout"] is NOT_GIVEN


def test_openai_compatible_client_returns_empty_content_when_response_has_no_choices() -> None:
    sdk_client = FakeOpenAIClient(response=SimpleNamespace(id="chatcmpl-empty", choices=[], usage=None))
    client = OpenAICompatibleLlmClient(
        client_id="main",
        model_name="model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        sdk_client=sdk_client,
    )

    result = client.complete(LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")]))

    assert result.content == ""
    assert result.usage is None
    assert result.finish_reason is None


@pytest.mark.parametrize(
    ("sdk_error_factory", "expected_error", "expected_code"),
    [
        ("authentication", LlmAuthenticationError, "LLM_AUTHENTICATION_FAILED"),
        ("permission_denied", LlmAuthenticationError, "LLM_AUTHENTICATION_FAILED"),
        ("rate_limit", LlmRateLimitError, "LLM_RATE_LIMITED"),
        ("timeout", LlmTimeoutError, "LLM_TIMEOUT"),
        ("connection", LlmCallError, "LLM_CALL_FAILED"),
    ],
)
def test_openai_compatible_client_maps_sdk_errors(
    sdk_error_factory: str,
    expected_error: type[Exception],
    expected_code: str,
) -> None:
    client = OpenAICompatibleLlmClient(
        client_id="main",
        model_name="model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        sdk_client=FakeOpenAIClient(error=_sdk_error(sdk_error_factory)),
    )

    with pytest.raises(expected_error) as exc:
        client.complete(LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")]))

    assert exc.value.code == expected_code
    assert exc.value.provider == "openai-compatible"
    assert exc.value.client_id == "main"


def test_openai_compatible_factory_rejects_inline_api_key() -> None:
    config = _client_config(options={"base_url": "https://llm.example/v1", "api_key": "secret"})

    with pytest.raises(LlmConfigError) as exc:
        build_openai_compatible_llm_client(config)

    assert exc.value.client_id == "main"


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"api_key_env": "TEST_LLM_API_KEY"},
        {"base_url": "https://llm.example/v1"},
        {"base_url": "https://llm.example/v1", "api_key_env": "TEST_LLM_API_KEY", "timeout_ms": 0},
    ],
)
def test_openai_compatible_factory_rejects_invalid_config(
    options: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_LLM_API_KEY", raising=False)

    with pytest.raises(LlmConfigError):
        build_openai_compatible_llm_client(_client_config(options=options))


def test_registry_registers_openai_compatible_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_LLM_API_KEY", "test-key")

    registry = LlmClientRegistry.from_config(
        LlmRegistryConfig(
            default_client_id="main",
            clients=[
                _client_config(
                    options={
                        "base_url": "https://llm.example/v1",
                        "api_key_env": "TEST_LLM_API_KEY",
                        "timeout_ms": 30000,
                    }
                )
            ],
        )
    )

    assert registry.get_default().provider == "openai-compatible"


def _client_config(*, options: dict[str, Any]) -> LlmClientConfig:
    return LlmClientConfig(
        client_id="main",
        provider="openai-compatible",
        model_name="model",
        options=options,
    )


def _completion_response(
    *,
    content: str = "ok",
    response_id: str = "chatcmpl-test",
    finish_reason: str = "stop",
    prompt_tokens: int = 1,
    completion_tokens: int = 2,
    total_tokens: int = 3,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
    )


def _fake_request() -> object:
    return SimpleNamespace(method="POST", url="https://llm.example/v1/chat/completions")


def _authentication_error() -> AuthenticationError:
    return AuthenticationError("bad key", response=_fake_response(401), body=None)


def _permission_denied_error() -> PermissionDeniedError:
    return PermissionDeniedError("forbidden", response=_fake_response(403), body=None)


def _rate_limit_error() -> RateLimitError:
    return RateLimitError("limited", response=_fake_response(429), body=None)


def _sdk_error(kind: str) -> Exception:
    if kind == "authentication":
        return _authentication_error()
    if kind == "permission_denied":
        return _permission_denied_error()
    if kind == "rate_limit":
        return _rate_limit_error()
    if kind == "timeout":
        return APITimeoutError(request=_fake_request())
    if kind == "connection":
        return APIConnectionError(request=_fake_request())
    raise AssertionError(f"unknown sdk error kind: {kind}")


def _fake_response(status_code: int) -> object:
    return SimpleNamespace(
        status_code=status_code,
        headers={},
        request=_fake_request(),
    )
