from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from agent_backend.foundation.llm.adapters.fake import FakeLlmClient
from agent_backend.foundation.llm.adapters.openai_compatible import (
    OpenAICompatibleLlmClient,
)
from agent_backend.foundation.llm.config import LlmClientConfig, LlmRegistryConfig
from agent_backend.foundation.llm.contracts import LlmClient
from agent_backend.foundation.llm.errors import (
    LlmConfigError,
    LlmProviderUnsupportedError,
)

LlmClientFactory = Callable[[LlmClientConfig], LlmClient]


def build_fake_llm_client(config: LlmClientConfig) -> LlmClient:
    outputs = config.options.get("outputs", "")
    if not isinstance(outputs, str | list):
        raise LlmConfigError("fake LLM client outputs must be a string or list", client_id=config.client_id)
    if isinstance(outputs, list) and not all(isinstance(output, str) for output in outputs):
        raise LlmConfigError("fake LLM client outputs list must contain strings only", client_id=config.client_id)

    return FakeLlmClient(
        outputs,
        client_id=config.client_id,
        model_name=config.model_name,
    )


def build_openai_compatible_llm_client(config: LlmClientConfig) -> LlmClient:
    if "api_key" in config.options:
        raise LlmConfigError("api_key is not allowed in LLM client options", client_id=config.client_id)

    base_url = config.options.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise LlmConfigError("openai-compatible LLM client base_url is required", client_id=config.client_id)

    api_key_env = config.options.get("api_key_env")
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise LlmConfigError("openai-compatible LLM client api_key_env is required", client_id=config.client_id)

    api_key = os.environ.get(api_key_env)
    if api_key is None or not api_key.strip():
        raise LlmConfigError(
            "openai-compatible LLM client api_key_env is not set",
            client_id=config.client_id,
        )

    timeout_ms = config.options.get("timeout_ms")
    if timeout_ms is not None and (not isinstance(timeout_ms, int) or timeout_ms <= 0):
        raise LlmConfigError(
            "openai-compatible LLM client timeout_ms must be greater than 0",
            client_id=config.client_id,
        )

    return OpenAICompatibleLlmClient(
        client_id=config.client_id,
        model_name=config.model_name,
        base_url=base_url,
        api_key=api_key,
        timeout_ms=timeout_ms,
    )


class LlmClientRegistry:
    def __init__(
        self,
        *,
        default_client_id: str | None = None,
        adapter_factories: Mapping[str, LlmClientFactory] | None = None,
    ) -> None:
        self.default_client_id = default_client_id
        self._clients: dict[str, LlmClient] = {}
        self._adapter_factories: dict[str, LlmClientFactory] = {
            "fake": build_fake_llm_client,
            "openai-compatible": build_openai_compatible_llm_client,
        }
        self._adapter_factories.update(adapter_factories or {})

    @classmethod
    def from_config(
        cls,
        config: LlmRegistryConfig,
        *,
        adapter_factories: Mapping[str, LlmClientFactory] | None = None,
    ) -> LlmClientRegistry:
        registry = cls(
            default_client_id=config.default_client_id,
            adapter_factories=adapter_factories,
        )
        for client_config in config.clients:
            registry.register_from_config(client_config)

        if config.default_client_id is not None and config.default_client_id not in registry._clients:
            raise LlmConfigError("default LLM client is not configured", client_id=config.default_client_id)

        return registry

    def register_adapter(self, provider: str, factory: LlmClientFactory) -> None:
        if not provider.strip():
            raise LlmConfigError("LLM provider cannot be empty")
        self._adapter_factories[provider] = factory

    def register(self, client: LlmClient) -> None:
        if client.client_id in self._clients:
            raise LlmConfigError("duplicate LLM client_id", client_id=client.client_id)
        self._clients[client.client_id] = client

    def register_from_config(self, config: LlmClientConfig) -> LlmClient:
        if config.client_id in self._clients:
            raise LlmConfigError("duplicate LLM client_id", client_id=config.client_id)

        factory = self._adapter_factories.get(config.provider)
        if factory is None:
            raise LlmProviderUnsupportedError(
                f"LLM provider is not supported: {config.provider}",
                provider=config.provider,
                client_id=config.client_id,
            )

        client = factory(config)
        self._clients[config.client_id] = client
        return client

    def get(self, client_id: str) -> LlmClient:
        client = self._clients.get(client_id)
        if client is None:
            raise LlmConfigError("LLM client is not configured", client_id=client_id)
        return client

    def get_default(self) -> LlmClient:
        if self.default_client_id is None:
            raise LlmConfigError("default LLM client is not configured")
        return self.get(self.default_client_id)

    def list_client_ids(self) -> list[str]:
        return list(self._clients)
