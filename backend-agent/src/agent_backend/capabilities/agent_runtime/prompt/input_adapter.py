from __future__ import annotations

from typing import Any

from agent_backend.capabilities.agent_runtime.context.contracts import (
    ContextBundle,
    ConversationContext,
    PreviousTurnContext,
)
from agent_backend.capabilities.agent_runtime.prompt.contracts import PromptRenderRequest
from agent_backend.capabilities.agent_runtime.prompt.exceptions import (
    MissingPromptInputSectionsError,
    PromptTemplateNotFoundError,
)


class PromptInputAdapter:
    def build_prompt_request(
        self,
        *,
        agent_id: str,
        node_id: str,
        bundle: ContextBundle,
        template_version: str | None = None,
    ) -> PromptRenderRequest:
        if agent_id == "data_analysis_agent" and node_id == "generate_sql":
            return self._build_generate_sql_request(
                agent_id=agent_id,
                node_id=node_id,
                bundle=bundle,
                template_version=template_version,
            )
        raise PromptTemplateNotFoundError(agent_id, node_id, template_version)

    def _build_generate_sql_request(
        self,
        *,
        agent_id: str,
        node_id: str,
        bundle: ContextBundle,
        template_version: str | None,
    ) -> PromptRenderRequest:
        missing_sections = self._missing_generate_sql_sections(bundle)
        if missing_sections:
            raise MissingPromptInputSectionsError(agent_id, node_id, missing_sections)

        assert bundle.request is not None
        assert bundle.dataset is not None
        assert bundle.schema_context is not None
        assert bundle.access_context is not None

        variables = {
            "user_question": bundle.request.question,
            "dataset_context": bundle.dataset.model_dump(mode="json", exclude_none=True),
            "schema_context": bundle.schema_context.model_dump(mode="json", exclude_none=True),
            "access_context": bundle.access_context.model_dump(mode="json", exclude_none=True),
            "metric_context": bundle.schema_context.metric_mapping,
            "time_context": bundle.schema_context.time_field_hints,
            "recent_context": self._build_recent_context(
                conversation=bundle.conversation,
                previous_turn=bundle.previous_turn,
            ),
        }
        return PromptRenderRequest(
            agent_id=agent_id,
            node_id=node_id,
            template_version=template_version,
            variables=variables,
        )

    def _missing_generate_sql_sections(self, bundle: ContextBundle) -> list[str]:
        missing_sections = []
        if bundle.request is None:
            missing_sections.append("request")
        if bundle.dataset is None:
            missing_sections.append("dataset")
        if bundle.schema_context is None:
            missing_sections.append("schema")
        if bundle.access_context is None:
            missing_sections.append("access")
        return missing_sections

    def _build_recent_context(
        self,
        *,
        conversation: ConversationContext | None,
        previous_turn: PreviousTurnContext | None,
    ) -> dict[str, Any]:
        recent_context: dict[str, Any] = {}
        if conversation is not None:
            recent_context["conversation"] = conversation.model_dump(
                mode="json",
                exclude_none=True,
            )
        if previous_turn is not None:
            recent_context["previous_turn"] = previous_turn.model_dump(
                mode="json",
                exclude_none=True,
            )
        return recent_context


def build_prompt_request(
    *,
    agent_id: str,
    node_id: str,
    bundle: ContextBundle,
    template_version: str | None = None,
) -> PromptRenderRequest:
    return PromptInputAdapter().build_prompt_request(
        agent_id=agent_id,
        node_id=node_id,
        bundle=bundle,
        template_version=template_version,
    )
