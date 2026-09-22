from __future__ import annotations

from agent_backend.capabilities.agent_runtime.skills.bindings import resolve_node_skill_path
from agent_backend.capabilities.agent_runtime.skills.contracts import SkillRenderRequest
from agent_backend.foundation.contracts.context import ContextBundle


class SkillInputAdapter:
    def build_skill_request(
        self,
        *,
        agent_id: str,
        node_id: str,
        bundle: ContextBundle,
    ) -> SkillRenderRequest:
        return SkillRenderRequest(
            agent_id=agent_id,
            node_id=node_id,
            bundle=bundle,
            skill_path=resolve_node_skill_path(agent_id, node_id),
        )


def build_skill_request(
    *,
    agent_id: str,
    node_id: str,
    bundle: ContextBundle,
) -> SkillRenderRequest:
    return SkillInputAdapter().build_skill_request(
        agent_id=agent_id,
        node_id=node_id,
        bundle=bundle,
    )
