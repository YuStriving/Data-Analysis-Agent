from __future__ import annotations


class LlmClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "LLM_CLIENT_ERROR",
        provider: str | None = None,
        client_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.provider = provider
        self.client_id = client_id
        self.retryable = retryable


class LlmConfigError(LlmClientError):
    def __init__(self, message: str, *, client_id: str | None = None) -> None:
        super().__init__(
            message,
            code="LLM_CONFIG_ERROR",
            client_id=client_id,
            retryable=False,
        )


class LlmProviderUnsupportedError(LlmClientError):
    def __init__(self, message: str, *, provider: str | None = None, client_id: str | None = None) -> None:
        super().__init__(
            message,
            code="LLM_PROVIDER_UNSUPPORTED",
            provider=provider,
            client_id=client_id,
            retryable=False,
        )


class LlmAuthenticationError(LlmClientError):
    def __init__(self, message: str, *, provider: str | None = None, client_id: str | None = None) -> None:
        super().__init__(
            message,
            code="LLM_AUTHENTICATION_FAILED",
            provider=provider,
            client_id=client_id,
            retryable=False,
        )


class LlmTimeoutError(LlmClientError):
    def __init__(self, message: str, *, provider: str | None = None, client_id: str | None = None) -> None:
        super().__init__(
            message,
            code="LLM_TIMEOUT",
            provider=provider,
            client_id=client_id,
            retryable=True,
        )


class LlmRateLimitError(LlmClientError):
    def __init__(self, message: str, *, provider: str | None = None, client_id: str | None = None) -> None:
        super().__init__(
            message,
            code="LLM_RATE_LIMITED",
            provider=provider,
            client_id=client_id,
            retryable=True,
        )


class LlmCallError(LlmClientError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        client_id: str | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(
            message,
            code="LLM_CALL_FAILED",
            provider=provider,
            client_id=client_id,
            retryable=retryable,
        )
