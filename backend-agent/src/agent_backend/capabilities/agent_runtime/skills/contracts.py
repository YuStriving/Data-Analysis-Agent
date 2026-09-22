from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agent_backend.foundation.contracts.context import ContextBundle
from agent_backend.foundation.llm import LlmResponseFormat


NodeSkillStatus = Literal["active", "inactive", "deprecated"]


@dataclass(frozen=True)
class NodeSkill:
    skill_id: str
    agent_id: str
    nodes: list[str]
    version: str
    status: NodeSkillStatus
    description: str
    required_context: list[str]
    optional_context: list[str]
    output_contract: str
    response_format: LlmResponseFormat
    body: str
    source_path: Path | None = None


@dataclass(frozen=True)
class SkillRenderRequest:
    agent_id: str
    node_id: str
    bundle: ContextBundle
    skill_path: Path | None = None


@dataclass(frozen=True)
class SkillRenderResult:
    agent_id: str
    node_id: str
    skill_id: str
    skill_version: str
    output_contract: str
    response_format: LlmResponseFormat
    rendered_text: str
    rendered_hash: str
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def template_id(self) -> str:
        return self.skill_id

    @property
    def template_version(self) -> str:
        return self.skill_version
