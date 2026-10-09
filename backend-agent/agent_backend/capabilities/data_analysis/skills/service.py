from __future__ import annotations

from agent_backend.agent_runtime.skills.loader import load_node_skill
from agent_backend.capabilities.data_analysis.skills.bindings import (
    resolve_node_skill_path,
)
from agent_backend.capabilities.data_analysis.skills.contracts import (
    SkillRenderRequest,
    SkillRenderResult,
)
from agent_backend.capabilities.data_analysis.skills.renderer import NodeSkillRenderer


def render_node_skill(request: SkillRenderRequest) -> SkillRenderResult:
    skill_path = request.skill_path or resolve_node_skill_path(request.agent_id, request.node_id)
    skill = load_node_skill(skill_path)
    return NodeSkillRenderer().render(skill, request)
