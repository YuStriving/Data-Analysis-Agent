from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from agent_backend.capabilities.agent_runtime.prompt.contracts import PromptTemplate
from agent_backend.capabilities.agent_runtime.prompt.exceptions import (
    DuplicateActivePromptTemplateError,
    PromptTemplateNotFoundError,
)
from agent_backend.capabilities.agent_runtime.prompt.loader import (
    has_front_matter,
    load_prompt_template,
)


class PromptRegistry:
    def __init__(self, template_roots: list[Path] | None = None) -> None:
        self.template_roots = template_roots or [_default_capabilities_root()]
        self._templates: dict[tuple[str, str, str], PromptTemplate] = {}
        self._active_index: dict[tuple[str, str], PromptTemplate] = {}
        self.reload()

    def reload(self) -> None:
        templates: dict[tuple[str, str, str], PromptTemplate] = {}
        active_candidates: dict[tuple[str, str], list[PromptTemplate]] = defaultdict(list)

        for root in self.template_roots:
            if not root.exists():
                continue
            for path in root.glob("*/prompts/**/*.md"):
                if not has_front_matter(path):
                    continue
                template = load_prompt_template(path)
                key = (template.agent_id, template.node_id, template.version)
                templates[key] = template
                if template.status == "active":
                    active_candidates[(template.agent_id, template.node_id)].append(template)

        active_index: dict[tuple[str, str], PromptTemplate] = {}
        for key, candidates in active_candidates.items():
            if len(candidates) > 1:
                raise DuplicateActivePromptTemplateError(
                    key[0],
                    key[1],
                    [template.template_id for template in candidates],
                )
            active_index[key] = candidates[0]

        self._templates = templates
        self._active_index = active_index

    def get_template(
        self,
        agent_id: str,
        node_id: str,
        template_version: str | None = None,
    ) -> PromptTemplate:
        if template_version:
            try:
                return self._templates[(agent_id, node_id, template_version)]
            except KeyError as exc:
                raise PromptTemplateNotFoundError(
                    agent_id,
                    node_id,
                    template_version,
                ) from exc

        try:
            return self._active_index[(agent_id, node_id)]
        except KeyError as exc:
            raise PromptTemplateNotFoundError(agent_id, node_id) from exc


def _default_capabilities_root() -> Path:
    return Path(__file__).resolve().parents[2]
