from __future__ import annotations

from agent_backend.orchestration.data_analysis.contracts import (
    DagEdge,
    DataAnalysisNodeId,
)


MVP_NODE_ORDER: tuple[DataAnalysisNodeId, ...] = (
    "load_task_context",
    "build_context",
    "generate_sql",
    "validate_sql",
    "execute_sql",
    "interpret_result",
    "build_chart",
    "persist_result",
)

MVP_DAG_EDGES: tuple[DagEdge, ...] = (
    ("load_task_context", "build_context"),
    ("build_context", "generate_sql"),
    ("generate_sql", "validate_sql"),
    ("validate_sql", "execute_sql"),
    ("execute_sql", "interpret_result"),
    ("interpret_result", "build_chart"),
    ("build_chart", "persist_result"),
)

