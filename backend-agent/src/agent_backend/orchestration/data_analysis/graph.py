from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_backend.capabilities.agent_runtime.prompt import PromptBudgetGuard
from agent_backend.capabilities.agent_runtime.tool_calling.runtime import (
    ToolCallingRuntime,
)
from agent_backend.capabilities.data_analysis.tools import (
    build_default_data_analysis_tool_runtime,
    validate_data_analysis_tool_runtime,
)
from agent_backend.foundation.llm import LlmClient
from agent_backend.orchestration.data_analysis.nodes import (
    build_chart,
    fail_task,
    interpret_result,
    load_task_context,
    persist_result,
    run_query,
    validate_sql,
)
from agent_backend.orchestration.data_analysis.nodes.build_context import (
    DatasetMetadataResolver,
    make_build_context_node,
)
from agent_backend.orchestration.data_analysis.nodes.generate_sql import (
    make_generate_sql_node,
)
from agent_backend.orchestration.state import AgentState


def build_data_analysis_graph(
    *,
    model_client: LlmClient,
    tool_runtime: ToolCallingRuntime | None = None,
    dataset_metadata_resolver: DatasetMetadataResolver | None = None,
    prompt_budget_guard: PromptBudgetGuard | None = None,
):
    dataset_metadata_by_id: dict[str, dict[str, Any]] = {}
    resolved_tool_runtime = _resolve_tool_runtime(tool_runtime, dataset_metadata_by_id)
    resolved_dataset_metadata_resolver = _metadata_resolver_with_cache(
        dataset_metadata_resolver,
        dataset_metadata_by_id,
    )

    workflow = StateGraph(AgentState)
    workflow.add_node("load_task_context", load_task_context)
    workflow.add_node(
        "build_context",
        _build_context_node(
            tool_runtime=resolved_tool_runtime,
            dataset_metadata_resolver=resolved_dataset_metadata_resolver,
        ),
    )
    workflow.add_node(
        "generate_sql",
        make_generate_sql_node(
            model_client=model_client,
            prompt_budget_guard=prompt_budget_guard,
        ),
    )
    workflow.add_node("validate_sql", validate_sql)
    workflow.add_node("run_query", run_query)
    workflow.add_node("interpret_result", interpret_result)
    workflow.add_node("build_chart", build_chart)
    workflow.add_node("persist_result", persist_result)
    workflow.add_node("fail_task", fail_task)

    workflow.add_edge(START, "load_task_context")
    workflow.add_conditional_edges(
        "load_task_context",
        _next_or_default("build_context"),
        {
            "build_context": "build_context",
            "fail_task": "fail_task",
        },
    )
    workflow.add_conditional_edges(
        "build_context",
        _next_or_default("generate_sql"),
        {
            "generate_sql": "generate_sql",
            "fail_task": "fail_task",
        },
    )
    workflow.add_conditional_edges(
        "generate_sql",
        _next_or_default("validate_sql"),
        {
            "validate_sql": "validate_sql",
            "fail_task": "fail_task",
        },
    )
    workflow.add_edge("validate_sql", "run_query")
    workflow.add_edge("run_query", "interpret_result")
    workflow.add_edge("interpret_result", "build_chart")
    workflow.add_edge("build_chart", "persist_result")
    workflow.add_edge("persist_result", END)
    workflow.add_edge("fail_task", END)
    return workflow.compile()


def _build_context_node(
    *,
    tool_runtime: ToolCallingRuntime,
    dataset_metadata_resolver: DatasetMetadataResolver | None,
) -> Callable[[AgentState], AgentState]:
    return make_build_context_node(
        tool_runtime=tool_runtime,
        dataset_metadata_resolver=dataset_metadata_resolver,
    )


def _next_or_default(default_next_node: str) -> Callable[[AgentState], str]:
    def _route(state: AgentState) -> str:
        next_node = state.get("graph", {}).get("next_node") or state.get("next_node")
        if next_node == "fail_task":
            return "fail_task"
        if isinstance(next_node, str) and next_node:
            return next_node
        return default_next_node

    return _route


def _resolve_tool_runtime(
    tool_runtime: ToolCallingRuntime | None,
    dataset_metadata_by_id: dict[str, dict[str, Any]],
) -> ToolCallingRuntime:
    resolved = tool_runtime or build_default_data_analysis_tool_runtime(dataset_metadata_by_id)
    validate_data_analysis_tool_runtime(resolved)
    return resolved


def _metadata_resolver_with_cache(
    dataset_metadata_resolver: DatasetMetadataResolver | None,
    dataset_metadata_by_id: dict[str, dict[str, Any]],
) -> DatasetMetadataResolver:
    def _resolve(state: AgentState, dataset_id: str) -> dict[str, Any] | None:
        metadata = (
            dataset_metadata_resolver(state, dataset_id)
            if dataset_metadata_resolver is not None
            else _resolve_dataset_metadata_from_state(state, dataset_id)
        )
        if metadata is None:
            return None
        copied_metadata = dict(metadata)
        dataset_metadata_by_id[dataset_id] = copied_metadata
        return copied_metadata

    return _resolve


def _resolve_dataset_metadata_from_state(state: AgentState, dataset_id: str) -> dict[str, Any] | None:
    context = state.get("context", {})
    by_id = context.get("dataset_metadata_by_id")
    if isinstance(by_id, dict) and isinstance(by_id.get(dataset_id), dict):
        return dict(by_id[dataset_id])
    metadata = context.get("dataset_metadata")
    if isinstance(metadata, dict) and metadata.get("dataset_id", dataset_id) == dataset_id:
        return dict(metadata)
    return None
