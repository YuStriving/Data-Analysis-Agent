from __future__ import annotations

from typing import Any

from agent_backend.capabilities.data_analysis.guardrails.sql import (
    validate_sql_detailed,
)
from agent_backend.orchestration.data_analysis.nodes._shared import (
    append_event,
    complete_node,
    enter_node,
    fail_node,
    has_error,
)
from agent_backend.orchestration.state import AgentState


def validate_sql(state: AgentState) -> AgentState:
    enter_node(state, "validate_sql")
    if has_error(state):
        return state

    analysis = state.setdefault("analysis", {})
    candidate_sql = str(analysis.get("candidate_sql", ""))
    result = validate_sql_detailed(
        candidate_sql,
        allowed_relations=_allowed_relations_from_state(state),
        policy_metadata=_policy_metadata_from_state(state),
    )
    result_payload = result.model_dump(mode="json")
    analysis["sql_validation"] = result_payload

    if result.passed:
        analysis["validated_sql"] = candidate_sql
        append_event(
            state,
            "sql_validated",
            {
                "rule_code": result.rule_code,
                "risk_level": result.risk_level,
                "referenced_relations": result.referenced_relations,
                "referenced_fields": result.referenced_fields,
                "warnings": result.warnings,
            },
        )
        return complete_node(state, "execute_sql")

    append_event(
        state,
        "sql_rejected",
        {
            "rule_code": result.rule_code,
            "message": result.message,
            "risk_level": result.risk_level,
            "recoverable": result.recoverable,
            "referenced_relations": result.referenced_relations,
            "referenced_fields": result.referenced_fields,
        },
        level="warning",
    )
    return fail_node(
        state,
        code=result.rule_code,
        message=result.message,
        failure_stage="validate_sql",
        user_action_required=False,
        recoverable=result.recoverable,
    )


def _allowed_relations_from_state(state: AgentState) -> dict[str, Any]:
    schema_context = state.get("context", {}).get("schema_context", {})
    if not isinstance(schema_context, dict):
        return {}
    field_summary = schema_context.get("field_summary", {})
    if not isinstance(field_summary, dict):
        return {}
    return {
        str(relation_name): dict(relation)
        for relation_name, relation in field_summary.items()
        if isinstance(relation, dict)
    }


def _policy_metadata_from_state(state: AgentState) -> dict[str, Any]:
    context = state.get("context", {})
    policy = context.get("sql_policy")
    if isinstance(policy, dict):
        return dict(policy)
    return {}
