from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


PromptStatus = Literal["active", "inactive", "deprecated"]


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    agent_id: str
    node_id: str
    version: str
    status: PromptStatus
    description: str
    required_variables: list[str]
    optional_variables: list[str]
    output_contract: str
    body: str
    source_path: Path | None = None


@dataclass(frozen=True)
class PromptRenderRequest:
    agent_id: str
    node_id: str
    variables: dict[str, Any]
    template_version: str | None = None


@dataclass(frozen=True)
class PromptRenderResult:
    agent_id: str
    node_id: str
    template_id: str
    template_version: str
    output_contract: str
    rendered_text: str
    rendered_hash: str
    variables_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserFacingFailure:
    code: str
    message: str
    retryable: bool
    user_action_required: bool
    missing_variables: list[str] = field(default_factory=list)
