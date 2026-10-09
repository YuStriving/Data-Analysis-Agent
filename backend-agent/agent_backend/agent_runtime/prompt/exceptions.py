from __future__ import annotations


class PromptHubError(Exception):
    """Base exception for prompt hub failures."""


class PromptTemplateFormatError(PromptHubError):
    def __init__(self, message: str, source_path: str | None = None) -> None:
        self.source_path = source_path
        super().__init__(message)


class PromptTemplateNotFoundError(PromptHubError):
    def __init__(
        self,
        agent_id: str,
        node_id: str,
        template_version: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        self.template_version = template_version
        version_hint = f" version={template_version}" if template_version else " active version"
        super().__init__(f"Prompt template not found for {agent_id}.{node_id}{version_hint}")


class DuplicateActivePromptTemplateError(PromptHubError):
    def __init__(self, agent_id: str, node_id: str, template_ids: list[str]) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        self.template_ids = template_ids
        super().__init__(
            f"Multiple active prompt templates for {agent_id}.{node_id}: {template_ids}"
        )


class MissingPromptVariablesError(PromptHubError):
    def __init__(
        self,
        agent_id: str,
        node_id: str,
        template_id: str | None,
        template_version: str | None,
        missing_variables: list[str],
    ) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        self.template_id = template_id
        self.template_version = template_version
        self.missing_variables = missing_variables
        super().__init__(
            f"Missing prompt variables for {agent_id}.{node_id}: {missing_variables}"
        )


class MissingPromptInputSectionsError(PromptHubError):
    def __init__(
        self,
        agent_id: str,
        node_id: str,
        missing_sections: list[str],
    ) -> None:
        self.agent_id = agent_id
        self.node_id = node_id
        self.missing_sections = missing_sections
        super().__init__(
            f"Missing prompt input sections for {agent_id}.{node_id}: {missing_sections}"
        )


class UndeclaredPromptVariablesError(PromptHubError):
    def __init__(
        self,
        template_id: str,
        variable_names: list[str],
    ) -> None:
        self.template_id = template_id
        self.variable_names = variable_names
        super().__init__(
            f"Prompt template {template_id} references undeclared variables: {variable_names}"
        )
