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
    "run_query",
    "interpret_result",
    "build_chart",
    "persist_result",
)

MVP_DAG_EDGES: tuple[DagEdge, ...] = (
    ("load_task_context", "build_context"),
    ("build_context", "generate_sql"),
    ("generate_sql", "validate_sql"),
    ("validate_sql", "run_query"),
    ("run_query", "interpret_result"),
    ("interpret_result", "build_chart"),
    ("build_chart", "persist_result"),
)

RESERVED_DAG_EDGES: tuple[DagEdge, ...] = (
    ("validate_sql", "repair_sql"),
    ("repair_sql", "validate_sql"),
    ("validate_sql", "human_review_interrupt"),
    ("human_review_interrupt", "run_query"),
    ("run_query", "repair_sql"),
    ("run_query", "python_analysis"),
    ("python_analysis", "interpret_result"),
    ("persist_result", "memory_update"),
    ("persist_result", "eval_record"),
)
