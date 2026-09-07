from __future__ import annotations

from shared_models.memory import ContextInjectionBundle, NodeCheckpointSnapshot
from shared_models.task import AnalysisTaskRequest

from context_hub.classifier import classify_task


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
