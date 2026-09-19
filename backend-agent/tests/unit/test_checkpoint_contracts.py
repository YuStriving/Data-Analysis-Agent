from agent_backend.capabilities.agent_runtime.checkpoint.contracts import NodeCheckpointSnapshot


def test_snapshot_contains_eight_core_groups() -> None:
    snapshot = NodeCheckpointSnapshot.demo()
    assert snapshot.user_id == "user-1"
    assert snapshot.node_name == "generate_sql"
    assert snapshot.task_type == "trend_analysis"
    assert snapshot.dataset_refs == ["dataset-sales"]
    assert snapshot.last_tool_name == "sql_guard"
    assert snapshot.prompt_version == "v1"
    assert snapshot.manual_restore_required is True
    assert snapshot.event_seq == 7
