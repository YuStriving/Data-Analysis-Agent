from __future__ import annotations

from typing import Any

from agent_backend.orchestration.data_analysis.nodes._shared import append_event, complete_node, enter_node, fail_node
from agent_backend.orchestration.state import AgentState


def load_task_context(state: AgentState) -> AgentState:
    enter_node(state, "load_task_context")
    task = state.setdefault("task", {})
    context = state.setdefault("context", {})

    _sync_flat_task_fields(state)
    missing_identity = [
        key
        for key in ("task_id", "trace_id", "tenant_id", "user_id", "session_id")
        if not task.get(key)
    ]
    if missing_identity:
        return fail_node(
            state,
            code="missing_task_identity",
            message=f"Task identity is incomplete: {', '.join(missing_identity)}.",
            failure_stage="load_task_context",
            user_action_required=False,
            recoverable=False,
        )

    question = str(task.get("question", "")).strip()
    if not question:
        return fail_node(
            state,
            code="missing_user_question",
            message="The analysis question is missing.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=True,
        )

    access_context = _access_context(task)
    if not access_context:
        return fail_node(
            state,
            code="missing_access_context",
            message="Access context is missing.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=True,
        )
    if access_context.get("readonly") is not True:
        return fail_node(
            state,
            code="readonly_required",
            message="Agent execution requires a readonly access context.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=False,
        )

    selected_dataset_id = _select_dataset(state)
    if selected_dataset_id is None:
        return fail_node(
            state,
            code="missing_dataset",
            message="No dataset was selected for this analysis task.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=True,
        )
    if selected_dataset_id == "__unsupported_multi_dataset__":
        return fail_node(
            state,
            code="unsupported_multi_dataset",
            message="MVP data analysis supports exactly one selected dataset.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=True,
        )

    allowed_dataset_ids = list(access_context.get("allowed_dataset_ids", []))
    if selected_dataset_id not in allowed_dataset_ids:
        return fail_node(
            state,
            code="unauthorized_dataset",
            message=f"Dataset is not authorized for this task: {selected_dataset_id}.",
            failure_stage="load_task_context",
            user_action_required=True,
            recoverable=False,
        )

    dataset_ids = list(task.get("dataset_ids", []))
    source = "explicit" if dataset_ids else "session"
    inferred = source == "session"
    context["selected_dataset_id"] = selected_dataset_id
    context["inferred_dataset"] = inferred
    context["dataset_selection_source"] = source
    context["injected_context_version"] = context.get("injected_context_version", "v1")

    state["dataset_ids"] = [selected_dataset_id]
    state["injected_context_version"] = context["injected_context_version"]
    append_event(
        state,
        "task_context_loaded",
        {
            "task_type": task.get("task_type", state.get("task_type", "unknown")),
            "selected_dataset_id": selected_dataset_id,
            "dataset_selection_source": source,
            "inferred_dataset": inferred,
        },
    )
    return complete_node(state, "build_context")


def _sync_flat_task_fields(state: AgentState) -> None:
    task = state.setdefault("task", {})
    for key in ("task_id", "trace_id", "tenant_id", "user_id", "session_id", "question", "dataset_ids", "task_type"):
        if key not in task and key in state:
            task[key] = state[key]  # type: ignore[literal-required]
        if key in task:
            state[key] = task[key]  # type: ignore[literal-required]


def _access_context(task: dict[str, Any]) -> dict[str, Any]:
    access_context = task.get("access_context")
    if isinstance(access_context, dict):
        return access_context
    return {}


def _select_dataset(state: AgentState) -> str | None:
    task = state.get("task", {})
    context = state.setdefault("context", {})
    dataset_ids = list(task.get("dataset_ids", state.get("dataset_ids", [])))
    if len(dataset_ids) > 1:
        return "__unsupported_multi_dataset__"
    if len(dataset_ids) == 1:
        return str(dataset_ids[0])
    recent_dataset_id = context.get("recent_dataset_id")
    if isinstance(recent_dataset_id, str) and recent_dataset_id:
        return recent_dataset_id
    return None
