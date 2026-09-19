from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from agent_backend.capabilities.agent_runtime.context.builder import ContextBuilder
from agent_backend.capabilities.agent_runtime.context.contracts import (
    ContextIdentity,
    ContextSource,
    DatasetContext,
    RequestContext,
    SchemaContext,
)
from agent_backend.capabilities.agent_runtime.context.policies import (
    resolve_context_policy,
)
from agent_backend.capabilities.agent_runtime.tool_calling.contracts import (
    DatasetScope,
    ToolCallRequest,
)
from agent_backend.capabilities.agent_runtime.tool_calling.runtime import (
    ToolCallingRuntime,
)
from agent_backend.capabilities.data_analysis.contracts import validate_dataset_metadata
from agent_backend.foundation.access import AccessContext
from agent_backend.orchestration.data_analysis.nodes._shared import (
    append_event,
    complete_node,
    enter_node,
    fail_node,
    has_error,
)
from agent_backend.orchestration.state import AgentState

DatasetMetadataResolver = Callable[[AgentState, str], dict[str, Any] | None]


def build_context(
    state: AgentState,
    *,
    tool_runtime: ToolCallingRuntime | None = None,
    dataset_metadata_resolver: DatasetMetadataResolver | None = None,
) -> AgentState:
    enter_node(state, "build_context")
    if has_error(state):
        return state

    selected_dataset_id = state.get("context", {}).get("selected_dataset_id")
    if not isinstance(selected_dataset_id, str) or not selected_dataset_id:
        return fail_node(
            state,
            code="missing_selected_dataset",
            message="Selected dataset is missing before context build.",
            failure_stage="build_context",
            user_action_required=True,
            recoverable=True,
        )

    metadata = (dataset_metadata_resolver or _resolve_dataset_metadata)(state, selected_dataset_id)
    if metadata is None:
        return fail_node(
            state,
            code="dataset_context_not_found",
            message=f"Dataset metadata was not found: {selected_dataset_id}.",
            failure_stage="build_context",
            user_action_required=True,
            recoverable=True,
        )

    try:
        dataset_metadata = validate_dataset_metadata(metadata, expected_dataset_id=selected_dataset_id)
    except (ValidationError, ValueError) as exc:
        return fail_node(
            state,
            code="invalid_dataset_metadata",
            message=str(exc),
            failure_stage="build_context",
            user_action_required=True,
            recoverable=True,
        )
    metadata = dataset_metadata.to_runtime_metadata()

    runtime = tool_runtime
    if runtime is None:
        return fail_node(
            state,
            code="context_build_failed",
            message="ToolCallingRuntime is required to build schema context.",
            failure_stage="build_context",
            user_action_required=False,
            recoverable=True,
        )

    tool_result = _call_schema_tool(state, runtime, metadata)
    if not tool_result.success:
        error_message = tool_result.error.message if tool_result.error is not None else "Schema tool call failed."
        return fail_node(
            state,
            code="schema_context_not_found",
            message=error_message,
            failure_stage="build_context",
            user_action_required=False,
            recoverable=True,
        )

    schema_tool_data = dict(tool_result.data)
    relations = list(schema_tool_data.get("relations", []))
    if not relations:
        return fail_node(
            state,
            code="schema_context_empty",
            message=f"Schema context is empty for dataset: {selected_dataset_id}.",
            failure_stage="build_context",
            user_action_required=True,
            recoverable=True,
        )

    schema_context = _schema_context_from_relations(relations)
    context_bundle = _build_context_bundle(state, metadata, schema_context)
    if context_bundle is None:
        return fail_node(
            state,
            code="context_policy_failed",
            message="Required context sections are missing for generate_sql.",
            failure_stage="build_context",
            user_action_required=True,
            recoverable=True,
        )

    context = state.setdefault("context", {})
    context["dataset_context"] = _dataset_context(metadata, selected_dataset_id)
    context["schema_context"] = schema_context.model_dump()
    context["context_bundle"] = context_bundle
    context["injected_context_version"] = "v1"
    if "normalized_relation_id" in schema_tool_data:
        context["normalized_relation_id"] = schema_tool_data["normalized_relation_id"]
    warnings = list(schema_tool_data.get("warnings", []))
    context["warnings"] = warnings
    state["injected_context_version"] = "v1"

    append_event(
        state,
        "context_built",
        {
            "selected_dataset_id": selected_dataset_id,
            "dataset_type": metadata.get("dataset_type"),
            "schema_relation_count": len(relations),
            "truncated": bool(schema_context.truncated),
            "context_version": "v1",
        },
    )
    return complete_node(state, "generate_sql")


def make_build_context_node(
    *,
    tool_runtime: ToolCallingRuntime,
    dataset_metadata_resolver: DatasetMetadataResolver | None = None,
) -> Callable[[AgentState], AgentState]:
    def _node(state: AgentState) -> AgentState:
        return build_context(
            state,
            tool_runtime=tool_runtime,
            dataset_metadata_resolver=dataset_metadata_resolver,
        )

    return _node


def _call_schema_tool(state: AgentState, runtime: ToolCallingRuntime, metadata: dict[str, Any]):
    request = _schema_tool_request(state, metadata)
    return asyncio.run(runtime.call(request))


