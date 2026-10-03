from __future__ import annotations

from typing import Any

from agent_backend.orchestration.data_analysis.nodes._shared import (
    append_event,
    enter_node,
)
from agent_backend.orchestration.state import AgentState


def fail_task(state: AgentState) -> AgentState:
    enter_node(state, "fail_task")
    error = state.setdefault("error", {})
    output = state.setdefault("output", {})
    message = error.get("error_message") or "The analysis task failed."
    output["final_answer"] = message
    state["final_answer"] = message
    state["node_status"] = "failed"
    state["graph"]["node_status"] = "failed"
    payload: dict[str, Any] = {
        "error_code": error.get("error_code"),
        "message": message,
        "failure_stage": error.get("failure_stage"),
        "user_action_required": bool(error.get("user_action_required", False)),
        "recoverable": bool(error.get("recoverable", False)),
    }
    if (tool_error := error.get("tool_error")) is not None:
        payload["tool_error"] = tool_error
    append_event(
        state,
        "task_failed",
        payload,
        level="error",
    )
    return state
