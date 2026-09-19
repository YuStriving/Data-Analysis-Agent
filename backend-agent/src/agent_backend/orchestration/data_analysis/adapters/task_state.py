from __future__ import annotations

from agent_backend.capabilities.agent_runtime.context.classifier import classify_task
from agent_backend.foundation.contracts.task import AnalysisTaskRequest
from agent_backend.orchestration.state import AgentState


def request_to_initial_state(
    request: AnalysisTaskRequest,
    *,
    request_source: str = "http",
) -> AgentState:
    profile = classify_task(request)
    access_context = request.access_context.model_dump()
    state: AgentState = {
        "task": {
            "task_id": request.task_id,
            "trace_id": request.trace_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "question": request.question,
            "dataset_ids": list(request.dataset_ids),
            "access_context": access_context,
            "task_type": profile.task_type,
            "request_source": request_source,
        },
        "graph": {
            "node_status": "pending",
            "event_seq": 0,
            "events": [],
        },
        "context": {
            "selected_dataset_id": None,
            "inferred_dataset": False,
            "dataset_selection_source": "none",
            "recent_dataset_id": None,
            "injected_context_version": "v1",
            "warnings": [],
        },
        "analysis": {},
        "output": {"warnings": []},
        "error": {
            "has_error": False,
            "error_code": None,
            "error_message": None,
            "failure_stage": None,
            "user_action_required": False,
            "recoverable": False,
        },
        "task_id": request.task_id,
        "trace_id": request.trace_id,
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "session_id": request.session_id,
        "question": request.question,
        "dataset_ids": list(request.dataset_ids),
        "task_type": profile.task_type,
        "event_seq": 0,
        "injected_context_version": "v1",
    }
    return state
