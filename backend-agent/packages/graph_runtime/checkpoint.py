from __future__ import annotations

from datetime import datetime, timezone

from shared_models.memory import (
    AuditState,
    ContextState,
    ExecutionState,
    GraphState,
    MemoryIdentity,
    NodeCheckpointSnapshot,
    RecoveryState,
    SnapshotCore,
    TaskState,
    ToolState,
)

from graph_runtime.state import AgentState


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
        core=SnapshotCore(
            identity=MemoryIdentity(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id,
                snapshot_id=snapshot_id,
                node_id=node_id,
            ),
            graph_state=GraphState(
                graph_name=state.get("graph_name", "analysis_graph"),
                node_name=state.get("node_name", node_id),
                node_status=state.get("node_status", "running"),
                previous_node=state.get("previous_node"),
                next_node=state.get("next_node"),
                resume_cursor=state.get("resume_cursor"),
            ),
            task_state=TaskState(
                task_type=state.get("task_type", "unknown"),
                task_summary=state.get("task_summary", ""),
                current_step=state.get("current_step", node_id),
                current_goal=state.get("current_goal", ""),
            ),
            context_state=ContextState(
                hot_context=dict(state.get("hot_context", {})),
                conversation_summary=state.get("conversation_summary", ""),
                confirmed_facts=list(state.get("confirmed_facts", [])),
                dataset_refs=list(state.get("dataset_ids", [])),
                injected_context_version=state.get("injected_context_version", "v1"),
            ),
            tool_state=ToolState(
                last_tool_name=state.get("last_tool_name"),
                last_tool_input_hash=state.get("last_tool_input_hash"),
                last_tool_output_ref=state.get("last_tool_output_ref"),
                retry_count=state.get("retry_count", 0),
                tool_status=state.get("tool_status"),
            ),
            execution_state=ExecutionState(
                llm_model=state.get("llm_model", ""),
                prompt_version=state.get("prompt_version", ""),
                token_usage=state.get("token_usage", 0),
                elapsed_ms=state.get("elapsed_ms", 0),
            ),
            recovery_state=RecoveryState(
                interrupt_reason=state.get("interrupt_reason"),
                failure_stage=state.get("failure_stage"),
                manual_restore_required=state.get("manual_restore_required", True),
                last_stable_checkpoint=state.get("last_stable_checkpoint"),
            ),
            audit_state=AuditState(
                created_at=now,
                updated_at=now,
                event_seq=state.get("event_seq", 0),
            ),
        ),
    )


def restore_checkpoint(snapshot: NodeCheckpointSnapshot) -> AgentState:
    core = snapshot.core
    return AgentState(
        task_id=snapshot.task_id,
        trace_id=snapshot.trace_id,
        tenant_id=snapshot.tenant_id,
        user_id=snapshot.user_id,
        session_id=snapshot.session_id,
        question=core.context_state.hot_context.get("question", ""),
        dataset_ids=list(core.context_state.dataset_refs),
        task_type=core.task_state.task_type,
        node_id=snapshot.node_id,
        node_name=core.graph_state.node_name,
        node_status=core.graph_state.node_status,
        previous_node=core.graph_state.previous_node,
        next_node=core.graph_state.next_node,
        resume_cursor=core.graph_state.resume_cursor,
        task_summary=core.task_state.task_summary,
        current_step=core.task_state.current_step,
        current_goal=core.task_state.current_goal,
        hot_context=dict(core.context_state.hot_context),
        conversation_summary=core.context_state.conversation_summary,
        confirmed_facts=list(core.context_state.confirmed_facts),
        injected_context_version=core.context_state.injected_context_version,
        last_tool_name=core.tool_state.last_tool_name,
        last_tool_input_hash=core.tool_state.last_tool_input_hash,
        last_tool_output_ref=core.tool_state.last_tool_output_ref,
        retry_count=core.tool_state.retry_count,
        tool_status=core.tool_state.tool_status,
        llm_model=core.execution_state.llm_model,
        prompt_version=core.execution_state.prompt_version,
        token_usage=core.execution_state.token_usage,
        elapsed_ms=core.execution_state.elapsed_ms,
        interrupt_reason=core.recovery_state.interrupt_reason,
        failure_stage=core.recovery_state.failure_stage,
        manual_restore_required=core.recovery_state.manual_restore_required,
        last_stable_checkpoint=core.recovery_state.last_stable_checkpoint,
        event_seq=core.audit_state.event_seq,
        snapshot_id=snapshot.snapshot_id,
    )
