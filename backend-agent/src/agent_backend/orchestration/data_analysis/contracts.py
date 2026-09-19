from __future__ import annotations

from typing import Literal


DataAnalysisNodeId = Literal[
    "load_task_context",
    "build_context",
    "generate_sql",
    "validate_sql",
    "run_query",
    "interpret_result",
    "build_chart",
    "persist_result",
]


ReservedDataAnalysisNodeId = Literal[
    "repair_sql",
    "human_review_interrupt",
    "python_analysis",
    "schema_profile",
    "plan_analysis",
    "memory_update",
    "eval_record",
    "mcp_call",
    "fail_task",
]


DagEdge = tuple[str, str]
