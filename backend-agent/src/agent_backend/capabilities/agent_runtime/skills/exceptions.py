from __future__ import annotations


class NodeSkillError(Exception):
    """Base exception for Node Skill failures."""


class NodeSkillFormatError(NodeSkillError):
    def __init__(self, message: str, source_path: str | None = None) -> None:
        self.source_path = source_path
        super().__init__(message)


class NodeSkillNotFoundError(NodeSkillError):
    def __init__(self, agent_id: str, node_id: str) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        super().__init__(f"Node Skill binding not found for {agent_id}.{node_id}")


class MissingSkillContextError(NodeSkillError):
    def __init__(
        self,
        agent_id: str,
        node_id: str,
        skill_id: str | None,
        missing_sections: list[str],
    ) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        self.skill_id = skill_id
        self.missing_sections = missing_sections
        super().__init__(
            f"Missing Node Skill context for {agent_id}.{node_id}: {missing_sections}"
        )
