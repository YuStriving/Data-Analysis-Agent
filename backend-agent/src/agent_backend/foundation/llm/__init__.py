"""LLM client infrastructure interfaces and adapters."""

from agent_backend.foundation.llm.config import LlmClientConfig, LlmRegistryConfig
from agent_backend.foundation.llm.contracts import (
    LlmClient,
    LlmCompletionRequest,
    LlmCompletionResult,
    LlmMessage,
    LlmMessageRole,
    LlmResponseFormat,
    LlmUsage,
)
from agent_backend.foundation.llm.errors import (
    LlmAuthenticationError,
    LlmCallError,
    LlmClientError,
    LlmConfigError,
    LlmProviderUnsupportedError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from agent_backend.foundation.llm.registry import (
    LlmClientFactory,
    LlmClientRegistry,
    build_fake_llm_client,
    build_openai_compatible_llm_client,
)
from agent_backend.foundation.llm.settings import (
    LLM_CONFIG_PATH_ENV,
    build_llm_client_registry_from_env,
    load_llm_registry_config,
    load_llm_registry_config_from_env,
)

__all__ = [
    "LLM_CONFIG_PATH_ENV",
    "LlmAuthenticationError",
    "LlmCallError",
    "LlmClient",
    "LlmClientConfig",
    "LlmClientError",
    "LlmClientFactory",
    "LlmClientRegistry",
    "LlmCompletionRequest",
    "LlmCompletionResult",
    "LlmConfigError",
    "LlmMessage",
    "LlmMessageRole",
    "LlmProviderUnsupportedError",
    "LlmRateLimitError",
    "LlmRegistryConfig",
    "LlmResponseFormat",
    "LlmTimeoutError",
    "LlmUsage",
    "build_fake_llm_client",
    "build_llm_client_registry_from_env",
    "build_openai_compatible_llm_client",
    "load_llm_registry_config",
    "load_llm_registry_config_from_env",
]