def _schema_tool_request(state: AgentState, metadata: dict[str, Any]) -> ToolCallRequest:
    task = state.get("task", {})
    access_context = dict(task.get("access_context", {}))
    selected_dataset_id = str(state.get("context", {}).get("selected_dataset_id"))
    dataset_type = str(metadata.get("dataset_type", ""))
    args = _schema_tool_args(selected_dataset_id, dataset_type, metadata)
    return ToolCallRequest(
        tool_call_id=f"schema-{uuid4().hex}",
        tool_name=_schema_tool_name(dataset_type),
        tool_version="v1",
        agent_name="data_analysis_agent",
        agent_version="v1",
        node_id="build_context",
        task_id=str(task.get("task_id", state.get("task_id", ""))),
        trace_id=str(task.get("trace_id", state.get("trace_id", ""))),
        session_id=str(task.get("session_id", state.get("session_id", ""))),
        tenant_id=str(task.get("tenant_id", state.get("tenant_id", ""))),
        user_id=str(task.get("user_id", state.get("user_id", ""))),
        dataset_scope=DatasetScope(
            selected_dataset_id=selected_dataset_id,
            allowed_dataset_ids=list(access_context.get("allowed_dataset_ids", [])),
            dataset_types={selected_dataset_id: dataset_type},
            permissions=["dataset:read"],
        ),
        args=args,
        timeout_ms=int(metadata.get("schema_timeout_ms", 10000)),
    )


def _schema_tool_name(dataset_type: str) -> str:
    if dataset_type == "mysql":
        return "mysql.schema_reader"
    if dataset_type in {"csv", "xls", "xlsx"}:
        return "file.relation_normalizer"
    return "unsupported.schema_reader"


def _schema_tool_args(dataset_id: str, dataset_type: str, metadata: dict[str, Any]) -> dict[str, Any]:
    if dataset_type == "mysql":
        args: dict[str, Any] = {
            "dataset_id": dataset_id,
            "include_sample_values": bool(metadata.get("include_sample_values", False)),
            "sample_rows": int(metadata.get("sample_rows", 3)),
        }
        if metadata.get("table_names"):
            args["table_names"] = list(metadata["table_names"])
        if metadata.get("max_tables"):
            args["max_tables"] = int(metadata["max_tables"])
        if metadata.get("max_columns_per_table"):
            args["max_columns_per_table"] = int(metadata["max_columns_per_table"])
        return args
    if dataset_type in {"csv", "xls", "xlsx"}:
        return {
            "dataset_id": dataset_id,
            "dataset_type": dataset_type,
            "file_ref": metadata.get("file_ref", ""),
            "sheet_names": list(metadata.get("sheet_names", [])),
            "header_row": int(metadata.get("header_row", 1)),
            "sample_rows": int(metadata.get("sample_rows", 20)),
            "max_rows_to_inspect": int(metadata.get("max_rows_to_inspect", 1000)),
        }
    return {"dataset_id": dataset_id}


def _build_context_bundle(
    state: AgentState,
    metadata: dict[str, Any],
    schema_context: SchemaContext,
) -> dict[str, Any] | None:
    task = state.get("task", {})
    selected_dataset_id = str(state.get("context", {}).get("selected_dataset_id"))
    try:
        access_context = AccessContext(**dict(task.get("access_context", {})))
    except ValidationError:
        return None
    source = ContextSource(
        identity=ContextIdentity(
            task_id=str(task.get("task_id", state.get("task_id", ""))),
            trace_id=str(task.get("trace_id", state.get("trace_id", ""))),
            tenant_id=str(task.get("tenant_id", state.get("tenant_id", ""))),
            user_id=str(task.get("user_id", state.get("user_id", ""))),
            session_id=str(task.get("session_id", state.get("session_id", ""))),
        ),
        request=RequestContext(
            question=str(task.get("question", state.get("question", ""))),
            task_type=str(task.get("task_type", state.get("task_type", "unknown"))),
        ),
        access=access_context,
        dataset=DatasetContext(
            available_dataset_ids=list(access_context.allowed_dataset_ids),
            selected_dataset_id=selected_dataset_id,
            last_used_dataset_id=state.get("context", {}).get("recent_dataset_id"),
        ),
        schema=schema_context,
    )
    policy = resolve_context_policy("data_analysis_agent", "generate_sql")
    result = ContextBuilder().build(source, policy)
    if result.status != "ok" or result.bundle is None:
        return None
    return result.bundle.model_dump(mode="json", by_alias=True)


def _schema_context_from_relations(relations: list[dict[str, Any]]) -> SchemaContext:
    summary_lines: list[str] = []
    field_summary: dict[str, Any] = {}
    for relation in relations:
        relation_name = str(relation.get("relation_name", "unknown_relation"))
        columns = list(relation.get("columns", []))
        column_parts = [
            f"{column.get('name')} {column.get('data_type', column.get('type', 'unknown'))}"
            for column in columns
        ]
        summary_lines.append(f"{relation_name}({', '.join(column_parts)})")
        field_summary[relation_name] = {
            "display_name": relation.get("display_name", relation_name),
            "source_type": relation.get("source_type"),
            "source_name": relation.get("source_name"),
            "columns": columns,
        }
    return SchemaContext(
        schema_summary="\n".join(summary_lines),
        field_summary=field_summary,
        truncated=False,
    )


def _dataset_context(metadata: dict[str, Any], selected_dataset_id: str) -> dict[str, Any]:
    return {
        "dataset_id": selected_dataset_id,
        "dataset_type": metadata.get("dataset_type"),
        "display_name": metadata.get("display_name", selected_dataset_id),
        "source": metadata.get("source"),
    }


def _resolve_dataset_metadata(state: AgentState, dataset_id: str) -> dict[str, Any] | None:
    context = state.get("context", {})
    by_id = context.get("dataset_metadata_by_id")
    if isinstance(by_id, dict) and isinstance(by_id.get(dataset_id), dict):
        return dict(by_id[dataset_id])
    metadata = context.get("dataset_metadata")
    if isinstance(metadata, dict) and metadata.get("dataset_id", dataset_id) == dataset_id:
        return dict(metadata)
    return None
