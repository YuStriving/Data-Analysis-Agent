from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field


class RuntimePolicy(BaseModel):
    max_steps: int = Field(default=20, ge=1)
    default_max_node_visits: int = Field(default=3, ge=1)
    repeated_error_limit: int = Field(default=3, ge=1)
    no_progress_limit: int = Field(default=2, ge=1)
    loop_attempt_limits: dict[str, int] = Field(
        default_factory=lambda: {"sql_repair_loop": 3}
    )


class BudgetPolicy(BaseModel):
    max_model_calls: int = Field(default=6, ge=0)
    max_tool_calls: int = Field(default=10, ge=0)
    max_elapsed_ms: int = Field(default=120_000, ge=1)
    warn_at_ratio: float = Field(default=0.8, ge=0, le=1)
    record_token_usage: bool = True


class ToolAccessPolicy(BaseModel):
    """Call eligibility configured outside a business tool's minimal contract."""

    allowed_agents: list[str] = Field(default_factory=list)
    allowed_nodes: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    requires_review: bool = False
    risk_level: str | None = None


ToolAccessPolicyResolver = Callable[[str, str | None], ToolAccessPolicy]


class ToolPolicy(BaseModel):
    same_tool_call_limit: int = Field(default=3, ge=1)
    same_tool_failure_limit: int = Field(default=2, ge=1)
    allowed_risk_levels: set[str] = Field(
        default_factory=lambda: {"read_only", "compute_only"}
    )


class TokenUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated: bool = False

    def merged(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated=self.estimated or other.estimated,
        )


class RuntimeUsage(BaseModel):
    step_count: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
