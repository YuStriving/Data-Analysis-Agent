from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


PromptBudgetStatus = Literal["ok", "ok_with_warning", "exceeded"]


class PromptBudgetPolicy(BaseModel):
    max_rendered_prompt_chars: int = Field(
        12_000,
        description="Maximum rendered prompt length allowed before model calls",
    )
    warn_at_ratio: float = Field(
        0.8,
        description="Warn when rendered prompt reaches this ratio of the maximum length",
    )

    @field_validator("max_rendered_prompt_chars")
    @classmethod
    def validate_max_rendered_prompt_chars(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_rendered_prompt_chars must be greater than 0")
        return value

    @field_validator("warn_at_ratio")
    @classmethod
    def validate_warn_at_ratio(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("warn_at_ratio must be greater than 0 and less than or equal to 1")
        return value


class PromptBudgetResult(BaseModel):
    status: PromptBudgetStatus
    rendered_prompt_chars: int
    max_rendered_prompt_chars: int
    warnings: list[str] = Field(default_factory=list)


class PromptBudgetGuard:
    def __init__(self, policy: PromptBudgetPolicy | None = None) -> None:
        self.policy = policy or PromptBudgetPolicy()

    def check_rendered_prompt(
        self,
        rendered_text: str,
        policy: PromptBudgetPolicy | None = None,
    ) -> PromptBudgetResult:
        active_policy = policy or self.policy
        rendered_prompt_chars = len(rendered_text)
        max_chars = active_policy.max_rendered_prompt_chars

        if rendered_prompt_chars > max_chars:
            return PromptBudgetResult(
                status="exceeded",
                rendered_prompt_chars=rendered_prompt_chars,
                max_rendered_prompt_chars=max_chars,
                warnings=["rendered_prompt_exceeded_budget"],
            )

        warn_at_chars = int(max_chars * active_policy.warn_at_ratio)
        if rendered_prompt_chars >= warn_at_chars:
            return PromptBudgetResult(
                status="ok_with_warning",
                rendered_prompt_chars=rendered_prompt_chars,
                max_rendered_prompt_chars=max_chars,
                warnings=["rendered_prompt_near_budget"],
            )

        return PromptBudgetResult(
            status="ok",
            rendered_prompt_chars=rendered_prompt_chars,
            max_rendered_prompt_chars=max_chars,
            warnings=[],
        )


def check_rendered_prompt_budget(
    rendered_text: str,
    policy: PromptBudgetPolicy | None = None,
) -> PromptBudgetResult:
    return PromptBudgetGuard(policy=policy).check_rendered_prompt(rendered_text)
