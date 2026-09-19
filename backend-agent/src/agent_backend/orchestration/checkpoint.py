from __future__ import annotations

from datetime import datetime, timezone

from agent_backend.capabilities.agent_runtime.checkpoint.contracts import (
    NodeCheckpointSnapshot,
)
from agent_backend.orchestration.state import AgentState


def capture_checkpoint(state: AgentState, node_id: str) -> NodeCheckpointSnapshot:
    now = datetime.now(timezone.utc)
    task_id = state["task_id"]
    trace_id = state["trace_id"]
    tenant_id = state.get("tenant_id", "")
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    snapshot_id = state.get("snapshot_id", f"{task_id}:{node_id}:{int(now.timestamp())}")

    return NodeCheckpointSnapshot(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        task_id=task_id,
        trace_id=trace_id,
        node_id=node_id,
        graph_name=state.get("graph_name", "analysis_graph"),
        node_name=state.get("node_name", node_id),
        node_status=state.get("node_status", "running"),
        previous_node=state.get("previous_node"),
        next_node=state.get("next_node"),
        resume_cursor=state.get("resume_cursor"),
        task_type=state.get("task_type", "unknown"),
        task_summary=state.get("task_summary", ""),
        current_step=state.get("current_step", node_id),
        current_goal=state.get("current_goal", ""),
        hot_context=dict(state.get("hot_context", {})),
        conversation_summary=state.get("conversation_summary", ""),
        confirmed_facts=list(state.get("confirmed_facts", [])),
        dataset_refs=list(state.get("dataset_ids", [])),
        injected_context_version=state.get("injected_context_version", "v1"),
        last_tool_name=state.get("last_tool_name"),
        last_tool_input_hash=state.get("last_tool_input_hash"),
        last_tool_output_ref=state.get("last_tool_output_ref"),
        retry_count=state.get("retry_count", 0),
        tool_status=state.get("tool_status"),
        llm_model=state.get("llm_model", ""),
        prompt_version=state.get("prompt_version", ""),
        token_usage=state.get("token_usage", 0),
        elapsed_ms=state.get("elapsed_ms", 0),
        interrupt_reason=state.get("interrupt_reason"),
        failure_stage=state.get("failure_stage"),
        manual_restore_required=state.get("manual_restore_required", True),
        last_stable_checkpoint=state.get("last_stable_checkpoint"),
        created_at=now,
        updated_at=now,
        event_seq=state.get("event_seq", 0),
    )


def restore_checkpoint(snapshot: NodeCheckpointSnapshot) -> AgentState:
    return AgentState(
        task_id=snapshot.task_id,
        trace_id=snapshot.trace_id,
        tenant_id=snapshot.tenant_id,
        user_id=snapshot.user_id,
        session_id=snapshot.session_id,
        question=snapshot.hot_context.get("question", ""),
        dataset_ids=list(snapshot.dataset_refs),
        task_type=snapshot.task_type,
        node_id=snapshot.node_id,
        node_name=snapshot.node_name,
        node_status=snapshot.node_status,
        previous_node=snapshot.previous_node,
        next_node=snapshot.next_node,
        resume_cursor=snapshot.resume_cursor,
        task_summary=snapshot.task_summary,
        current_step=snapshot.current_step,
        current_goal=snapshot.current_goal,
        hot_context=dict(snapshot.hot_context),
        conversation_summary=snapshot.conversation_summary,
        confirmed_facts=list(snapshot.confirmed_facts),
        injected_context_version=snapshot.injected_context_version,
        last_tool_name=snapshot.last_tool_name,
        last_tool_input_hash=snapshot.last_tool_input_hash,
        last_tool_output_ref=snapshot.last_tool_output_ref,
        retry_count=snapshot.retry_count,
        tool_status=snapshot.tool_status,
        llm_model=snapshot.llm_model,
        prompt_version=snapshot.prompt_version,
        token_usage=snapshot.token_usage,
        elapsed_ms=snapshot.elapsed_ms,
        interrupt_reason=snapshot.interrupt_reason,
        failure_stage=snapshot.failure_stage,
        manual_restore_required=snapshot.manual_restore_required,
        last_stable_checkpoint=snapshot.last_stable_checkpoint,
        event_seq=snapshot.event_seq,
        snapshot_id=snapshot.snapshot_id,
    )


__all__ = ["capture_checkpoint", "restore_checkpoint"]
