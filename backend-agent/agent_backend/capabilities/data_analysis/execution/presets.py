from __future__ import annotations

from agent_backend.agent_runtime.execution_control.contracts import (
    AgentSpec,
    EdgeSpec,
    NodeSpec,
)
from agent_backend.agent_runtime.execution_control.policies import (
    BudgetPolicy,
    RuntimePolicy,
    ToolPolicy,
)


def build_data_analysis_agent_spec() -> AgentSpec:
    return AgentSpec(
        agent_id="data_analysis_agent",
        execution_mode="workflow_mode",
        entry_node="load_task_context",
        terminal_nodes={"persist_result", "fail_task"},
        node_specs={
            "load_task_context": NodeSpec(node_id="load_task_context"),
            "build_context": NodeSpec(
                node_id="build_context",
                allowed_tools={"mysql.schema_reader", "file.relation_normalizer"},
            ),
            "generate_sql": NodeSpec(node_id="generate_sql", max_visits=2),
            "validate_sql": NodeSpec(node_id="validate_sql", max_visits=5),
            "repair_sql": NodeSpec(node_id="repair_sql", max_visits=3),
            "execute_sql": NodeSpec(
                node_id="execute_sql",
                allowed_tools={"mysql.query_executor", "relation.query_executor"},
                max_visits=3,
            ),
            "interpret_result": NodeSpec(node_id="interpret_result"),
            "build_chart": NodeSpec(
                node_id="build_chart",
                allowed_tools={"chart.spec_builder"},
            ),
            "persist_result": NodeSpec(
                node_id="persist_result",
                can_emit_final_result=True,
            ),
            "fail_task": NodeSpec(
                node_id="fail_task",
                can_emit_final_result=True,
            ),
        },
        edge_specs=[
            EdgeSpec(from_node="load_task_context", to_node="build_context"),
            EdgeSpec(from_node="load_task_context", to_node="fail_task"),
            EdgeSpec(from_node="build_context", to_node="generate_sql"),
            EdgeSpec(from_node="build_context", to_node="fail_task"),
            EdgeSpec(from_node="generate_sql", to_node="validate_sql"),
            EdgeSpec(from_node="generate_sql", to_node="fail_task"),
            EdgeSpec(from_node="validate_sql", to_node="execute_sql"),
            EdgeSpec(
                from_node="validate_sql",
                to_node="repair_sql",
                max_traversals=3,
                loop_name="sql_repair_loop",
            ),
            EdgeSpec(
                from_node="repair_sql",
                to_node="validate_sql",
                max_traversals=3,
                loop_name="sql_repair_loop",
            ),
            EdgeSpec(from_node="execute_sql", to_node="interpret_result"),
            EdgeSpec(
                from_node="execute_sql",
                to_node="repair_sql",
                max_traversals=2,
                loop_name="sql_repair_loop",
            ),
            EdgeSpec(from_node="interpret_result", to_node="build_chart"),
            EdgeSpec(from_node="build_chart", to_node="persist_result"),
        ],
        runtime_policy=RuntimePolicy(
            max_steps=20,
            default_max_node_visits=3,
            repeated_error_limit=3,
            no_progress_limit=2,
            loop_attempt_limits={"sql_repair_loop": 3},
        ),
        budget_policy=BudgetPolicy(
            max_model_calls=6,
            max_tool_calls=10,
            max_elapsed_ms=120_000,
            record_token_usage=True,
        ),
        tool_policy=ToolPolicy(
            same_tool_call_limit=3,
            same_tool_failure_limit=2,
            allowed_risk_levels={"read_only", "compute_only", "low", "medium"},
        ),
    )
