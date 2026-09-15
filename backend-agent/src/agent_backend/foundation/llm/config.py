from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LlmClientConfig(BaseModel):
    client_id: str
    provider: str
    model_name: str
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("client_id", "provider", "model_name")
    @classmethod
    def validate_required_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("LLM client config identity fields cannot be empty")
        return value


class LlmRegistryConfig(BaseModel):
    clients: list[LlmClientConfig]
    default_client_id: str | None = None

    @field_validator("clients")
    @classmethod
    def validate_clients(cls, value: list[LlmClientConfig]) -> list[LlmClientConfig]:
        if not value:
            raise ValueError("clients is required")
        return value

    @field_validator("default_client_id")
    @classmethod
    def validate_default_client_id(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("default_client_id cannot be empty")
        return value
