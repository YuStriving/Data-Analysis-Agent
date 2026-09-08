from __future__ import annotations

from copy import deepcopy

from agent_backend.foundation.contracts.context import (
    ContextBuildResult,
    ContextBundle,
    ContextMeta,
    ContextPolicy,
    ContextSource,
    RuntimeContext,
    SchemaContext,
)
from agent_backend.foundation.contracts.memory import ContextInjectionBundle, NodeCheckpointSnapshot
from agent_backend.foundation.contracts.task import AnalysisTaskRequest

from agent_backend.capabilities.agent_runtime.context.classifier import classify_task


class ContextBuilder:
    def build(
        self,
        source: ContextSource,
        policy: ContextPolicy,
    ) -> ContextBuildResult:
        missing_sections = self._missing_required_sections(source, policy)
        if missing_sections:
            return ContextBuildResult(
                status="missing_required_context",
                missing_sections=missing_sections,
            )

        bundle_data = {}
        truncated_sections: list[str] = []
        warnings: list[str] = []

        for section in policy.allowed_sections:
            if section == "meta":
                continue
            value = getattr(source, self._source_attr(section))
            if value is None:
                continue
            prepared, was_truncated = self._apply_limits(section, value, policy)
            if was_truncated:
                truncated_sections.append(section)
            bundle_data[section] = prepared

        runtime = bundle_data.get("runtime")
        if runtime is None and "runtime" in policy.allowed_sections:
            runtime = RuntimeContext(
                agent_name=policy.agent_name,
                node_name=policy.node_name,
                policy_name=policy.policy_name,
                policy_version=policy.policy_version,
            )
            bundle_data["runtime"] = runtime

        included_sections = list(bundle_data)
        meta = ContextMeta(
            included_sections=[*included_sections, "meta"],
            missing_sections=[],
            truncated_sections=truncated_sections,
            warnings=warnings,
        )
        if "meta" in policy.allowed_sections:
            bundle_data["meta"] = meta

        return ContextBuildResult(
            status="ok",
            bundle=ContextBundle(**bundle_data),
            missing_sections=[],
            warnings=warnings,
        )

    def _missing_required_sections(
        self,
        source: ContextSource,
        policy: ContextPolicy,
    ) -> list[str]:
        missing = []
        for section in policy.required_sections:
            value = getattr(source, self._source_attr(section))
            if value is None or self._section_is_empty(section, value):
                missing.append(section)
        return missing

    def _source_attr(self, section: str) -> str:
        if section == "schema":
            return "schema_context"
        return section

    def _section_is_empty(self, section: str, value: object) -> bool:
        if section == "dataset":
            return not getattr(value, "selected_dataset_id", None)
        if section == "schema":
            return not (
                getattr(value, "schema_summary", "")
                or getattr(value, "semantic_schema_summary", "")
                or getattr(value, "field_summary", {})
            )
        if section == "repair":
            return not (
                getattr(value, "failed_sql", None)
                and getattr(value, "error_message", None)
            )
        if section == "execution_result":
            return not (
                getattr(value, "executed_sql", None)
                or getattr(value, "result_summary", "")
                or getattr(value, "table_preview", [])
            )
        return False

    def _apply_limits(
        self,
        section: str,
        value: object,
        policy: ContextPolicy,
    ) -> tuple[object, bool]:
        prepared = deepcopy(value)
        was_truncated = False

        if section == "schema" and isinstance(prepared, SchemaContext):
            was_truncated = self._truncate_schema(prepared, policy)
        elif section == "conversation" and policy.max_conversation_chars is not None:
            summary = getattr(prepared, "conversation_summary", "")
            truncated = self._truncate_text(summary, policy.max_conversation_chars)
            prepared.conversation_summary = truncated
            was_truncated = len(truncated) < len(summary)
        elif section == "repair":
            avoid_errors = getattr(prepared, "avoid_errors", [])
            prepared.avoid_errors = list(avoid_errors[: policy.max_repair_items])
            was_truncated = len(prepared.avoid_errors) < len(avoid_errors)
        elif section == "execution_result" and not policy.include_raw_rows:
            rows = getattr(prepared, "table_preview", [])
            if rows:
                prepared.table_preview = []
                prepared.truncated = True
                was_truncated = True

        return prepared, was_truncated

    def _truncate_schema(self, schema: SchemaContext, policy: ContextPolicy) -> bool:
        if policy.max_schema_chars is None:
            return False

        truncated = False
        schema.schema_summary, changed = self._truncate_text_with_flag(
            schema.schema_summary,
            policy.max_schema_chars,
        )
        truncated = truncated or changed

        remaining_chars = max(policy.max_schema_chars - len(schema.schema_summary), 0)
        schema.semantic_schema_summary, changed = self._truncate_text_with_flag(
            schema.semantic_schema_summary,
            remaining_chars,
        )
        truncated = truncated or changed

        if truncated:
            schema.truncated = True
        return truncated

    def _truncate_text_with_flag(self, text: str, max_chars: int) -> tuple[str, bool]:
        truncated = self._truncate_text(text, max_chars)
        return truncated, len(truncated) < len(text)

    def _truncate_text(self, text: str, max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        return text[:max_chars]


def build_context(
    request: AnalysisTaskRequest,
    snapshot: NodeCheckpointSnapshot | None = None,
) -> dict:
    profile = classify_task(request, snapshot=snapshot)
    bundle = ContextInjectionBundle(
        task_type=profile.task_type,
        injection_strategy=profile.injection_strategy,
        task_id=request.task_id,
        trace_id=request.trace_id,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        session_id=snapshot.session_id if snapshot is not None else request.task_id,
        dataset_ids=list(request.dataset_ids),
        hot_context={},
        confirmed_facts=[],
        conversation_summary="",
        injected_context_version="v1",
    )
    if snapshot is not None:
        bundle.hot_context = dict(snapshot.core.context_state.hot_context)
        bundle.confirmed_facts = list(snapshot.core.context_state.confirmed_facts)
        bundle.conversation_summary = snapshot.core.context_state.conversation_summary
        bundle.injected_context_version = snapshot.core.context_state.injected_context_version
    return bundle.model_dump()
