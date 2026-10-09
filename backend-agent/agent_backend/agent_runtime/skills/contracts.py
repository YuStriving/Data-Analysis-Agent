from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
