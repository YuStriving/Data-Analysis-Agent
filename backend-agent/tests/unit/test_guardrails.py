from agent_backend.capabilities.agent_runtime.guardrails.sql import validate_sql, validate_sql_detailed


def test_validate_sql_rejects_write_statement() -> None:
    assert not validate_sql("DELETE FROM sales")


def test_validate_sql_detailed_serializes_passed_result_with_policy_extensions() -> None:
    result = validate_sql_detailed(
        "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month",
        allowed_relations={"sales": {"columns": [{"name": "order_month"}, {"name": "revenue"}]}},
        policy_metadata={"masked_columns": [], "denied_columns": [], "policy_warnings": []},
    )

    assert result.passed is True
    assert result.rule_code == "SQL_VALID"
    assert result.risk_level == "low"
    assert result.recoverable is False
    assert result.referenced_relations == ["sales"]
    assert result.referenced_fields == ["order_month", "revenue"]
    assert result.warnings == []
    assert result.policy_metadata == {
        "masked_columns": [],
        "denied_columns": [],
        "policy_warnings": [],
    }
    assert result.model_dump(mode="json")["validation_version"] == "sql_validation_v1"


def test_validate_sql_detailed_rejects_empty_sql() -> None:
    result = validate_sql_detailed("")

    assert result.passed is False
    assert result.rule_code == "SQL_EMPTY"
    assert result.recoverable is True


def test_validate_sql_detailed_rejects_write_statement() -> None:
    result = validate_sql_detailed("DELETE FROM sales")

    assert result.passed is False
    assert result.rule_code == "SQL_FORBIDDEN_TOKEN"
    assert result.risk_level == "high"
    assert result.recoverable is False


def test_validate_sql_detailed_rejects_multiple_statements() -> None:
    result = validate_sql_detailed("SELECT * FROM sales; SELECT * FROM users")

    assert result.passed is False
    assert result.rule_code == "SQL_MULTIPLE_STATEMENTS"
    assert result.risk_level == "high"


def test_validate_sql_detailed_rejects_unknown_relation() -> None:
    result = validate_sql_detailed(
        "SELECT order_month FROM secret_sales",
        allowed_relations={"sales": {"columns": [{"name": "order_month"}]}},
    )

    assert result.passed is False
    assert result.rule_code == "SQL_UNAUTHORIZED_RELATION"
    assert result.recoverable is False
    assert result.referenced_relations == ["secret_sales"]


def test_validate_sql_detailed_rejects_unknown_field() -> None:
    result = validate_sql_detailed(
        "SELECT gross_margin FROM sales",
        allowed_relations={"sales": {"columns": [{"name": "order_month"}]}},
    )

    assert result.passed is False
    assert result.rule_code == "SQL_UNAUTHORIZED_FIELD"
    assert result.recoverable is False
    assert result.referenced_fields == ["gross_margin"]


def test_validate_sql_detailed_warns_for_detail_query_without_limit() -> None:
    result = validate_sql_detailed(
        "SELECT order_month, revenue FROM sales",
        allowed_relations={"sales": {"columns": [{"name": "order_month"}, {"name": "revenue"}]}},
    )

    assert result.passed is True
    assert result.rule_code == "SQL_VALID_WITH_WARNINGS"
    assert result.risk_level == "medium"
    assert "SQL_RESULT_SCALE_RISK" in result.warnings


def test_validate_sql_detailed_allows_aggregate_without_limit() -> None:
    result = validate_sql_detailed(
        "SELECT order_month, SUM(revenue) AS revenue FROM sales GROUP BY order_month",
        allowed_relations={"sales": {"columns": [{"name": "order_month"}, {"name": "revenue"}]}},
    )

    assert result.passed is True
    assert "SQL_RESULT_SCALE_RISK" not in result.warnings

