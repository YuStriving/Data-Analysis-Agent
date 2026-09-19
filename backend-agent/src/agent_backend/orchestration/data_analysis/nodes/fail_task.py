from __future__ import annotations

from agent_backend.orchestration.data_analysis.nodes._shared import append_event, enter_node
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
    append_event(
        state,
        "task_failed",
        {
            "error_code": error.get("error_code"),
            "message": message,
            "failure_stage": error.get("failure_stage"),
            "user_action_required": bool(error.get("user_action_required", False)),
            "recoverable": bool(error.get("recoverable", False)),
        },
        level="error",
    )
    return state
