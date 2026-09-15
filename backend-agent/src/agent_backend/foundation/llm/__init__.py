"""LLM client infrastructure interfaces and adapters."""

from agent_backend.foundation.llm.contracts import (
    LlmClient,
    LlmCompletionRequest,
    LlmCompletionResult,
    LlmMessage,
    LlmMessageRole,
    LlmResponseFormat,
    LlmUsage,
)
from agent_backend.foundation.llm.config import LlmClientConfig, LlmRegistryConfig
from agent_backend.foundation.llm.errors import (
    LlmAuthenticationError,
    LlmCallError,
    LlmClientError,
    LlmConfigError,
    LlmProviderUnsupportedError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from agent_backend.foundation.llm.registry import LlmClientFactory, LlmClientRegistry, build_fake_llm_client

__all__ = [
    "LlmAuthenticationError",
    "LlmCallError",
    "LlmClient",
    "LlmClientError",
    "LlmCompletionRequest",
    "LlmCompletionResult",
    "LlmClientConfig",
    "LlmClientFactory",
    "LlmClientRegistry",
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
]
