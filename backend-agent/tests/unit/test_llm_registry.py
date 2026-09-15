from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_backend.foundation.llm import (
    LlmClientConfig,
    LlmClientRegistry,
    LlmCompletionRequest,
    LlmConfigError,
    LlmMessage,
    LlmProviderUnsupportedError,
    LlmRegistryConfig,
)
from agent_backend.foundation.llm.adapters.fake import FakeLlmClient


def test_registry_builds_multiple_fake_clients_from_config() -> None:
    registry = LlmClientRegistry.from_config(
        LlmRegistryConfig(
            default_client_id="sql",
            clients=[
                LlmClientConfig(
                    client_id="sql",
                    provider="fake",
                    model_name="fake-sql",
                    options={"outputs": '{"sql":"select 1"}'},
                ),
                LlmClientConfig(
                    client_id="summary",
                    provider="fake",
                    model_name="fake-summary",
                    options={"outputs": ["first", "second"]},
                ),
            ],
        )
    )

    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")])

    assert registry.list_client_ids() == ["sql", "summary"]
    assert registry.get("sql").complete(request).content == '{"sql":"select 1"}'
    assert registry.get("summary").complete(request).content == "first"
    assert registry.get("summary").complete(request).content == "second"
    assert registry.get_default().model_name == "fake-sql"


def test_registry_can_register_custom_provider_factory() -> None:
    def build_custom_client(config: LlmClientConfig) -> FakeLlmClient:
        return FakeLlmClient(
            "custom-output",
            client_id=config.client_id,
            model_name=config.model_name,
        )

    registry = LlmClientRegistry.from_config(
        LlmRegistryConfig(
            clients=[
                LlmClientConfig(
                    client_id="custom",
                    provider="custom-provider",
                    model_name="custom-model",
                )
            ],
        ),
        adapter_factories={"custom-provider": build_custom_client},
    )

    request = LlmCompletionRequest(messages=[LlmMessage(role="user", content="Hello.")])

    assert registry.get("custom").complete(request).content == "custom-output"


def test_registry_can_register_adapter_after_init() -> None:
    registry = LlmClientRegistry()

    registry.register_adapter(
        "custom-provider",
        lambda config: FakeLlmClient("custom-output", client_id=config.client_id, model_name=config.model_name),
    )
    client = registry.register_from_config(
        LlmClientConfig(
            client_id="custom",
            provider="custom-provider",
            model_name="custom-model",
        )
    )

    assert client is registry.get("custom")


def test_registry_raises_for_unsupported_provider() -> None:
    with pytest.raises(LlmProviderUnsupportedError) as exc:
        LlmClientRegistry.from_config(
            LlmRegistryConfig(
                clients=[
                    LlmClientConfig(
                        client_id="main",
                        provider="unknown",
                        model_name="model",
                    )
                ],
            )
        )

    assert exc.value.code == "LLM_PROVIDER_UNSUPPORTED"
    assert exc.value.provider == "unknown"
    assert exc.value.client_id == "main"
    assert exc.value.retryable is False


def test_registry_raises_for_missing_default_client() -> None:
    with pytest.raises(LlmConfigError) as exc:
        LlmClientRegistry.from_config(
            LlmRegistryConfig(
                default_client_id="missing",
                clients=[
                    LlmClientConfig(
                        client_id="main",
                        provider="fake",
                        model_name="model",
                    )
                ],
            )
        )

    assert exc.value.code == "LLM_CONFIG_ERROR"
    assert exc.value.client_id == "missing"
    assert exc.value.retryable is False


def test_registry_raises_when_default_client_is_requested_but_unset() -> None:
    registry = LlmClientRegistry.from_config(
        LlmRegistryConfig(
            clients=[
                LlmClientConfig(
                    client_id="main",
                    provider="fake",
                    model_name="model",
                )
            ],
        )
    )

    with pytest.raises(LlmConfigError) as exc:
        registry.get_default()

    assert exc.value.code == "LLM_CONFIG_ERROR"
    assert exc.value.client_id is None


def test_registry_raises_for_missing_client_id() -> None:
    registry = LlmClientRegistry.from_config(
        LlmRegistryConfig(
            clients=[
                LlmClientConfig(
                    client_id="main",
                    provider="fake",
                    model_name="model",
                )
            ],
        )
    )

    with pytest.raises(LlmConfigError) as exc:
        registry.get("missing")

    assert exc.value.client_id == "missing"


def test_registry_raises_for_duplicate_client_id() -> None:
    with pytest.raises(LlmConfigError) as exc:
        LlmClientRegistry.from_config(
            LlmRegistryConfig(
                clients=[
                    LlmClientConfig(
                        client_id="main",
                        provider="fake",
                        model_name="model",
                    ),
                    LlmClientConfig(
                        client_id="main",
                        provider="fake",
                        model_name="other-model",
                    ),
                ],
            )
        )

    assert exc.value.code == "LLM_CONFIG_ERROR"
    assert exc.value.client_id == "main"


def test_registry_config_rejects_empty_clients() -> None:
    with pytest.raises(ValidationError):
        LlmRegistryConfig(clients=[])


def test_client_config_rejects_blank_identity_fields() -> None:
    with pytest.raises(ValidationError):
        LlmClientConfig(client_id=" ", provider="fake", model_name="model")


def test_fake_factory_rejects_invalid_outputs_option() -> None:
    with pytest.raises(LlmConfigError) as exc:
        LlmClientRegistry.from_config(
            LlmRegistryConfig(
                clients=[
                    LlmClientConfig(
                        client_id="main",
                        provider="fake",
                        model_name="model",
                        options={"outputs": [1]},
                    )
                ],
            )
        )

    assert exc.value.client_id == "main"
