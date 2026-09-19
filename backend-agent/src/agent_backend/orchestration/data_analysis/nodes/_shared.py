from __future__ import annotations

from typing import Any

from agent_backend.orchestration.state import AgentState


def enter_node(state: AgentState, node_id: str) -> AgentState:
    graph = _ensure_graph(state)
    previous_node = graph.get("node_id") or state.get("node_id")
    graph["previous_node"] = previous_node
    graph["node_id"] = node_id
    graph["node_name"] = node_id
    graph["node_status"] = "running"
    graph["resume_cursor"] = node_id
    graph["next_node"] = None

    state["previous_node"] = previous_node
    state["node_id"] = node_id
    state["node_name"] = node_id
    state["node_status"] = "running"
    state["current_step"] = node_id
    state["resume_cursor"] = node_id
    state["next_node"] = None
    return state


def complete_node(state: AgentState, next_node: str | None) -> AgentState:
    graph = _ensure_graph(state)
    graph["node_status"] = "completed"
    graph["next_node"] = next_node
    state["node_status"] = "completed"
    state["next_node"] = next_node
    return state


def fail_node(
    state: AgentState,
    *,
    code: str,
    message: str,
    failure_stage: str,
    user_action_required: bool,
    recoverable: bool,
) -> AgentState:
    graph = _ensure_graph(state)
    error = _ensure_error(state)
    graph["node_status"] = "failed"
    graph["next_node"] = "fail_task"
    error.update(
        {
            "has_error": True,
            "error_code": code,
            "error_message": message,
            "failure_stage": failure_stage,
            "user_action_required": user_action_required,
            "recoverable": recoverable,
        }
    )
    state["node_status"] = "failed"
    state["next_node"] = "fail_task"
    state["failure_stage"] = failure_stage
    append_event(
        state,
        "task_failed",
        {
            "error_code": code,
            "message": message,
            "failure_stage": failure_stage,
            "user_action_required": user_action_required,
            "recoverable": recoverable,
        },
        level="error",
    )
    return state


def append_event(
    state: AgentState,
    event_type: str,
    payload: dict[str, Any],
    *,
    level: str = "info",
) -> dict[str, Any]:
    graph = _ensure_graph(state)
    event_seq = int(graph.get("event_seq", state.get("event_seq", 0))) + 1
    graph["event_seq"] = event_seq
    state["event_seq"] = event_seq
    event = {
        "seq": event_seq,
        "task_id": _task_value(state, "task_id"),
        "trace_id": _task_value(state, "trace_id"),
        "event_type": event_type,
        "level": level,
        "node_id": graph.get("node_id", state.get("node_id")),
        "payload": payload,
    }
    events = graph.setdefault("events", [])
    events.append(event)
    return event


def has_error(state: AgentState) -> bool:
    return bool(state.get("error", {}).get("has_error"))


def _task_value(state: AgentState, key: str) -> Any:
    return state.get("task", {}).get(key, state.get(key))


def _ensure_graph(state: AgentState) -> dict[str, Any]:
    graph = state.setdefault("graph", {})
    graph.setdefault("event_seq", state.get("event_seq", 0))
    graph.setdefault("events", [])
    return graph


def _ensure_error(state: AgentState) -> dict[str, Any]:
    error = state.setdefault("error", {})
    error.setdefault("has_error", False)
    error.setdefault("error_code", None)
    error.setdefault("error_message", None)
    error.setdefault("failure_stage", None)
    error.setdefault("user_action_required", False)
    error.setdefault("recoverable", False)
    return error
