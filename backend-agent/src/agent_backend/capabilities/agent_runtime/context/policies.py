from __future__ import annotations

from agent_backend.capabilities.agent_runtime.context.contracts import ContextPolicy
from agent_backend.foundation.contracts.task import AnalysisTaskType


def resolve_injection_strategy(task_type: AnalysisTaskType) -> str:
    mapping = {
        "trend_analysis": "trend_bundle",
        "comparison_analysis": "comparison_bundle",
        "distribution_analysis": "distribution_bundle",
        "resume_recovery": "checkpoint_first",
        "unknown": "default_bundle",
    }
    return mapping[task_type]


def resolve_context_policy(agent_name: str, node_name: str) -> ContextPolicy:
    policy_key = f"{agent_name}.{node_name}"
    policies = {
        "data_analysis_agent.generate_sql": ContextPolicy(
            policy_name="generate_sql_v2",
            agent_name=agent_name,
            node_name=node_name,
            allowed_sections=[
                "identity",
                "request",
                "access",
                "dataset",
                "schema",
                "conversation",
                "previous_turn",
                "repair",
                "runtime",
                "meta",
            ],
            required_sections=["request", "access", "dataset", "schema"],
            max_schema_chars=4000,
            max_conversation_chars=2000,
            max_previous_turns=1,
            max_repair_items=3,
            include_raw_rows=False,
        ),
        "data_analysis_agent.repair_sql": ContextPolicy(
            policy_name="repair_sql_v2",
            agent_name=agent_name,
            node_name=node_name,
            allowed_sections=[
                "identity",
                "request",
                "access",
                "dataset",
                "schema",
                "previous_turn",
                "repair",
                "runtime",
                "meta",
            ],
            required_sections=["request", "access", "dataset", "schema", "repair"],
            max_schema_chars=4000,
            max_repair_items=3,
            include_raw_rows=False,
        ),
        "data_analysis_agent.interpret_result": ContextPolicy(
            policy_name="interpret_result_v2",
            agent_name=agent_name,
            node_name=node_name,
            allowed_sections=[
                "identity",
                "request",
                "dataset",
                "conversation",
                "previous_turn",
                "execution_result",
                "runtime",
                "meta",
            ],
            required_sections=["request", "execution_result"],
            max_conversation_chars=2000,
            include_raw_rows=False,
        ),
        "data_analysis_agent.build_chart": ContextPolicy(
            policy_name="build_chart_v2",
            agent_name=agent_name,
            node_name=node_name,
            allowed_sections=[
                "identity",
                "request",
                "dataset",
                "previous_turn",
                "execution_result",
                "chart",
                "runtime",
                "meta",
            ],
            required_sections=["request", "execution_result"],
            include_raw_rows=False,
        ),
    }
    try:
        return policies[policy_key]
    except KeyError as exc:
        raise ValueError(f"No context policy configured for {policy_key}") from exc
