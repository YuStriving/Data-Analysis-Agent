from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

FORBIDDEN_TOKENS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
}

SQL_FUNCTIONS = {
    "AVG",
    "COUNT",
    "MAX",
    "MIN",
    "SUM",
    "ROUND",
    "DATE",
    "YEAR",
    "MONTH",
    "DAY",
}

SQL_KEYWORDS = {
    "AS",
    "AND",
    "ASC",
    "BY",
    "CASE",
    "DESC",
    "DISTINCT",
    "ELSE",
    "END",
    "FROM",
    "GROUP",
    "HAVING",
    "IN",
    "IS",
    "LIMIT",
    "NOT",
    "NULL",
    "ON",
    "OR",
    "ORDER",
    "SELECT",
    "THEN",
    "WHEN",
    "WHERE",
    "WITH",
}

RiskLevel = Literal["low", "medium", "high"]


class SqlValidationResult(BaseModel):
    passed: bool
    rule_code: str
    message: str
    risk_level: RiskLevel = "low"
    recoverable: bool = False
    referenced_relations: list[str] = Field(default_factory=list)
    referenced_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    policy_metadata: dict[str, Any] = Field(default_factory=dict)
    validation_version: str = "sql_validation_v1"


def validate_sql(
    sql: str,
    *,
    allowed_relations: dict[str, Any] | None = None,
) -> bool:
    return validate_sql_detailed(sql, allowed_relations=allowed_relations).passed


def validate_sql_detailed(
    sql: str,
    *,
    allowed_relations: dict[str, Any] | None = None,
    policy_metadata: dict[str, Any] | None = None,
) -> SqlValidationResult:
    stripped = sql.strip() if isinstance(sql, str) else ""
    if not stripped:
        return _result(
            passed=False,
            rule_code="SQL_EMPTY",
            message="Candidate SQL is empty.",
            recoverable=True,
            policy_metadata=policy_metadata,
        )

    normalized = _strip_string_literals(stripped).upper()
    if _has_multiple_statements(stripped):
        return _result(
            passed=False,
            rule_code="SQL_MULTIPLE_STATEMENTS",
            message="SQL must contain exactly one statement.",
            risk_level="high",
            policy_metadata=policy_metadata,
        )

    forbidden_token = _first_forbidden_token(normalized)
    if forbidden_token is not None:
        return _result(
            passed=False,
            rule_code="SQL_FORBIDDEN_TOKEN",
            message=f"SQL contains forbidden token: {forbidden_token}.",
            risk_level="high",
            policy_metadata=policy_metadata,
        )

    if not _is_readonly_select(normalized):
        return _result(
            passed=False,
            rule_code="SQL_NOT_READONLY_SELECT",
            message="SQL must be a readonly SELECT statement.",
            risk_level="high",
            recoverable=True,
            policy_metadata=policy_metadata,
        )

    referenced_relations = _referenced_relations(stripped)
    allowed = allowed_relations or {}
    if allowed:
        unknown_relations = [name for name in referenced_relations if name not in allowed]
        if unknown_relations:
            return _result(
                passed=False,
                rule_code="SQL_UNAUTHORIZED_RELATION",
                message=f"SQL references unauthorized relation: {unknown_relations[0]}.",
                risk_level="high",
                referenced_relations=referenced_relations,
                policy_metadata=policy_metadata,
            )

    known_fields = _allowed_fields(allowed)
    referenced_fields = _referenced_fields(stripped, known_fields)
    if known_fields:
        unknown_fields = _unknown_fields(stripped, known_fields, referenced_relations)
        if unknown_fields:
            return _result(
                passed=False,
                rule_code="SQL_UNAUTHORIZED_FIELD",
                message=f"SQL references unauthorized field: {unknown_fields[0]}.",
                risk_level="high",
                referenced_relations=referenced_relations,
                referenced_fields=unknown_fields,
                policy_metadata=policy_metadata,
            )

    warnings = []
    risk_level: RiskLevel = "low"
    rule_code = "SQL_VALID"
    if _is_detail_query_without_limit(normalized):
        warnings.append("SQL_RESULT_SCALE_RISK")
        risk_level = "medium"
        rule_code = "SQL_VALID_WITH_WARNINGS"

    return _result(
        passed=True,
        rule_code=rule_code,
        message="SQL validation passed.",
        risk_level=risk_level,
        referenced_relations=referenced_relations,
        referenced_fields=referenced_fields,
        warnings=warnings,
        policy_metadata=policy_metadata,
    )


