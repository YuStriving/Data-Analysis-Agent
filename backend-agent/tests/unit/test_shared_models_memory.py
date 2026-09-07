from agent_backend.foundation.contracts.memory import NodeCheckpointSnapshot


def test_snapshot_contains_eight_core_groups() -> None:
    snapshot = NodeCheckpointSnapshot.demo()
    assert snapshot.core.identity.user_id == "user-1"
    assert snapshot.core.graph_state.node_name == "generate_sql"
    assert snapshot.core.task_state.task_type == "trend_analysis"
    assert snapshot.core.context_state.dataset_refs == ["dataset-sales"]
    assert snapshot.core.tool_state.last_tool_name == "sql_guard"
    assert snapshot.core.execution_state.prompt_version == "v1"
    assert snapshot.core.recovery_state.manual_restore_required is True
    assert snapshot.core.audit_state.event_seq == 7
