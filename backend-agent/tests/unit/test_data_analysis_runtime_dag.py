from agent_backend.orchestration.data_analysis import (
    MVP_DAG_EDGES,
    MVP_NODE_ORDER,
)


def test_mvp_data_analysis_dag_has_eight_nodes_in_order() -> None:
    assert MVP_NODE_ORDER == (
        "load_task_context",
        "build_context",
        "generate_sql",
        "validate_sql",
        "execute_sql",
        "interpret_result",
        "build_chart",
        "persist_result",
    )


def test_mvp_data_analysis_dag_edges_follow_node_order() -> None:
    assert MVP_DAG_EDGES == tuple(zip(MVP_NODE_ORDER, MVP_NODE_ORDER[1:]))