def _result(
    *,
    passed: bool,
    rule_code: str,
    message: str,
    risk_level: RiskLevel = "low",
    recoverable: bool = False,
    referenced_relations: list[str] | None = None,
    referenced_fields: list[str] | None = None,
    warnings: list[str] | None = None,
    policy_metadata: dict[str, Any] | None = None,
) -> SqlValidationResult:
    return SqlValidationResult(
        passed=passed,
        rule_code=rule_code,
        message=message,
        risk_level=risk_level,
        recoverable=recoverable,
        referenced_relations=referenced_relations or [],
        referenced_fields=referenced_fields or [],
        warnings=warnings or [],
        policy_metadata=policy_metadata or {},
    )


def _strip_string_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)


def _has_multiple_statements(sql: str) -> bool:
    parts = [part.strip() for part in sql.split(";")]
    return len([part for part in parts if part]) > 1


def _first_forbidden_token(normalized_sql: str) -> str | None:
    for token in sorted(FORBIDDEN_TOKENS):
        if re.search(rf"\b{re.escape(token)}\b", normalized_sql):
            return token
    return None


def _is_readonly_select(normalized_sql: str) -> bool:
    return bool(re.match(r"^\s*(SELECT|WITH)\b", normalized_sql))


def _referenced_relations(sql: str) -> list[str]:
    names = re.findall(r"\b(?:FROM|JOIN)\s+([`\"\[]?[\w.]+[`\"\]]?)", sql, flags=re.IGNORECASE)
    return _dedupe([_clean_identifier(name).split(".")[-1] for name in names])


def _allowed_fields(allowed_relations: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for relation in allowed_relations.values():
        columns = relation.get("columns", []) if isinstance(relation, dict) else []
        for column in columns:
            if isinstance(column, dict) and isinstance(column.get("name"), str):
                fields.add(column["name"])
    return fields


def _referenced_fields(sql: str, known_fields: set[str]) -> list[str]:
    if not known_fields:
        return []
    identifiers = _select_like_identifiers(sql)
    return _dedupe([identifier for identifier in identifiers if identifier in known_fields])


def _unknown_fields(sql: str, known_fields: set[str], referenced_relations: list[str]) -> list[str]:
    relation_set = set(referenced_relations)
    unknown = []
    for identifier in _select_like_identifiers(sql):
        if identifier in known_fields or identifier in relation_set:
            continue
        unknown.append(identifier)
    return _dedupe(unknown)


def _select_like_identifiers(sql: str) -> list[str]:
    scrubbed = _strip_string_literals(sql)
    select_match = re.search(r"\bSELECT\b(?P<body>.*?)\bFROM\b", scrubbed, flags=re.IGNORECASE | re.DOTALL)
    group_match = re.search(
        r"\bGROUP\s+BY\b(?P<body>.*?)(?:\bORDER\s+BY\b|\bLIMIT\b|$)",
        scrubbed,
        flags=re.IGNORECASE | re.DOTALL,
    )
    order_match = re.search(r"\bORDER\s+BY\b(?P<body>.*?)(?:\bLIMIT\b|$)", scrubbed, flags=re.IGNORECASE | re.DOTALL)
    bodies = [
        match.group("body")
        for match in (select_match, group_match, order_match)
        if match is not None
    ]
    identifiers: list[str] = []
    for body in bodies:
        body = re.sub(r"\bAS\s+[a-zA-Z_][\w]*\b", "", body, flags=re.IGNORECASE)
        for token in re.findall(r"\b[a-zA-Z_][\w]*\b", body):
            normalized = token.upper()
            if normalized in SQL_KEYWORDS or normalized in SQL_FUNCTIONS:
                continue
            identifiers.append(token)
    return _dedupe(identifiers)


def _is_detail_query_without_limit(normalized_sql: str) -> bool:
    aggregate_pattern = r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(|\bGROUP\s+BY\b"
    return not re.search(aggregate_pattern, normalized_sql) and not re.search(r"\bLIMIT\b", normalized_sql)


def _clean_identifier(value: str) -> str:
    return value.strip().strip("`\"[]")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped

