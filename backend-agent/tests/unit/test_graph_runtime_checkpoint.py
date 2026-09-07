from graph_runtime.checkpoint import capture_checkpoint, restore_checkpoint
from graph_runtime.state import AgentState


def test_restore_checkpoint_keeps_last_stable_node() -> None:
    state: AgentState = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "session_id": "session-1",
        "question": "...",
        "dataset_ids": ["dataset-sales"],
        "task_type": "trend_analysis",
        "node_id": "generate_sql",
        "node_name": "generate_sql",
        "node_status": "running",
        "resume_cursor": "cursor-1",
        "task_summary": "Analyze monthly revenue trend",
        "current_step": "generate_sql",
        "current_goal": "Generate read-only SQL",
        "hot_context": {"question": "Show revenue trend"},
        "conversation_summary": "User wants monthly revenue trend analysis.",
        "confirmed_facts": ["dataset-sales is authorized"],
        "injected_context_version": "v1",
        "last_tool_name": "sql_guard",
        "retry_count": 1,
        "tool_status": "passed",
        "llm_model": "gpt-5",
        "prompt_version": "v1",
        "token_usage": 128,
        "elapsed_ms": 42,
        "interrupt_reason": "manual_checkpoint",
        "failure_stage": "node_exit",
        "manual_restore_required": True,
        "last_stable_checkpoint": "cursor-1",
        "event_seq": 7,
    }

    snapshot = capture_checkpoint(state, node_id="generate_sql")
    restored = restore_checkpoint(snapshot)

    assert snapshot.core.graph_state.node_name == "generate_sql"
    assert restored["node_id"] == "generate_sql"
    assert restored["resume_cursor"] == "cursor-1"
