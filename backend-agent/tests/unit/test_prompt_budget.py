import pytest
from pydantic import ValidationError

from agent_backend.capabilities.agent_runtime.prompt import (
    PromptBudgetGuard,
    PromptBudgetPolicy,
    check_rendered_prompt_budget,
)


def test_prompt_budget_guard_allows_prompt_under_warning_threshold() -> None:
    result = check_rendered_prompt_budget(
        "x" * 79,
        PromptBudgetPolicy(max_rendered_prompt_chars=100, warn_at_ratio=0.8),
    )

    assert result.status == "ok"
    assert result.rendered_prompt_chars == 79
    assert result.max_rendered_prompt_chars == 100
    assert result.warnings == []


def test_prompt_budget_guard_warns_when_prompt_reaches_threshold() -> None:
    result = PromptBudgetGuard(
        PromptBudgetPolicy(max_rendered_prompt_chars=100, warn_at_ratio=0.8)
    ).check_rendered_prompt("x" * 80)

    assert result.status == "ok_with_warning"
    assert result.rendered_prompt_chars == 80
    assert result.warnings == ["rendered_prompt_near_budget"]


def test_prompt_budget_guard_rejects_prompt_over_maximum() -> None:
    result = PromptBudgetGuard(
        PromptBudgetPolicy(max_rendered_prompt_chars=100, warn_at_ratio=0.8)
    ).check_rendered_prompt("x" * 101)

    assert result.status == "exceeded"
    assert result.rendered_prompt_chars == 101
    assert result.warnings == ["rendered_prompt_exceeded_budget"]


def test_prompt_budget_policy_rejects_invalid_maximum() -> None:
    with pytest.raises(ValidationError, match="max_rendered_prompt_chars"):
        PromptBudgetPolicy(max_rendered_prompt_chars=0)


def test_prompt_budget_policy_rejects_invalid_warning_ratio() -> None:
    with pytest.raises(ValidationError, match="warn_at_ratio"):
        PromptBudgetPolicy(warn_at_ratio=1.1)
