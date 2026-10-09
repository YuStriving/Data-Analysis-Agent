from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

LlmMessageRole = Literal["system", "user", "assistant", "tool"]
LlmResponseFormat = Literal["text", "json_object"]


class LlmMessage(BaseModel):
    role: LlmMessageRole
    content: str
    name: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content is required")
        return value


class LlmCompletionRequest(BaseModel):
    messages: list[LlmMessage]
    response_format: LlmResponseFormat = "text"
    temperature: float | None = None
    max_output_tokens: int | None = None
    timeout_ms: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, value: list[LlmMessage]) -> list[LlmMessage]:
        if not value:
            raise ValueError("messages is required")
        return value

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2")
        return value

    @field_validator("max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_output_tokens must be greater than 0")
        return value

    @field_validator("timeout_ms")
    @classmethod
    def validate_timeout_ms(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("timeout_ms must be greater than 0")
        return value


class LlmUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @field_validator("input_tokens", "output_tokens", "total_tokens")
    @classmethod
    def validate_token_count(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("token count cannot be negative")
        return value


class LlmCompletionResult(BaseModel):
    content: str
    client_id: str
    provider: str
    model_name: str
    usage: LlmUsage | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None
    raw_response_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("client_id", "provider", "model_name")
    @classmethod
    def validate_required_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("LLM result identity fields cannot be empty")
        return value

    @field_validator("latency_ms")
    @classmethod
    def validate_latency_ms(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("latency_ms cannot be negative")
        return value


class LlmClient(Protocol):
    client_id: str
    provider: str
    model_name: str

    def complete(self, request: LlmCompletionRequest) -> LlmCompletionResult: ...
