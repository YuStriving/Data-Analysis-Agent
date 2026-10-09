from __future__ import annotations

from agent_backend.agent_runtime.prompt.contracts import (
    PromptRenderRequest,
    PromptRenderResult,
)
from agent_backend.agent_runtime.prompt.registry import PromptRegistry
from agent_backend.agent_runtime.prompt.renderer import PromptRenderer

_DEFAULT_REGISTRY: PromptRegistry | None = None


def render_prompt(request: PromptRenderRequest) -> PromptRenderResult:
    registry = _get_default_registry()
    template = registry.get_template(
        request.agent_id,
        request.node_id,
        request.template_version,
    )
    return PromptRenderer().render(template, request)


def render_system_prompt(agent_id: str, variables: dict[str, object] | None = None) -> PromptRenderResult:
    return render_prompt(
        PromptRenderRequest(
            agent_id=agent_id,
            node_id="system",
            variables=dict(variables or {}),
        )
    )


def _get_default_registry() -> PromptRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = PromptRegistry()
    return _DEFAULT_REGISTRY
