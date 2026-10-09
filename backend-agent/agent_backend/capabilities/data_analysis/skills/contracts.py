from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_backend.capabilities.data_analysis.contracts.context import ContextBundle
from agent_backend.foundation.llm import LlmResponseFormat


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
